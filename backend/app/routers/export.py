from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
import os
import tempfile
import shutil
import zipfile
import json
from datetime import datetime
from pathlib import Path
import re
import time
import uuid
from app.core import get_db_dependency, get_current_admin

router = APIRouter(prefix="/api/export", tags=["导出"])


class ExportFormat(str, Enum):
    YOLOV8 = "yolov8"      # YOLOv5/v7/v8 (Ultralytics)
    DARKNET = "darknet"    # YOLOv3/v4 (Darknet)
    COCO = "coco"          # COCO JSON


class ExportRequest(BaseModel):
    dataset_id: int
    format: ExportFormat = ExportFormat.YOLOV8
    output_name: Optional[str] = None
    train_ratio: float = Field(default=0.8, ge=0, le=1, allow_inf_nan=False)
    val_ratio: float = Field(default=0.1, ge=0, le=1, allow_inf_nan=False)
    test_ratio: float = Field(default=0.1, ge=0, le=1, allow_inf_nan=False)
    include_unlabeled: bool = False

    @field_validator("output_name")
    @classmethod
    def valid_output_name(cls, value):
        if value and (value in {".", ".."} or any(c in value for c in '/\\\x00')):
            raise ValueError("输出名称不能包含路径分隔符")
        return value



class ExportResponse(BaseModel):
    total_images: int
    train_images: int
    val_images: int
    test_images: int
    total_annotations: int
    categories: int
    format: str
    download_url: str


# Shared filesystem storage works across API workers and survives process restarts.
EXPORT_ROOT = Path(tempfile.gettempdir()) / "robomark-exports"
EXPORT_TTL_SECONDS = 3600


def cleanup_expired_exports():
    if not EXPORT_ROOT.exists():
        return
    for directory in EXPORT_ROOT.iterdir():
        if re.fullmatch(r"[0-9a-f]{32}", directory.name) and directory.is_dir() and not directory.is_symlink():
            try:
                if time.time() - directory.stat().st_mtime > EXPORT_TTL_SECONDS:
                    shutil.rmtree(directory, ignore_errors=True)
            except FileNotFoundError:
                pass  # Another worker already expired this artifact.



def get_export_formats():
    """获取支持的导出格式列表"""
    return [
        {"id": "yolov8", "name": "YOLOv5/v7/v8 (Ultralytics)", "description": "适用于 Ultralytics YOLO 系列，使用 data.yaml 配置"},
        {"id": "darknet", "name": "YOLO Darknet (v3/v4)", "description": "适用于原版 Darknet YOLO，使用 .names 和 .data 配置"},
        {"id": "coco", "name": "COCO JSON", "description": "通用格式，适用于多种框架（Detectron2, MMDetection 等）"},
    ]


@router.get("/formats")
async def list_export_formats():
    """获取支持的导出格式"""
    return get_export_formats()


@router.post("", response_model=ExportResponse)
async def export_dataset(
    request: ExportRequest,
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """导出数据集（支持多种格式）"""
    # 验证比例
    total_ratio = request.train_ratio + request.val_ratio + request.test_ratio
    if abs(total_ratio - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail="分割比例之和必须为1")

    with conn.cursor() as cursor:
        # 获取数据集
        cursor.execute("SELECT * FROM datasets WHERE id = %s", (request.dataset_id,))
        dataset = cursor.fetchone()
        if not dataset:
            raise HTTPException(status_code=404, detail="数据集不存在")

        # 获取类别
        cursor.execute(
            "SELECT * FROM categories WHERE dataset_id = %s ORDER BY sort_order",
            (request.dataset_id,)
        )
        categories = cursor.fetchall()
        category_map = {cat['id']: idx for idx, cat in enumerate(categories)}

        # 获取图片
        if request.include_unlabeled:
            cursor.execute("SELECT * FROM images WHERE dataset_id = %s", (request.dataset_id,))
        else:
            cursor.execute("SELECT * FROM images WHERE dataset_id = %s AND status = 'labeled'", (request.dataset_id,))
        images = cursor.fetchall()

        total = len(images)
        if total == 0:
            raise HTTPException(status_code=400, detail="没有可导出的图片")

        # 创建临时目录
        EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
        cleanup_expired_exports()
        task_id = uuid.uuid4().hex
        export_dir = str(EXPORT_ROOT / task_id)
        os.makedirs(export_dir)
        output_name = request.output_name or f"dataset_{request.dataset_id}"
        output_path = os.path.join(export_dir, output_name)
        os.makedirs(output_path, exist_ok=True)

        # 计算分割点
        train_end = int(total * request.train_ratio)
        val_end = train_end + int(total * request.val_ratio)

        # 根据格式导出
        if request.format == ExportFormat.YOLOV8:
            stats = export_yolov8(output_path, images, categories, category_map,
                                  train_end, val_end, cursor)
        elif request.format == ExportFormat.DARKNET:
            stats = export_darknet(output_path, images, categories, category_map,
                                   train_end, val_end, cursor)
        elif request.format == ExportFormat.COCO:
            stats = export_coco(output_path, images, categories, category_map,
                               train_end, val_end, cursor, dataset['name'])

        # 创建ZIP文件
        zip_path = os.path.join(export_dir, f"{output_name}.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(output_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, export_dir)
                    zipf.write(file_path, arcname)



    return ExportResponse(
        total_images=total,
        train_images=stats["train"],
        val_images=stats["val"],
        test_images=stats["test"],
        total_annotations=stats["annotations"],
        categories=len(categories),
        format=request.format.value,
        download_url=f"/api/export/download/{task_id}"
    )


def export_yolov8(output_path, images, categories, category_map, train_end, val_end, cursor):
    """导出为 YOLOv5/v7/v8 格式"""
    # 创建目录结构
    for split in ["train", "val", "test"]:
        os.makedirs(os.path.join(output_path, "images", split), exist_ok=True)
        os.makedirs(os.path.join(output_path, "labels", split), exist_ok=True)

    # 创建 data.yaml
    names = [cat['name'] for cat in categories]
    yaml_content = f"""# YOLOv8 Dataset Config
path: .
train: images/train
val: images/val
test: images/test

nc: {len(names)}
names: {names}
"""
    with open(os.path.join(output_path, "data.yaml"), "w", encoding="utf-8") as f:
        f.write(yaml_content)

    stats = {"train": 0, "val": 0, "test": 0, "annotations": 0}

    for idx, image in enumerate(images):
        split = "train" if idx < train_end else ("val" if idx < val_end else "test")

        # 复制图片
        src_path = image['file_path']
        if os.path.exists(src_path):
            shutil.copy2(src_path, os.path.join(output_path, "images", split, image['filename']))
            stats[split] += 1

        # 创建标签文件
        cursor.execute("SELECT * FROM annotations WHERE image_id = %s", (image['id'],))
        annotations = cursor.fetchall()

        label_filename = os.path.splitext(image['filename'])[0] + ".txt"
        label_path = os.path.join(output_path, "labels", split, label_filename)

        with open(label_path, "w") as f:
            for ann in annotations:
                if ann['category_id'] in category_map:
                    class_id = category_map[ann['category_id']]
                    # 对平行四边形使用外接矩形（已经是 x_center, y_center, width, height）
                    f.write(f"{class_id} {ann['x_center']:.6f} {ann['y_center']:.6f} {ann['width']:.6f} {ann['height']:.6f}\n")
                    stats["annotations"] += 1

    return stats


def export_darknet(output_path, images, categories, category_map, train_end, val_end, cursor):
    """导出为 YOLO Darknet 格式 (v3/v4)"""
    # 创建目录结构
    images_dir = os.path.join(output_path, "images")
    labels_dir = os.path.join(output_path, "labels")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(labels_dir, exist_ok=True)

    # 创建 classes.names 文件
    names = [cat['name'] for cat in categories]
    with open(os.path.join(output_path, "classes.names"), "w", encoding="utf-8") as f:
        for name in names:
            f.write(f"{name}\n")

    train_list = []
    val_list = []
    test_list = []

    stats = {"train": 0, "val": 0, "test": 0, "annotations": 0}

    for idx, image in enumerate(images):
        split = "train" if idx < train_end else ("val" if idx < val_end else "test")

        # 复制图片
        src_path = image['file_path']
        dst_image_path = os.path.join(images_dir, image['filename'])
        if os.path.exists(src_path):
            shutil.copy2(src_path, dst_image_path)
            stats[split] += 1

            # 记录路径（相对路径）
            rel_path = f"images/{image['filename']}"
            if split == "train":
                train_list.append(rel_path)
            elif split == "val":
                val_list.append(rel_path)
            else:
                test_list.append(rel_path)

        # 创建标签文件
        cursor.execute("SELECT * FROM annotations WHERE image_id = %s", (image['id'],))
        annotations = cursor.fetchall()

        label_filename = os.path.splitext(image['filename'])[0] + ".txt"
        label_path = os.path.join(labels_dir, label_filename)

        with open(label_path, "w") as f:
            for ann in annotations:
                if ann['category_id'] in category_map:
                    class_id = category_map[ann['category_id']]
                    f.write(f"{class_id} {ann['x_center']:.6f} {ann['y_center']:.6f} {ann['width']:.6f} {ann['height']:.6f}\n")
                    stats["annotations"] += 1

    # 创建路径列表文件
    with open(os.path.join(output_path, "train.txt"), "w") as f:
        f.write("\n".join(train_list))
    with open(os.path.join(output_path, "val.txt"), "w") as f:
        f.write("\n".join(val_list))
    with open(os.path.join(output_path, "test.txt"), "w") as f:
        f.write("\n".join(test_list))

    # 创建 .data 配置文件
    data_content = f"""classes = {len(names)}
train = train.txt
valid = val.txt
names = classes.names
backup = backup/
"""
    with open(os.path.join(output_path, "dataset.data"), "w") as f:
        f.write(data_content)

    return stats


def export_coco(output_path, images, categories, category_map, train_end, val_end, cursor, dataset_name):
    """导出为 COCO JSON 格式"""
    # 创建目录结构
    for split in ["train", "val", "test"]:
        os.makedirs(os.path.join(output_path, split), exist_ok=True)

    annotations_dir = os.path.join(output_path, "annotations")
    os.makedirs(annotations_dir, exist_ok=True)

    stats = {"train": 0, "val": 0, "test": 0, "annotations": 0}

    # COCO 格式的类别（ID 从 1 开始）
    coco_categories = [
        {"id": idx + 1, "name": cat['name'], "supercategory": "object"}
        for idx, cat in enumerate(categories)
    ]

    # 分割数据
    splits_data = {
        "train": {"images": [], "annotations": []},
        "val": {"images": [], "annotations": []},
        "test": {"images": [], "annotations": []}
    }

    annotation_id = 1

    for idx, image in enumerate(images):
        split = "train" if idx < train_end else ("val" if idx < val_end else "test")

        # 复制图片
        src_path = image['file_path']
        dst_image_path = os.path.join(output_path, split, image['filename'])
        if os.path.exists(src_path):
            shutil.copy2(src_path, dst_image_path)
            stats[split] += 1

            # COCO 图片信息
            img_width = image['width'] or 640
            img_height = image['height'] or 480

            coco_image = {
                "id": image['id'],
                "file_name": image['filename'],
                "width": img_width,
                "height": img_height
            }
            splits_data[split]["images"].append(coco_image)

            # 获取标注
            cursor.execute("SELECT * FROM annotations WHERE image_id = %s", (image['id'],))
            annotations = cursor.fetchall()

            for ann in annotations:
                if ann['category_id'] in category_map:
                    ann_type = ann.get('annotation_type', 'bbox')

                    if ann_type == 'parallelogram' and ann.get('p1_x') is not None:
                        # 平行四边形：使用 polygon 格式
                        points = [
                            (ann['p1_x'], ann['p1_y']),
                            (ann['p2_x'], ann['p2_y']),
                            (ann['p3_x'], ann['p3_y']),
                            (ann['p4_x'], ann['p4_y']),
                        ]
                        # 转换为像素坐标
                        flat_segmentation = []
                        for px, py in points:
                            flat_segmentation.extend([round(px * img_width, 2), round(py * img_height, 2)])

                        # 计算外接矩形
                        xs = [p[0] * img_width for p in points]
                        ys = [p[1] * img_height for p in points]
                        min_x, max_x = min(xs), max(xs)
                        min_y, max_y = min(ys), max(ys)
                        bbox_w = max_x - min_x
                        bbox_h = max_y - min_y

                        # 使用 Shoelace 公式计算面积
                        area = 0
                        for i in range(len(points)):
                            j = (i + 1) % len(points)
                            area += points[i][0] * points[j][1] * img_width * img_height
                            area -= points[j][0] * points[i][1] * img_width * img_height
                        area = abs(area) / 2

                        coco_ann = {
                            "id": annotation_id,
                            "image_id": image['id'],
                            "category_id": category_map[ann['category_id']] + 1,
                            "bbox": [round(min_x, 2), round(min_y, 2), round(bbox_w, 2), round(bbox_h, 2)],
                            "area": round(area, 2),
                            "segmentation": [flat_segmentation],
                            "iscrowd": 0
                        }
                    else:
                        # 矩形框：原有逻辑
                        x_center = ann['x_center'] * img_width
                        y_center = ann['y_center'] * img_height
                        width = ann['width'] * img_width
                        height = ann['height'] * img_height

                        x = x_center - width / 2
                        y = y_center - height / 2

                        coco_ann = {
                            "id": annotation_id,
                            "image_id": image['id'],
                            "category_id": category_map[ann['category_id']] + 1,
                            "bbox": [round(x, 2), round(y, 2), round(width, 2), round(height, 2)],
                            "area": round(width * height, 2),
                            "iscrowd": 0
                        }

                    splits_data[split]["annotations"].append(coco_ann)
                    annotation_id += 1
                    stats["annotations"] += 1

    # 写入 JSON 文件
    for split in ["train", "val", "test"]:
        coco_data = {
            "info": {
                "description": f"{dataset_name} - {split}",
                "version": "1.0",
                "year": datetime.now().year,
                "date_created": datetime.now().isoformat()
            },
            "licenses": [],
            "images": splits_data[split]["images"],
            "annotations": splits_data[split]["annotations"],
            "categories": coco_categories
        }

        json_path = os.path.join(annotations_dir, f"instances_{split}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(coco_data, f, ensure_ascii=False, indent=2)

    return stats


# 保留旧的 API 路径兼容
@router.post("/yolo", response_model=ExportResponse)
async def export_yolo_legacy(
    request: ExportRequest,
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """导出数据集为YOLO格式（兼容旧接口）"""
    request.format = ExportFormat.YOLOV8
    return await export_dataset(request, conn, current_admin)


@router.get("/download/{task_id}")
async def download_export(
    task_id: str,
    current_admin = Depends(get_current_admin)
):
    """下载导出的文件"""
    if not re.fullmatch(r"[0-9a-f]{32}", task_id):
        raise HTTPException(status_code=404, detail="导出任务不存在或已过期")
    directory = EXPORT_ROOT / task_id
    if not directory.is_dir() or directory.is_symlink():
        raise HTTPException(status_code=404, detail="导出任务不存在或已过期")
    if time.time() - directory.stat().st_mtime > EXPORT_TTL_SECONDS:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(status_code=404, detail="导出任务已过期，请重新导出")
    archives = list(directory.glob("*.zip"))
    if len(archives) != 1 or not archives[0].is_file() or archives[0].is_symlink():
        raise HTTPException(status_code=404, detail="文件不存在")
    # Keep the archive until expiry so interrupted or repeated downloads can retry.
    return FileResponse(archives[0], media_type="application/zip", filename=archives[0].name)
