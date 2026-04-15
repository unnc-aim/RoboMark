import os
import time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.core import get_db_dependency, get_current_admin, get_current_user

router = APIRouter(prefix="/api/categories", tags=["类别"])

# 模板图片存储目录
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "category_templates")
os.makedirs(TEMPLATE_DIR, exist_ok=True)

# 预定义颜色
COLOR_OPTIONS = [
    '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF',
    '#FF8000', '#8000FF', '#0080FF', '#FF0080', '#80FF00', '#00FF80'
]


class CategoryCreate(BaseModel):
    dataset_id: int
    name: str
    shortcut_key: Optional[str] = None
    color: Optional[str] = "#FF0000"
    sort_order: Optional[int] = 0


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    shortcut_key: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    template_image_path: Optional[str] = None


class CategoryResponse(BaseModel):
    id: int
    dataset_id: int
    name: str
    shortcut_key: Optional[str]
    color: str
    sort_order: int
    template_image_path: Optional[str] = None
    created_at: datetime


class BatchTextImportRequest(BaseModel):
    text: str


@router.get("/dataset/{dataset_id}", response_model=List[CategoryResponse])
async def list_categories(
    dataset_id: int,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """获取数据集的类别列表"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="数据集不存在")

        cursor.execute(
            "SELECT * FROM categories WHERE dataset_id = %s ORDER BY sort_order",
            (dataset_id,)
        )
        categories = cursor.fetchall()

    return categories


@router.post("", response_model=CategoryResponse)
async def create_category(
    category_data: CategoryCreate,
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """创建类别"""
    with conn.cursor() as cursor:
        # 检查数据集是否存在
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (category_data.dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="数据集不存在")

        # 检查类别名是否重复
        cursor.execute(
            "SELECT id FROM categories WHERE dataset_id = %s AND name = %s",
            (category_data.dataset_id, category_data.name)
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="类别名已存在")

        # 检查快捷键是否重复
        if category_data.shortcut_key:
            cursor.execute(
                "SELECT id FROM categories WHERE dataset_id = %s AND shortcut_key = %s",
                (category_data.dataset_id, category_data.shortcut_key)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="快捷键已被使用")

        cursor.execute(
            "INSERT INTO categories (dataset_id, name, shortcut_key, color, sort_order) VALUES (%s, %s, %s, %s, %s)",
            (category_data.dataset_id, category_data.name, category_data.shortcut_key, category_data.color, category_data.sort_order)
        )
        category_id = cursor.lastrowid

        cursor.execute("SELECT * FROM categories WHERE id = %s", (category_id,))
        category = cursor.fetchone()

    return category


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_data: CategoryUpdate,
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """更新类别"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM categories WHERE id = %s", (category_id,))
        category = cursor.fetchone()
        if not category:
            raise HTTPException(status_code=404, detail="类别不存在")

        updates = []
        params = []

        if category_data.name is not None:
            # 检查名称是否重复
            cursor.execute(
                "SELECT id FROM categories WHERE dataset_id = %s AND name = %s AND id != %s",
                (category['dataset_id'], category_data.name, category_id)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="类别名已存在")
            updates.append("name = %s")
            params.append(category_data.name)

        if category_data.shortcut_key is not None:
            if category_data.shortcut_key:
                cursor.execute(
                    "SELECT id FROM categories WHERE dataset_id = %s AND shortcut_key = %s AND id != %s",
                    (category['dataset_id'], category_data.shortcut_key, category_id)
                )
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail="快捷键已被使用")
            updates.append("shortcut_key = %s")
            params.append(category_data.shortcut_key)

        if category_data.color is not None:
            updates.append("color = %s")
            params.append(category_data.color)

        if category_data.sort_order is not None:
            updates.append("sort_order = %s")
            params.append(category_data.sort_order)

        if category_data.template_image_path is not None:
            updates.append("template_image_path = %s")
            params.append(category_data.template_image_path)

        if updates:
            params.append(category_id)
            cursor.execute(f"UPDATE categories SET {', '.join(updates)} WHERE id = %s", params)

        cursor.execute("SELECT * FROM categories WHERE id = %s", (category_id,))
        category = cursor.fetchone()

    return category


@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """删除类别"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, template_image_path FROM categories WHERE id = %s", (category_id,))
        category = cursor.fetchone()
        if not category:
            raise HTTPException(status_code=404, detail="类别不存在")

        # 删除模板图片文件
        if category.get('template_image_path'):
            file_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                category['template_image_path'].lstrip('/')
            )
            if os.path.exists(file_path):
                os.remove(file_path)

        cursor.execute("DELETE FROM categories WHERE id = %s", (category_id,))

    return {"message": "删除成功"}


@router.post("/batch", response_model=List[CategoryResponse])
async def batch_create_categories(
    categories: List[CategoryCreate],
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """批量创建类别"""
    if not categories:
        raise HTTPException(status_code=400, detail="类别列表不能为空")

    dataset_id = categories[0].dataset_id

    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="数据集不存在")

        created_ids = []
        for cat_data in categories:
            if cat_data.dataset_id != dataset_id:
                raise HTTPException(status_code=400, detail="所有类别必须属于同一数据集")

            cursor.execute(
                "INSERT INTO categories (dataset_id, name, shortcut_key, color, sort_order) VALUES (%s, %s, %s, %s, %s)",
                (cat_data.dataset_id, cat_data.name, cat_data.shortcut_key, cat_data.color, cat_data.sort_order)
            )
            created_ids.append(cursor.lastrowid)

        cursor.execute(
            f"SELECT * FROM categories WHERE id IN ({','.join(['%s'] * len(created_ids))})",
            created_ids
        )
        created = cursor.fetchall()

    return created


class ImportFromDatasetRequest(BaseModel):
    source_dataset_id: int


@router.post("/import-from-dataset/{dataset_id}")
async def import_from_dataset(
    dataset_id: int,
    data: ImportFromDatasetRequest,
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """从其他数据集导入类别"""
    with conn.cursor() as cursor:
        # 检查目标数据集是否存在
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="目标数据集不存在")

        # 检查源数据集是否存在
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (data.source_dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="源数据集不存在")

        # 获取源数据集的类别
        cursor.execute(
            "SELECT name, shortcut_key, color, sort_order FROM categories WHERE dataset_id = %s ORDER BY sort_order",
            (data.source_dataset_id,)
        )
        source_categories = cursor.fetchall()

        if not source_categories:
            raise HTTPException(status_code=400, detail="源数据集没有类别")

        # 获取目标数据集已有的类别名
        cursor.execute(
            "SELECT name FROM categories WHERE dataset_id = %s",
            (dataset_id,)
        )
        existing_names = {row['name'] for row in cursor.fetchall()}

        # 获取目标数据集已用的快捷键
        cursor.execute(
            "SELECT shortcut_key FROM categories WHERE dataset_id = %s AND shortcut_key IS NOT NULL",
            (dataset_id,)
        )
        existing_keys = {row['shortcut_key'] for row in cursor.fetchall()}

        imported = 0
        skipped = 0
        for cat in source_categories:
            if cat['name'] in existing_names:
                skipped += 1
                continue

            # 检查快捷键是否已被使用
            shortcut_key = cat['shortcut_key']
            if shortcut_key and shortcut_key in existing_keys:
                shortcut_key = None  # 清除冲突的快捷键

            cursor.execute(
                """INSERT INTO categories (dataset_id, name, shortcut_key, color, sort_order)
                   VALUES (%s, %s, %s, %s, %s)""",
                (dataset_id, cat['name'], shortcut_key, cat['color'], cat['sort_order'])
            )
            imported += 1

            if shortcut_key:
                existing_keys.add(shortcut_key)
            existing_names.add(cat['name'])

    return {
        "message": f"成功导入 {imported} 个类别，跳过 {skipped} 个已存在的类别",
        "imported": imported,
        "skipped": skipped
    }


@router.post("/batch-text/{dataset_id}", response_model=List[CategoryResponse])
async def batch_text_import_categories(
    dataset_id: int,
    data: BatchTextImportRequest,
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """批量文本导入类别（每行一个名称）"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="数据集不存在")

        # 获取已有的类别名
        cursor.execute("SELECT name FROM categories WHERE dataset_id = %s", (dataset_id,))
        existing_names = {row['name'] for row in cursor.fetchall()}

        # 获取当前最大 sort_order
        cursor.execute(
            "SELECT COALESCE(MAX(sort_order), -1) as max_order FROM categories WHERE dataset_id = %s",
            (dataset_id,)
        )
        result = cursor.fetchone()
        sort_order = result['max_order'] + 1

        # 解析文本
        names = [line.strip() for line in data.text.strip().split('\n') if line.strip()]
        # 去重
        seen = set()
        unique_names = []
        for name in names:
            if name not in seen:
                seen.add(name)
                unique_names.append(name)

        created_ids = []
        for i, name in enumerate(unique_names):
            if name in existing_names:
                continue

            color = COLOR_OPTIONS[i % len(COLOR_OPTIONS)]
            cursor.execute(
                "INSERT INTO categories (dataset_id, name, color, sort_order) VALUES (%s, %s, %s, %s)",
                (dataset_id, name, color, sort_order + i)
            )
            created_ids.append(cursor.lastrowid)
            existing_names.add(name)

        if created_ids:
            cursor.execute(
                f"SELECT * FROM categories WHERE id IN ({','.join(['%s'] * len(created_ids))})",
                created_ids
            )
            created = cursor.fetchall()
        else:
            created = []

    return created


@router.post("/batch-images/{dataset_id}")
async def batch_image_import_categories(
    dataset_id: int,
    files: List[UploadFile] = File(...),
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """批量图片导入类别（图片文件名作为类别名，图片作为模板）"""
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}

    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="数据集不存在")

        # 获取已有的类别名
        cursor.execute("SELECT name FROM categories WHERE dataset_id = %s", (dataset_id,))
        existing_names = {row['name'] for row in cursor.fetchall()}

        # 获取当前最大 sort_order
        cursor.execute(
            "SELECT COALESCE(MAX(sort_order), -1) as max_order FROM categories WHERE dataset_id = %s",
            (dataset_id,)
        )
        result = cursor.fetchone()
        sort_order = result['max_order'] + 1

        imported = 0
        skipped = 0

        for file in files:
            if not file.filename:
                continue

            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in allowed_extensions:
                skipped += 1
                continue

            # 文件名（不含扩展名）作为类别名
            name = os.path.splitext(file.filename)[0].strip()
            if not name:
                continue

            if name in existing_names:
                skipped += 1
                continue

            color = COLOR_OPTIONS[imported % len(COLOR_OPTIONS)]

            # 创建类别
            cursor.execute(
                "INSERT INTO categories (dataset_id, name, color, sort_order) VALUES (%s, %s, %s, %s)",
                (dataset_id, name, color, sort_order + imported)
            )
            category_id = cursor.lastrowid

            # 保存模板图片
            filename = f"{category_id}_{int(time.time())}{ext}"
            file_path = os.path.join(TEMPLATE_DIR, filename)
            content = await file.read()
            with open(file_path, 'wb') as f:
                f.write(content)

            # 更新类别的模板图片路径
            db_path = f"uploads/category_templates/{filename}"
            cursor.execute(
                "UPDATE categories SET template_image_path = %s WHERE id = %s",
                (db_path, category_id)
            )

            imported += 1
            existing_names.add(name)

    return {
        "message": f"成功导入 {imported} 个类别，跳过 {skipped} 个",
        "imported": imported,
        "skipped": skipped
    }


@router.post("/{category_id}/template-image")
async def upload_template_image(
    category_id: int,
    file: UploadFile = File(...),
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """上传类别模板图片"""
    # 验证文件类型
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ''
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="不支持的图片格式")

    with conn.cursor() as cursor:
        cursor.execute("SELECT id, template_image_path FROM categories WHERE id = %s", (category_id,))
        category = cursor.fetchone()
        if not category:
            raise HTTPException(status_code=404, detail="类别不存在")

        # 删除旧模板图片
        if category.get('template_image_path'):
            old_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                category['template_image_path'].lstrip('/')
            )
            if os.path.exists(old_path):
                os.remove(old_path)

        # 保存新文件
        filename = f"{category_id}_{int(time.time())}{ext}"
        file_path = os.path.join(TEMPLATE_DIR, filename)
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)

        # 更新数据库
        db_path = f"uploads/category_templates/{filename}"
        cursor.execute(
            "UPDATE categories SET template_image_path = %s WHERE id = %s",
            (db_path, category_id)
        )

    return {"message": "上传成功", "path": db_path}


@router.delete("/{category_id}/template-image")
async def delete_template_image(
    category_id: int,
    conn = Depends(get_db_dependency),
    current_admin = Depends(get_current_admin)
):
    """删除类别模板图片"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, template_image_path FROM categories WHERE id = %s", (category_id,))
        category = cursor.fetchone()
        if not category:
            raise HTTPException(status_code=404, detail="类别不存在")

        if not category.get('template_image_path'):
            raise HTTPException(status_code=400, detail="该类别没有模板图片")

        # 删除文件
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            category['template_image_path'].lstrip('/')
        )
        if os.path.exists(file_path):
            os.remove(file_path)

        # 更新数据库
        cursor.execute(
            "UPDATE categories SET template_image_path = NULL WHERE id = %s",
            (category_id,)
        )

    return {"message": "删除成功"}


@router.get("/{category_id}/template-image")
async def get_template_image(
    category_id: int,
    conn = Depends(get_db_dependency)
):
    """获取类别模板图片（无需认证）"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT template_image_path FROM categories WHERE id = %s", (category_id,))
        category = cursor.fetchone()
        if not category or not category.get('template_image_path'):
            raise HTTPException(status_code=404, detail="模板图片不存在")

        file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            category['template_image_path'].lstrip('/')
        )
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="模板图片文件不存在")

    return FileResponse(file_path)
