<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from "vue";
import {
  lineIntersection,
  pointInPolygon,
} from "../features/annotation/domain/geometry";

const props = defineProps({
  imageId: Number,
  annotations: Array,
  categories: Array,
  readonly: { type: Boolean, default: false },
  selectedCategory: Object,
  mode: {
    type: String,
    default: "annotate", // 'annotate' | 'pan'
  },
  allowDrawWithoutCategory: {
    type: Boolean,
    default: false,
  },
  shapeMode: {
    type: String,
    default: "bbox", // 'bbox' | '4point' | '8point'
  },
});

const emit = defineEmits(["add", "update", "delete", "zoom-change"]);

const canvasRef = ref(null);
const containerRef = ref(null);
const ctx = ref(null);
const image = ref(null);
let resizeObserver;

// 画布状态
const scale = ref(1);
const offsetX = ref(0);
const offsetY = ref(0);

// 绘制状态
const isDrawing = ref(false);
const isDragging = ref(false); // 调整边框大小
const isMoving = ref(false); // 整体移动框
const isPanning = ref(false);
const spacePressed = ref(false);

const startPoint = ref({ x: 0, y: 0 });
const currentBox = ref(null);
const selectedAnnotation = ref(null);
const dragHandle = ref(null);

// 拖动调整时的临时边界框（用于实时预览）
const dragBox = ref(null);

// 平行四边形点标注状态
const currentPoints = ref([]);
const maxPoints = computed(() => {
  if (props.shapeMode === "4point") return 4;
  if (props.shapeMode === "8point") return 8;
  return 0;
});
const isPointMode = computed(
  () => props.shapeMode === "4point" || props.shapeMode === "8point",
);
const isAdjustingPoint = ref(false); // 长按拖动调整刚放置的点

// 图片URL
const imageUrl = computed(() => `/api/images/${props.imageId}/file`);

onMounted(() => {
  const canvas = canvasRef.value;
  ctx.value = canvas.getContext("2d");
  loadImage();
  resizeObserver = new ResizeObserver(() => fitToContainer());
  resizeObserver.observe(containerRef.value);

  window.addEventListener("keydown", handleKeyDown);
  window.addEventListener("keyup", handleKeyUp);
});

onUnmounted(() => {
  resizeObserver?.disconnect();
  window.removeEventListener("keydown", handleKeyDown);
  window.removeEventListener("keyup", handleKeyUp);
});

watch(
  () => props.imageId,
  () => {
    resetView();
    loadImage();
  },
);

watch(
  () => props.annotations,
  () => {
    if (selectedAnnotation.value) {
      selectedAnnotation.value =
        props.annotations.find(
          (a) => a.id === selectedAnnotation.value.id && !a.is_readonly,
        ) || null;
    }
    draw();
  },
  { deep: true },
);

// 模式变化时更新光标
watch(
  () => props.mode,
  () => {
    if (canvasRef.value) {
      if (props.mode === "pan") {
        canvasRef.value.style.cursor = "grab";
      } else {
        canvasRef.value.style.cursor = "crosshair";
      }
    }
  },
);

// 切换图片时清除正在标注的点
watch(
  () => props.imageId,
  () => {
    currentPoints.value = [];
  },
);

function loadImage() {
  if (!props.imageId) return;

  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => {
    image.value = img;
    fitToContainer();
    draw();
  };
  img.src = imageUrl.value;
}

function fitToContainer() {
  if (!image.value || !containerRef.value) return;

  const container = containerRef.value;
  const img = image.value;

  // 计算适合容器的缩放比例
  const scaleX = container.clientWidth / img.width;
  const scaleY = container.clientHeight / img.height;
  scale.value = Math.min(scaleX, scaleY) * 0.9;

  // 居中
  offsetX.value = (container.clientWidth - img.width * scale.value) / 2;
  offsetY.value = (container.clientHeight - img.height * scale.value) / 2;

  resizeCanvas();
}

function resizeCanvas() {
  if (!containerRef.value) return;
  canvasRef.value.width = containerRef.value.clientWidth;
  canvasRef.value.height = containerRef.value.clientHeight;
  draw();
}

function resetView() {
  scale.value = 1;
  offsetX.value = 0;
  offsetY.value = 0;
  selectedAnnotation.value = null;
  currentPoints.value = [];
}

function draw() {
  if (!ctx.value || !canvasRef.value) return;

  const canvas = canvasRef.value;
  ctx.value.clearRect(0, 0, canvas.width, canvas.height);

  // 绘制图片
  if (image.value) {
    ctx.value.save();
    ctx.value.translate(offsetX.value, offsetY.value);
    ctx.value.scale(scale.value, scale.value);
    ctx.value.drawImage(image.value, 0, 0);
    ctx.value.restore();
  }

  // 绘制已有标注
  props.annotations.forEach((ann, index) => {
    ctx.value.save();
    ctx.value.setLineDash(ann.is_candidate ? [6, 4] : []);
    const isSelected = ann.id === selectedAnnotation.value?.id;
    if (isSelected && (isDragging.value || isMoving.value) && dragBox.value) {
      drawAnnotationWithBox(ann, dragBox.value, index, true);
    } else {
      drawAnnotation(ann, index, isSelected);
    }
    ctx.value.restore();
  });

  // 绘制当前正在绘制的框（bbox模式）
  if (currentBox.value && !isPointMode.value) {
    drawBox(currentBox.value, props.selectedCategory?.color || "#409EFF", true);
  }

  // 绘制当前正在标注的点（点模式）
  if (currentPoints.value.length > 0 && isPointMode.value) {
    drawCurrentPoints();
  }
}

// 绘制当前正在标注的点
function drawCurrentPoints() {
  const color = props.selectedCategory?.color || "#409EFF";
  const points = currentPoints.value;

  // 在 4 点模式下：相邻点连线（1→2, 2→3, 3→4, 4→1 闭合）
  // 在 8 点模式下：每 2 个点连线（1→2, 3→4, 5→6, 7→8）
  if (props.shapeMode === "4point" && points.length >= 2) {
    ctx.value.beginPath();
    ctx.value.strokeStyle = color;
    ctx.value.lineWidth = 2;
    const first = imageToScreen(points[0].x, points[0].y);
    ctx.value.moveTo(first.x, first.y);
    for (let i = 1; i < points.length; i++) {
      const p = imageToScreen(points[i].x, points[i].y);
      ctx.value.lineTo(p.x, p.y);
    }
    // 如果满了4个点，闭合
    if (points.length === 4) {
      ctx.value.lineTo(first.x, first.y);
    }
    ctx.value.stroke();
    // 半透明填充
    if (points.length === 4) {
      ctx.value.fillStyle = color + "20";
      ctx.value.fill();
    }
  } else if (props.shapeMode === "8point") {
    ctx.value.beginPath();
    ctx.value.strokeStyle = color;
    ctx.value.lineWidth = 2;
    for (let i = 0; i < points.length; i += 2) {
      if (i + 1 < points.length) {
        const p1 = imageToScreen(points[i].x, points[i].y);
        const p2 = imageToScreen(points[i + 1].x, points[i + 1].y);
        ctx.value.beginPath();
        ctx.value.moveTo(p1.x, p1.y);
        ctx.value.lineTo(p2.x, p2.y);
        ctx.value.stroke();
      }
    }
  }

  // 绘制所有点
  points.forEach((p, i) => {
    const sp = imageToScreen(p.x, p.y);
    ctx.value.beginPath();
    ctx.value.arc(sp.x, sp.y, 5, 0, Math.PI * 2);
    ctx.value.fillStyle = color;
    ctx.value.fill();
    ctx.value.strokeStyle = "#fff";
    ctx.value.lineWidth = 1.5;
    ctx.value.stroke();
    // 显示点序号
    ctx.value.fillStyle = "#fff";
    ctx.value.font = "10px Arial";
    ctx.value.textAlign = "center";
    ctx.value.fillText(i + 1, sp.x, sp.y - 8);
  });
}

function imageToScreen(imgX, imgY) {
  return {
    x: imgX * scale.value + offsetX.value,
    y: imgY * scale.value + offsetY.value,
  };
}

function drawAnnotation(ann, index, isSelected) {
  const category = props.categories.find((c) => c.id === ann.category_id);
  const color = category?.color || "#FF0000";
  const annType = ann.annotation_type || "bbox";

  if (annType === "parallelogram" && ann.p1_x != null) {
    drawParallelogramAnnotation(ann, index, isSelected, color);
  } else {
    // 原有 bbox 绘制
    const imgW = image.value.width;
    const imgH = image.value.height;
    const x = (ann.x_center - ann.width / 2) * imgW;
    const y = (ann.y_center - ann.height / 2) * imgH;
    const w = ann.width * imgW;
    const h = ann.height * imgH;
    const box = { x, y, w, h };
    drawBox(box, color, isSelected);

    // 绘制类别标签
    const screenX = x * scale.value + offsetX.value;
    const screenY = y * scale.value + offsetY.value;
    const labelText = `#${index + 1} ${category?.name || ""}`;
    ctx.value.font = "12px Arial";
    ctx.value.fillStyle = color;
    ctx.value.fillRect(
      screenX,
      screenY - 18,
      ctx.value.measureText(labelText).width + 8,
      18,
    );
    ctx.value.fillStyle = "white";
    ctx.value.fillText(labelText, screenX + 4, screenY - 5);
  }
}

function drawAnnotationWithBox(ann, box, index, isSelected) {
  const category = props.categories.find((c) => c.id === ann.category_id);
  const color = category?.color || "#FF0000";

  drawBox(box, color, isSelected);

  const screenX = box.x * scale.value + offsetX.value;
  const screenY = box.y * scale.value + offsetY.value;
  const labelText = `#${index + 1} ${category?.name || ""}`;
  ctx.value.font = "12px Arial";
  ctx.value.fillStyle = color;
  ctx.value.fillRect(
    screenX,
    screenY - 18,
    ctx.value.measureText(labelText).width + 8,
    18,
  );
  ctx.value.fillStyle = "white";
  ctx.value.fillText(labelText, screenX + 4, screenY - 5);
}

// 绘制平行四边形标注
function drawParallelogramAnnotation(ann, index, isSelected, color) {
  const corners = [
    { x: ann.p1_x, y: ann.p1_y },
    { x: ann.p2_x, y: ann.p2_y },
    { x: ann.p3_x, y: ann.p3_y },
    { x: ann.p4_x, y: ann.p4_y },
  ];

  // 绘制填充
  ctx.value.beginPath();
  const first = imageToScreen(
    corners[0].x * image.value.width,
    corners[0].y * image.value.height,
  );
  ctx.value.moveTo(first.x, first.y);
  for (let i = 1; i < corners.length; i++) {
    const p = imageToScreen(
      corners[i].x * image.value.width,
      corners[i].y * image.value.height,
    );
    ctx.value.lineTo(p.x, p.y);
  }
  ctx.value.closePath();
  ctx.value.fillStyle = color + "20";
  ctx.value.fill();
  ctx.value.strokeStyle = color;
  ctx.value.lineWidth = isSelected ? 3 : 2;
  ctx.value.stroke();

  // 选中时绘制角点手柄
  if (isSelected) {
    corners.forEach((c) => {
      const sp = imageToScreen(
        c.x * image.value.width,
        c.y * image.value.height,
      );
      ctx.value.fillStyle = color;
      ctx.value.fillRect(sp.x - 5, sp.y - 5, 10, 10);
    });
  }

  // 标签
  const screenP = imageToScreen(
    Math.min(corners[0].x, corners[3].x) * image.value.width,
    Math.min(corners[0].y, corners[1].y) * image.value.height,
  );
  const category = props.categories.find((c) => c.id === ann.category_id);
  const labelText = `#${index + 1} ${category?.name || ""}`;
  ctx.value.font = "12px Arial";
  ctx.value.fillStyle = color;
  ctx.value.fillRect(
    screenP.x,
    screenP.y - 18,
    ctx.value.measureText(labelText).width + 8,
    18,
  );
  ctx.value.fillStyle = "white";
  ctx.value.fillText(labelText, screenP.x + 4, screenP.y - 5);
}

function drawBox(box, color, isSelected) {
  const screenX = box.x * scale.value + offsetX.value;
  const screenY = box.y * scale.value + offsetY.value;
  const screenW = box.w * scale.value;
  const screenH = box.h * scale.value;

  ctx.value.strokeStyle = color;
  ctx.value.lineWidth = isSelected ? 3 : 2;
  ctx.value.strokeRect(screenX, screenY, screenW, screenH);

  // 半透明填充
  ctx.value.fillStyle = color + "20";
  ctx.value.fillRect(screenX, screenY, screenW, screenH);

  // 选中时绘制调整手柄
  if (isSelected) {
    const handles = getHandles(screenX, screenY, screenW, screenH);
    ctx.value.fillStyle = color;
    handles.forEach((h) => {
      ctx.value.fillRect(h.x - 4, h.y - 4, 8, 8);
    });
  }
}

function getHandles(x, y, w, h) {
  return [
    { x: x, y: y, cursor: "nw-resize", type: "tl" },
    { x: x + w / 2, y: y, cursor: "n-resize", type: "t" },
    { x: x + w, y: y, cursor: "ne-resize", type: "tr" },
    { x: x + w, y: y + h / 2, cursor: "e-resize", type: "r" },
    { x: x + w, y: y + h, cursor: "se-resize", type: "br" },
    { x: x + w / 2, y: y + h, cursor: "s-resize", type: "b" },
    { x: x, y: y + h, cursor: "sw-resize", type: "bl" },
    { x: x, y: y + h / 2, cursor: "w-resize", type: "l" },
  ];
}

function screenToImage(screenX, screenY) {
  return {
    x: (screenX - offsetX.value) / scale.value,
    y: (screenY - offsetY.value) / scale.value,
  };
}

function handleMouseDown(e) {
  e.preventDefault();

  const rect = canvasRef.value.getBoundingClientRect();
  const screenX = e.clientX - rect.left;
  const screenY = e.clientY - rect.top;

  // 拖动模式或空格键按下时进入平移模式
  if (props.readonly || props.mode === "pan" || spacePressed.value) {
    isPanning.value = true;
    startPoint.value = { x: e.clientX, y: e.clientY };
    canvasRef.value.style.cursor = "grabbing";
    return;
  }

  // 点标注模式（4point / 8point）
  if (
    isPointMode.value &&
    (props.selectedCategory || props.allowDrawWithoutCategory)
  ) {
    const imgPoint = screenToImage(screenX, screenY);
    currentPoints.value.push({ x: imgPoint.x, y: imgPoint.y });
    isAdjustingPoint.value = true;
    draw();
    return;
  }

  // 检查是否点击了调整手柄（bbox模式）
  if (selectedAnnotation.value) {
    const ann = selectedAnnotation.value;
    const annType = ann.annotation_type || "bbox";

    if (annType === "parallelogram" && ann.p1_x != null) {
      // 平行四边形角点拖拽
      const handle = getClickedParallelogramHandle(screenX, screenY, ann);
      if (handle) {
        dragHandle.value = handle;
        isDragging.value = true;
        startPoint.value = screenToImage(screenX, screenY);
        return;
      }
    } else {
      const handle = getClickedHandle(screenX, screenY);
      if (handle) {
        dragHandle.value = handle;
        isDragging.value = true;
        startPoint.value = screenToImage(screenX, screenY);
        const imgW = image.value.width;
        const imgH = image.value.height;
        dragBox.value = {
          x: (ann.x_center - ann.width / 2) * imgW,
          y: (ann.y_center - ann.height / 2) * imgH,
          w: ann.width * imgW,
          h: ann.height * imgH,
        };
        return;
      }
    }
  }

  // 检查是否点击了已有标注（开始拖动移动）
  const clickedAnn = getAnnotationAt(screenX, screenY);
  if (clickedAnn) {
    selectedAnnotation.value = clickedAnn;
    isMoving.value = true;
    startPoint.value = screenToImage(screenX, screenY);
    const ann = clickedAnn;
    const annType = ann.annotation_type || "bbox";

    if (annType === "parallelogram" && ann.p1_x != null) {
      // 平行四边形移动 - 存储所有角点
      dragBox.value = {
        corners: [
          { x: ann.p1_x, y: ann.p1_y },
          { x: ann.p2_x, y: ann.p2_y },
          { x: ann.p3_x, y: ann.p3_y },
          { x: ann.p4_x, y: ann.p4_y },
        ],
      };
    } else {
      const imgW = image.value.width;
      const imgH = image.value.height;
      dragBox.value = {
        x: (ann.x_center - ann.width / 2) * imgW,
        y: (ann.y_center - ann.height / 2) * imgH,
        w: ann.width * imgW,
        h: ann.height * imgH,
      };
    }
    draw();
    return;
  }

  // 开始绘制新框（bbox模式）
  if (props.selectedCategory || props.allowDrawWithoutCategory) {
    selectedAnnotation.value = null;
    isDrawing.value = true;
    const imgPoint = screenToImage(screenX, screenY);
    startPoint.value = imgPoint;
    currentBox.value = { x: imgPoint.x, y: imgPoint.y, w: 0, h: 0 };
  }
}

function handleMouseMove(e) {
  const rect = canvasRef.value.getBoundingClientRect();
  const screenX = e.clientX - rect.left;
  const screenY = e.clientY - rect.top;

  // 拖动调整刚放置的点
  if (isAdjustingPoint.value && currentPoints.value.length > 0) {
    const imgPoint = screenToImage(screenX, screenY);
    currentPoints.value[currentPoints.value.length - 1] = {
      x: imgPoint.x,
      y: imgPoint.y,
    };
    draw();
    return;
  }

  // 平移
  if (isPanning.value) {
    offsetX.value += e.clientX - startPoint.value.x;
    offsetY.value += e.clientY - startPoint.value.y;
    startPoint.value = { x: e.clientX, y: e.clientY };
    draw();
    return;
  }

  // 平行四边形角点拖拽
  if (isDragging.value && selectedAnnotation.value && dragHandle.value) {
    const ann = selectedAnnotation.value;
    const annType = ann.annotation_type || "bbox";
    if (annType === "parallelogram" && dragHandle.value.cornerIndex != null) {
      const imgPoint = screenToImage(screenX, screenY);
      const imgW = image.value.width;
      const imgH = image.value.height;
      // 直接更新角点（实时预览）
      const cornerFields = ["p1", "p2", "p3", "p4"];
      const ci = dragHandle.value.cornerIndex;
      const field = cornerFields[ci];
      selectedAnnotation.value = {
        ...selectedAnnotation.value,
        [field + "_x"]: imgPoint.x / imgW,
        [field + "_y"]: imgPoint.y / imgH,
      };
      draw();
      return;
    }
  }

  // bbox 调整大小
  if (
    isDragging.value &&
    selectedAnnotation.value &&
    dragHandle.value &&
    dragBox.value
  ) {
    const imgPoint = screenToImage(screenX, screenY);
    updateDragBox(dragHandle.value.type, imgPoint);
    draw();
    return;
  }

  // 整体移动
  if (isMoving.value && selectedAnnotation.value && dragBox.value) {
    const ann = selectedAnnotation.value;
    const annType = ann.annotation_type || "bbox";

    if (annType === "parallelogram" && dragBox.value.corners) {
      // 平行四边形移动
      const imgPoint = screenToImage(screenX, screenY);
      const dx = imgPoint.x - startPoint.value.x;
      const dy = imgPoint.y - startPoint.value.y;
      const imgW = image.value.width;
      const imgH = image.value.height;
      const origCorners = dragBox.value.corners;
      const newCorners = origCorners.map((c) => ({
        x: c.x * imgW + dx,
        y: c.y * imgH + dy,
      }));
      // 计算新的 bbox 和角点
      const cornerFields = ["p1", "p2", "p3", "p4"];
      const updates = {};
      newCorners.forEach((c, i) => {
        updates[cornerFields[i] + "_x"] = c.x / imgW;
        updates[cornerFields[i] + "_y"] = c.y / imgH;
      });
      // 也更新外接矩形
      const xs = newCorners.map((c) => c.x);
      const ys = newCorners.map((c) => c.y);
      updates.x_center = (Math.min(...xs) + Math.max(...xs)) / 2 / imgW;
      updates.y_center = (Math.min(...ys) + Math.max(...ys)) / 2 / imgH;
      updates.width = (Math.max(...xs) - Math.min(...xs)) / imgW;
      updates.height = (Math.max(...ys) - Math.min(...ys)) / imgH;
      selectedAnnotation.value = { ...selectedAnnotation.value, ...updates };
      draw();
    } else {
      // bbox 移动
      const imgPoint = screenToImage(screenX, screenY);
      const dx = imgPoint.x - startPoint.value.x;
      const dy = imgPoint.y - startPoint.value.y;

      const imgW = image.value.width;
      const imgH = image.value.height;
      const origX = (ann.x_center - ann.width / 2) * imgW;
      const origY = (ann.y_center - ann.height / 2) * imgH;

      dragBox.value = {
        x: origX + dx,
        y: origY + dy,
        w: dragBox.value.w,
        h: dragBox.value.h,
      };
      draw();
    }
    return;
  }

  // 绘制中
  if (isDrawing.value && currentBox.value) {
    const imgPoint = screenToImage(screenX, screenY);
    currentBox.value.w = imgPoint.x - startPoint.value.x;
    currentBox.value.h = imgPoint.y - startPoint.value.y;
    draw();
  }

  // 更新光标
  updateCursor(screenX, screenY);
}

function handleMouseUp(e) {
  // 松开确认点位置，并检查是否完成
  if (isAdjustingPoint.value) {
    isAdjustingPoint.value = false;
    if (currentPoints.value.length >= maxPoints.value) {
      completePointAnnotation();
    }
    return;
  }

  if (isPanning.value) {
    isPanning.value = false;
    return;
  }

  // 平行四边形角点拖拽完成
  if (isDragging.value && selectedAnnotation.value) {
    const ann = selectedAnnotation.value;
    const annType = ann.annotation_type || "bbox";
    if (annType === "parallelogram" && dragHandle.value?.cornerIndex != null) {
      // emit update with new corner positions
      const cornerFields = ["p1", "p2", "p3", "p4"];
      const ci = dragHandle.value.cornerIndex;
      const field = cornerFields[ci];
      emit("update", selectedAnnotation.value.id, {
        [field + "_x"]: selectedAnnotation.value[field + "_x"],
        [field + "_y"]: selectedAnnotation.value[field + "_y"],
      });
      isDragging.value = false;
      dragHandle.value = null;
      return;
    }
  }

  if (isDragging.value || isMoving.value) {
    const wasMoving = isMoving.value;
    isDragging.value = false;
    isMoving.value = false;
    dragHandle.value = null;

    const ann = selectedAnnotation.value;
    const annType = ann?.annotation_type || "bbox";

    if (
      ann &&
      annType === "parallelogram" &&
      wasMoving &&
      dragBox.value?.corners
    ) {
      // 平行四边形移动完成 - emit update
      const cornerFields = ["p1", "p2", "p3", "p4"];
      const updates = {};
      cornerFields.forEach((f) => {
        updates[f + "_x"] = ann[f + "_x"];
        updates[f + "_y"] = ann[f + "_y"];
      });
      updates.x_center = ann.x_center;
      updates.y_center = ann.y_center;
      updates.width = ann.width;
      updates.height = ann.height;
      emit("update", ann.id, updates);
    } else if (selectedAnnotation.value && dragBox.value && image.value) {
      // bbox update
      const imgW = image.value.width;
      const imgH = image.value.height;
      const box = dragBox.value;
      const newData = {
        x_center: (box.x + box.w / 2) / imgW,
        y_center: (box.y + box.h / 2) / imgH,
        width: box.w / imgW,
        height: box.h / imgH,
      };
      emit("update", selectedAnnotation.value.id, newData);
      selectedAnnotation.value = {
        ...selectedAnnotation.value,
        ...newData,
      };
    }
    dragBox.value = null;
    return;
  }

  if (isDrawing.value && currentBox.value) {
    isDrawing.value = false;

    // 规范化框坐标
    let { x, y, w, h } = currentBox.value;
    if (w < 0) {
      x += w;
      w = -w;
    }
    if (h < 0) {
      y += h;
      h = -h;
    }

    // 最小尺寸检查
    if (w > 5 && h > 5 && image.value) {
      const imgW = image.value.width;
      const imgH = image.value.height;

      const annotation = {
        x_center: (x + w / 2) / imgW,
        y_center: (y + h / 2) / imgH,
        width: w / imgW,
        height: h / imgH,
      };

      // 只在预选类别模式下设置 category_id
      if (props.selectedCategory) {
        annotation.category_id = props.selectedCategory.id;
      }

      emit("add", annotation);
    }

    currentBox.value = null;
    draw();
  }
}

// 完成点标注（4点/8点模式）
function completePointAnnotation() {
  const points = currentPoints.value;
  if (!image.value || points.length < maxPoints.value) return;

  const imgW = image.value.width;
  const imgH = image.value.height;

  let corners = [];

  if (props.shapeMode === "4point") {
    // 4个点直接就是4个角
    corners = points.map((p) => ({
      x: p.x / imgW,
      y: p.y / imgH,
    }));
  } else if (props.shapeMode === "8point") {
    // 8个点：每2个点定义一条边，计算相邻边的交点得到4个角
    // edges: (0,1), (2,3), (4,5), (6,7)
    corners = [
      lineIntersection(points[0], points[1], points[6], points[7], imgW, imgH), // edge1 ∩ edge4
      lineIntersection(points[0], points[1], points[2], points[3], imgW, imgH), // edge1 ∩ edge2
      lineIntersection(points[2], points[3], points[4], points[5], imgW, imgH), // edge2 ∩ edge3
      lineIntersection(points[4], points[5], points[6], points[7], imgW, imgH), // edge3 ∩ edge4
    ];
  }

  // 检查交点有效性
  if (corners.some((c) => c == null || isNaN(c.x) || isNaN(c.y))) {
    // 无效交点（平行线等），直接用外接矩形作为 bbox
    const xs = points.map((p) => p.x);
    const ys = points.map((p) => p.y);
    const minX = Math.min(...xs),
      maxX = Math.max(...xs);
    const minY = Math.min(...ys),
      maxY = Math.max(...ys);
    const annotation = {
      annotation_type: "bbox",
      x_center: (minX + maxX) / 2 / imgW,
      y_center: (minY + maxY) / 2 / imgH,
      width: (maxX - minX) / imgW,
      height: (maxY - minY) / imgH,
    };
    if (props.selectedCategory) {
      annotation.category_id = props.selectedCategory.id;
    }
    emit("add", annotation);
    currentPoints.value = [];
    draw();
    return;
  }

  // 计算外接矩形
  const xs = corners.map((c) => c.x);
  const ys = corners.map((c) => c.y);
  const bbox = {
    x_center: (Math.min(...xs) + Math.max(...xs)) / 2,
    y_center: (Math.min(...ys) + Math.max(...ys)) / 2,
    width: Math.max(...xs) - Math.min(...xs),
    height: Math.max(...ys) - Math.min(...ys),
  };

  const annotation = {
    annotation_type: "parallelogram",
    x_center: bbox.x_center,
    y_center: bbox.y_center,
    width: bbox.width,
    height: bbox.height,
    p1_x: corners[0].x,
    p1_y: corners[0].y,
    p2_x: corners[1].x,
    p2_y: corners[1].y,
    p3_x: corners[2].x,
    p3_y: corners[2].y,
    p4_x: corners[3].x,
    p4_y: corners[3].y,
  };

  if (props.selectedCategory) {
    annotation.category_id = props.selectedCategory.id;
  }

  emit("add", annotation);
  currentPoints.value = [];
  draw();
}

// 计算两条直线的交点（归一化坐标）
function handleWheel(e) {
  e.preventDefault();

  const rect = canvasRef.value.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;

  const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
  const newScale = Math.min(Math.max(scale.value * zoomFactor, 0.1), 10);

  // 以鼠标位置为中心缩放
  const imgPoint = screenToImage(mouseX, mouseY);
  scale.value = newScale;
  offsetX.value = mouseX - imgPoint.x * newScale;
  offsetY.value = mouseY - imgPoint.y * newScale;

  emit("zoom-change", scale.value);
  draw();
}

function handleKeyDown(e) {
  if(document.querySelector('[role="dialog"],[role="alertdialog"],[role="listbox"],[role="menu"]')) return;
  if (
    e.target.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)
  )
    return;
  if (e.code === "Space") {
    e.preventDefault();
    spacePressed.value = true;
    canvasRef.value.style.cursor = "grab";
  }

  if (!props.readonly && (e.key === "Delete" || e.key === "Backspace")) {
    if (selectedAnnotation.value) {
      emit("delete", selectedAnnotation.value.id);
      selectedAnnotation.value = null;
      draw();
    } else if (isPointMode.value && currentPoints.value.length > 0) {
      // 删除最后一个点
      currentPoints.value.pop();
      draw();
    }
  }

  // Escape 取消当前点标注
  if (
    e.key === "Escape" &&
    isPointMode.value &&
    currentPoints.value.length > 0
  ) {
    currentPoints.value = [];
    draw();
  }
}

function handleKeyUp(e) {
  if (e.code === "Space") {
    spacePressed.value = false;
    canvasRef.value.style.cursor = "crosshair";
  }
}

function getAnnotationAt(screenX, screenY) {
  if (!image.value) return null;

  const imgPoint = screenToImage(screenX, screenY);
  const imgW = image.value.width;
  const imgH = image.value.height;

  for (let i = props.annotations.length - 1; i >= 0; i--) {
    const ann = props.annotations[i];
    if (ann.is_readonly) continue;
    const annType = ann.annotation_type || "bbox";

    if (annType === "parallelogram" && ann.p1_x != null) {
      // 点在平行四边形内判断（射线法）
      const corners = [
        { x: ann.p1_x * imgW, y: ann.p1_y * imgH },
        { x: ann.p2_x * imgW, y: ann.p2_y * imgH },
        { x: ann.p3_x * imgW, y: ann.p3_y * imgH },
        { x: ann.p4_x * imgW, y: ann.p4_y * imgH },
      ];
      if (pointInPolygon(imgPoint, corners)) return ann;
    } else {
      // bbox 检测
      const x = (ann.x_center - ann.width / 2) * imgW;
      const y = (ann.y_center - ann.height / 2) * imgH;
      const w = ann.width * imgW;
      const h = ann.height * imgH;
      if (
        imgPoint.x >= x &&
        imgPoint.x <= x + w &&
        imgPoint.y >= y &&
        imgPoint.y <= y + h
      ) {
        return ann;
      }
    }
  }
  return null;
}

// 射线法判断点是否在多边形内
// 获取平行四边形的角点手柄
function getClickedParallelogramHandle(screenX, screenY, ann) {
  if (!image.value) return null;

  const imgW = image.value.width;
  const imgH = image.value.height;
  const corners = [
    { x: ann.p1_x, y: ann.p1_y },
    { x: ann.p2_x, y: ann.p2_y },
    { x: ann.p3_x, y: ann.p3_y },
    { x: ann.p4_x, y: ann.p4_y },
  ];

  for (let i = 0; i < corners.length; i++) {
    const sp = imageToScreen(corners[i].x * imgW, corners[i].y * imgH);
    if (Math.abs(screenX - sp.x) < 10 && Math.abs(screenY - sp.y) < 10) {
      return { cornerIndex: i };
    }
  }
  return null;
}

function getClickedHandle(screenX, screenY) {
  if (!selectedAnnotation.value || !image.value) return null;

  const ann = selectedAnnotation.value;
  const imgW = image.value.width;
  const imgH = image.value.height;

  const x = (ann.x_center - ann.width / 2) * imgW;
  const y = (ann.y_center - ann.height / 2) * imgH;
  const w = ann.width * imgW;
  const h = ann.height * imgH;

  const handles = getHandles(
    x * scale.value + offsetX.value,
    y * scale.value + offsetY.value,
    w * scale.value,
    h * scale.value,
  );

  for (const handle of handles) {
    if (Math.abs(screenX - handle.x) < 8 && Math.abs(screenY - handle.y) < 8) {
      return handle;
    }
  }
  return null;
}

function updateDragBox(handleType, imgPoint) {
  if (!dragBox.value) return;

  let x1 = dragBox.value.x;
  let y1 = dragBox.value.y;
  let x2 = dragBox.value.x + dragBox.value.w;
  let y2 = dragBox.value.y + dragBox.value.h;

  switch (handleType) {
    case "tl":
      x1 = imgPoint.x;
      y1 = imgPoint.y;
      break;
    case "t":
      y1 = imgPoint.y;
      break;
    case "tr":
      x2 = imgPoint.x;
      y1 = imgPoint.y;
      break;
    case "r":
      x2 = imgPoint.x;
      break;
    case "br":
      x2 = imgPoint.x;
      y2 = imgPoint.y;
      break;
    case "b":
      y2 = imgPoint.y;
      break;
    case "bl":
      x1 = imgPoint.x;
      y2 = imgPoint.y;
      break;
    case "l":
      x1 = imgPoint.x;
      break;
  }

  // 确保最小尺寸
  if (x2 - x1 < 10) x2 = x1 + 10;
  if (y2 - y1 < 10) y2 = y1 + 10;

  dragBox.value = {
    x: x1,
    y: y1,
    w: x2 - x1,
    h: y2 - y1,
  };
}

function updateCursor(screenX, screenY) {
  // 拖动模式
  if (props.mode === "pan") {
    canvasRef.value.style.cursor = isPanning.value ? "grabbing" : "grab";
    return;
  }

  if (spacePressed.value) {
    canvasRef.value.style.cursor = isPanning.value ? "grabbing" : "grab";
    return;
  }

  if (selectedAnnotation.value) {
    const ann = selectedAnnotation.value;
    const annType = ann.annotation_type || "bbox";

    if (annType === "parallelogram" && ann.p1_x != null) {
      const handle = getClickedParallelogramHandle(screenX, screenY, ann);
      if (handle) {
        canvasRef.value.style.cursor = "move";
        return;
      }
    } else {
      const handle = getClickedHandle(screenX, screenY);
      if (handle) {
        canvasRef.value.style.cursor = handle.cursor;
        return;
      }
    }
  }

  const ann = getAnnotationAt(screenX, screenY);
  canvasRef.value.style.cursor = ann ? "move" : "crosshair";
}

// 暴露方法供外部调用
function selectAnnotation(id) {
  const ann = props.annotations.find((a) => a.id === id && !a.is_readonly);
  if (ann) {
    selectedAnnotation.value = ann;
    draw();
  }
}
function zoomBy(factor) {
  scale.value = Math.max(0.1, Math.min(10, scale.value * factor));
  draw();
  emit("zoom-change", scale.value);
}

defineExpose({
  zoomBy,
  fitToContainer,
  selectAnnotation,
  scale,
});
</script>

<template>
  <div ref="containerRef" class="canvas-wrapper">
    <canvas
      ref="canvasRef"
      @mousedown="handleMouseDown"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @mouseleave="handleMouseUp"
      @wheel="handleWheel"
    />
  </div>
</template>

<style scoped>
.canvas-wrapper {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

canvas {
  display: block;
  cursor: crosshair;
}
</style>
