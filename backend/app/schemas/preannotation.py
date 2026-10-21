"""统一标注契约；模型输出与审核草稿使用同一几何验证。"""
from typing import Literal, Optional, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator
import math

POINT_FIELDS = [f"p{i}_{axis}" for i in range(1, 5) for axis in ("x", "y")]
GEOMETRY_FIELDS = ["category_id", "annotation_type", "x_center", "y_center", "width", "height", *POINT_FIELDS]


class Annotation(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    category_id: int = Field(gt=0)
    annotation_type: Literal["bbox", "parallelogram"] = "bbox"
    x_center: float = Field(ge=0, le=1)
    y_center: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    p1_x: Optional[float] = None
    p1_y: Optional[float] = None
    p2_x: Optional[float] = None
    p2_y: Optional[float] = None
    p3_x: Optional[float] = None
    p3_y: Optional[float] = None
    p4_x: Optional[float] = None
    p4_y: Optional[float] = None
    source_preannotation_id: Optional[int] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_geometry(self):
        if self.annotation_type == "bbox":
            if (self.x_center - self.width / 2 < -1e-6 or self.x_center + self.width / 2 > 1 + 1e-6
                    or self.y_center - self.height / 2 < -1e-6 or self.y_center + self.height / 2 > 1 + 1e-6):
                raise ValueError("矩形边界超出图片")
            for name in POINT_FIELDS:
                setattr(self, name, None)
        else:
            points = []
            for i in range(1, 5):
                x, y = getattr(self, f"p{i}_x"), getattr(self, f"p{i}_y")
                if x is None or y is None or not math.isfinite(x) or not math.isfinite(y) or not (0 <= x <= 1 and 0 <= y <= 1):
                    raise ValueError("四点坐标必须有限且位于 0–1 范围")
                points.append((x, y))
            cross = []
            for i in range(4):
                a, b, c = points[i], points[(i + 1) % 4], points[(i + 2) % 4]
                cross.append((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))
            if not (all(v > 1e-10 for v in cross) or all(v < -1e-10 for v in cross)):
                raise ValueError("四点须按边界顺序构成有效凸四边形")
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            self.x_center, self.y_center = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
            self.width, self.height = max(xs)-min(xs), max(ys)-min(ys)
        return self


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    endpoint: str = Field(min_length=1, max_length=2000)
    interface_type: Literal["openai", "http_json"] = "openai"
    http_method: Literal["POST", "PUT"] = "POST"
    model: str = Field(default="", max_length=200)
    api_key: Optional[str] = Field(default=None, max_length=8192)
    clear_credentials: bool = False
    headers: dict[str, str] = Field(default_factory=dict)
    request_template: dict[str, Any] = Field(default_factory=dict)
    response_path: str = "choices[0].message.content"
    annotations_path: str = "annotations"
    field_mapping: dict[str, str] = Field(default_factory=dict)
    coordinate_system: Literal["normalized", "pixels", "relative_1000"] = "normalized"
    box_format: Literal["center", "xyxy"] = "center"
    structured_output: Literal["none", "response_format", "vllm"] = "none"
    timeout_seconds: int = Field(default=120, ge=5, le=600, description='连接与发送超时；不限制单图推理总耗时或响应读取等待')
    max_attempts: int = Field(default=3, ge=1, le=5)
    is_shared: bool = False


class TaskInput(BaseModel):
    profile_id: int = Field(gt=0)
    prompt: str = Field(min_length=1, max_length=12000)
    annotation_type: Literal["bbox", "parallelogram"] = "bbox"
    category_ids: list[int] = Field(min_length=1, max_length=200)
    sample_size: Optional[int] = Field(default=None, ge=1)


class ProfileTestInput(BaseModel):
    profile: ProfileInput
    existing_profile_id: Optional[int] = Field(default=None, gt=0)


class CandidateInput(Annotation):
    id: Optional[int] = Field(default=None, gt=0)
    is_deleted: bool = False


class DraftInput(BaseModel):
    revision: int = Field(ge=0)
    annotations: list[CandidateInput] = Field(max_length=500)


class ReviewInput(BaseModel):
    revision: int = Field(ge=0)
    image_revision: int = Field(ge=0)
    action: Literal["approve", "reject", "empty"]
