<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from "vue";
import {
  useRoute,
  useRouter,
  onBeforeRouteLeave,
  onBeforeRouteUpdate,
} from "vue-router";
import { useAnnotationStore } from "../stores/annotation";
import { useShortcutsStore } from "../stores/shortcuts";
import { usePreannotationReviewStore } from "../stores/preannotationReview";
import { message, messageBox } from "../shared/ui/feedback";
import AnnotationCanvas from "../components/AnnotationCanvas.vue";
import CategorySelectionPopup from "../components/CategorySelectionPopup.vue";
import PreannotationTrace from "./PreannotationTrace.vue";
import api from "../utils/api";
import { createImagePrefetcher } from "../utils/imagePrefetch";
import {
  eventShortcut,
  categoryShortcutConflict,
  reservedCategoryKeys,
} from "../features/annotation/domain/shortcuts";

const upcomingImages = createImagePrefetcher();
const upcomingFrames = ref([]),
  traceOpen = ref(false),
  traceContext = ref(null),
  inspectorOpen = ref(false);
const route = useRoute();
const router = useRouter();
const store = useAnnotationStore();
const shortcutsStore = useShortcutsStore();
const review = usePreannotationReviewStore();

const datasetId = computed(() => parseInt(route.params.datasetId));
const progress = ref(null);
const showHelp = ref(false);
const showRawOutput = ref(false);
const showShortcutSettings = ref(false);
const editingShortcut = ref(null);
const editingCategoryShortcut = ref(null); // 正在编辑快捷键的类别ID

// 模式切换（默认拖动模式）
const canvasMode = ref("pan"); // 'annotate' | 'pan'
const zoomLevel = ref(1);
const canvasRef = ref(null);

// RC2026-wulin 模式相关
const pendingAnnotation = ref(null); // 等待类别选择的标注
const showCategoryPopup = ref(false); // 类别选择弹窗
const shapeMode = ref("bbox"); // 'bbox' | '4point' | '8point'

const source = ref("manual");
const batches = ref([]);
const workspaceLoading = ref(true),
  actionBusy = ref(false),
  contextError = ref(false);
const guardPrompt = ref(false);
const loadedDatasetId = ref(null),
  manualSnapshot = ref("[]"),
  lastReviewTaskId = ref(null);
let loadedContextKey = "",
  contextGeneration = 0,
  disposed = false;
const isReviewMode = computed(() => source.value === "preannotation");
const currentImage = computed(() =>
  isReviewMode.value ? review.image : store.currentImage,
);
const workAnnotations = computed(() =>
  isReviewMode.value ? review.activeCandidates : store.annotations,
);
const canvasAnnotations = computed(() =>
  isReviewMode.value ? review.canvasAnnotations : store.annotations,
);
const canUndo = computed(() =>
  isReviewMode.value ? review.canUndo : store.canUndo,
);
const canRedo = computed(() =>
  isReviewMode.value ? review.canRedo : store.canRedo,
);
const canPrevious = computed(() =>
  isReviewMode.value ? !!review.previousId : store.canGoPrevious,
);
const canNext = computed(() =>
  isReviewMode.value
    ? !!review.nextId
    : !(store.isInHistory && !store.canGoNext),
);
const imageLoading = computed(
  () =>
    workspaceLoading.value ||
    (isReviewMode.value ? review.loading : store.isLoading),
);
const editable = computed(
  () =>
    !imageLoading.value &&
    !actionBusy.value &&
    !guardPrompt.value &&
    (isReviewMode.value
      ? review.editable && !review.busy
      : !!currentImage.value),
);
const dirty = computed(() =>
  isReviewMode.value
    ? review.dirty
    : JSON.stringify(store.annotations) !== manualSnapshot.value,
);
const pendingReviews = computed(() =>
  review.task
    ? (review.task.counts.succeeded || 0) -
      review.task.approved -
      review.task.rejected
    : 0,
);
const reviewedCount = computed(() =>
  review.task ? review.task.approved + review.task.rejected : 0,
);
const reviewProgress = computed(() =>
  review.task?.counts.succeeded
    ? Math.round((reviewedCount.value / review.task.counts.succeeded) * 100)
    : 0,
);
const statusLabels = {
  unreviewed: "待审核",
  draft: "审核草稿",
  approved: "已通过",
  rejected: "已驳回",
};
const statusText = computed(() =>
  isReviewMode.value
    ? statusLabels[review.item?.review_status] ||
      (imageLoading.value
        ? "加载中"
        : contextError.value
          ? "加载失败"
          : "当前队列为空")
    : "人工标注",
);
const emptyDescription = computed(() =>
  contextError.value
    ? "加载失败，请重试"
    : isReviewMode.value
      ? ["queued", "running", "cancelling"].includes(review.task?.status)
        ? "批次仍在后台处理，暂无符合条件的结果，可稍后刷新"
        : pendingReviews.value === 0 && review.task?.counts.succeeded
          ? "当前批次的待审核图片已处理完毕"
          : "暂无符合筛选条件的预标注结果"
      : "没有更多图片需要标注",
);

function positive(value) {
  const n = Number(value);
  return Number.isInteger(n) && n > 0 ? n : undefined;
}
function contextKey(to) {
  return JSON.stringify([
    String(to.params.datasetId),
    to.query.source || "auto",
    String(to.query.task || ""),
    String(to.query.image || ""),
    to.query.review_status || "pending",
    to.query.has_candidates || "",
    to.query.execution_status || "succeeded",
  ]);
}
function contextQuery(extra = {}) {
  const query = { ...route.query, source: source.value, ...extra };
  if (isReviewMode.value) {
    query.task = review.task?.id;
    query.image = currentImage.value?.id;
    Object.assign(query, review.queue, extra);
  } else {
    for (const key of [
      "task",
      "review_status",
      "has_candidates",
      "execution_status",
    ])
      delete query[key];
    query.image = currentImage.value?.id;
    Object.assign(query, extra);
  }
  for (const key of Object.keys(query))
    if (query[key] === undefined || query[key] === null || query[key] === "")
      delete query[key];
  return query;
}
async function syncLocation() {
  const target = {
    name: "Annotation",
    params: { datasetId: datasetId.value },
    query: contextQuery(),
  };
  loadedContextKey = contextKey({ params: target.params, query: target.query });
  await router.replace(target);
}
function preferredBatch() {
  return batches.value.find((t) => !t.is_sample) || batches.value[0];
}
async function loadData(to = route) {
  const token = ++contextGeneration;
  workspaceLoading.value = true;
  contextError.value = false;
  try {
    const id = positive(to.params.datasetId);
    if (!id) throw new Error("数据集参数不正确");
    if (loadedDatasetId.value !== id) {
      store.reset();
      review.reset();
      await store.loadDatasetConfig(id);
      await store.loadCategories(id);
      const response = await api.get(`/datasets/${id}/preannotation-tasks`, {
        params: { page_size: 100 },
      });
      if (disposed || token !== contextGeneration) return;
      batches.value = response.data.items;
      // 连续抽样很多次时，也要找到最近一次全量批次。
      let page = 1;
      while (
        !batches.value.some((t) => !t.is_sample) &&
        batches.value.length < response.data.total
      ) {
        const older = await api.get(`/datasets/${id}/preannotation-tasks`, {
          params: { page_size: 100, page: ++page },
        });
        if (disposed || token !== contextGeneration) return;
        if (!older.data.items.length) break;
        batches.value.push(...older.data.items);
      }
      loadedDatasetId.value = id;
    }
    const selectedId = positive(to.query.task);
    const batch = selectedId || preferredBatch()?.id;
    const useReview = to.query.source !== "manual" && !!batch;
    source.value = useReview ? "preannotation" : "manual";
    if (useReview) {
      await review.load(id, batch, positive(to.query.image), {
        review_status: [
          "pending",
          "unreviewed",
          "draft",
          "approved",
          "rejected",
          "all",
        ].includes(to.query.review_status)
          ? to.query.review_status
          : "pending",
        execution_status: to.query.execution_status || "succeeded",
        has_candidates: to.query.has_candidates || "",
      });
      if (disposed || token !== contextGeneration) return;
      if (!batches.value.some((t) => t.id === review.task.id))
        batches.value.unshift(review.task);
      lastReviewTaskId.value = review.task.id;
      canvasMode.value = "annotate";
    } else {
      review.reset();
      if (positive(to.query.image))
        await store.fetchImage(positive(to.query.image));
      else await store.fetchNextImage(id);
      if (disposed || token !== contextGeneration) return;
      if (store.currentImage && store.currentImage.dataset_id !== id) {
        store.currentImage = null;
        store.annotations = [];
        throw new Error("图片不属于当前数据集");
      }
      manualSnapshot.value = JSON.stringify(store.annotations);
      canvasMode.value = "pan";
    }
    shapeMode.value = "bbox";
    pendingAnnotation.value = null;
    showCategoryPopup.value = false;
    await loadProgress();
    if (!disposed && token === contextGeneration) await syncLocation();
  } catch (error) {
    if (!disposed && token === contextGeneration) {
      contextError.value = true;
      message.error(error.response?.data?.detail || "加载标注工作台失败");
    }
  } finally {
    if (token === contextGeneration) workspaceLoading.value = false;
  }
}
async function ensureCanLeave() {
  if (guardPrompt.value) return false;
  if (!dirty.value) return true;
  guardPrompt.value = true;
  try {
    await messageBox.confirm(
      isReviewMode.value
        ? "保存本图审核草稿后切换？草稿不会计为审核通过。"
        : "保存当前人工标注后切换？",
      "有未保存的修改",
      {
        confirmButtonText: "保存并切换",
        cancelButtonText: "放弃修改",
        distinguishCancelAndClose: true,
        type: "warning",
      },
    );
    if (isReviewMode.value) return await review.saveDraft();
    await store.saveAnnotations(false);
    manualSnapshot.value = JSON.stringify(store.annotations);
    return true;
  } catch (reason) {
    return reason === "cancel";
  } finally {
    guardPrompt.value = false;
  }
}
async function refreshResults() {
  if (await ensureCanLeave()) await loadData();
}
onBeforeRouteLeave(() =>
  actionBusy.value || review.busy ? false : ensureCanLeave(),
);
onBeforeRouteUpdate(async (to) =>
  contextKey(to) === loadedContextKey ? true : await ensureCanLeave(),
);
watch(
  () => contextKey(route),
  (key) => {
    if (key !== loadedContextKey && !disposed) loadData(route);
  },
);
// Fetch only the next few records in the active review queue, without assigning them.
watch(
  () =>
    JSON.stringify([
      currentImage.value?.id,
      datasetId.value,
      source.value,
      review.task?.id,
      review.queue,
    ]),
  async (_, __, onCleanup) => {
    const imageId = currentImage.value?.id;
    if (!imageId) {
      upcomingImages.clear();
      upcomingFrames.value = [];
      return;
    }
    let cancelled = false;
    onCleanup(() => {
      cancelled = true;
    });
    const params = { after_id: imageId, page_size: 3 };
    if (isReviewMode.value) {
      params.task_id = review.task?.id;
      params.execution_status = review.queue.execution_status;
      if (review.queue.review_status !== "all")
        params.review_status = review.queue.review_status;
      if (review.queue.has_candidates !== "")
        params.has_candidates = review.queue.has_candidates;
    }
    try {
      const response = await api.get(`/datasets/${datasetId.value}/images`, {
        params,
      });
      if (!cancelled && !disposed) {
        upcomingFrames.value = response.data.items;
        upcomingImages.preload(response.data.items.map((image) => image.id));
      }
    } catch {
      /* Prefetch failure must not block the current image. */
    }
  },
);
function beforeUnload(event) {
  if (dirty.value) {
    event.preventDefault();
    event.returnValue = "";
  }
}
onMounted(async () => {
  window.addEventListener("keydown", handleKeydown);
  window.addEventListener("beforeunload", beforeUnload);
  await loadData();
});
onUnmounted(() => {
  disposed = true;
  contextGeneration++;
  upcomingImages.clear();
  window.removeEventListener("keydown", handleKeydown);
  window.removeEventListener("beforeunload", beforeUnload);
  review.reset();
  store.reset();
});
async function changeSource(value) {
  if (actionBusy.value || workspaceLoading.value) return;
  const query = { source: value };
  if (value === "preannotation")
    query.task = lastReviewTaskId.value || preferredBatch()?.id;
  else query.image = currentImage.value?.id;
  await router.push({
    name: "Annotation",
    params: { datasetId: datasetId.value },
    query,
  });
}
async function changeBatch(value) {
  await router.push({
    name: "Annotation",
    params: { datasetId: datasetId.value },
    query: { source: "preannotation", task: value, review_status: "pending" },
  });
}
async function changeReviewFilter(key, value) {
  await router.push({
    name: "Annotation",
    params: { datasetId: datasetId.value },
    query: { ...contextQuery({ [key]: value }), image: undefined },
  });
}
async function reviewNavigate(direction) {
  if (!currentImage.value || review.busy || actionBusy.value) return;
  try {
    if (review.dirty && !(await review.saveDraft())) return;
    await review.refreshNavigation(datasetId.value);
    const id = direction === "previous" ? review.previousId : review.nextId;
    if (!id) return message.info("当前筛选队列中没有更多图片");
    await router.push({
      name: "Annotation",
      params: { datasetId: datasetId.value },
      query: contextQuery({ image: id }),
    });
  } catch {
    /* 拦截器显示错误，保留当前图片和草稿 */
  }
}
async function approveReview(action = "approve") {
  if (!editable.value || actionBusy.value || showCategoryPopup.value) return;
  if (action === "empty" && review.activeCandidates.length)
    return message.warning("请先删除全部候选框，再确认无目标");
  if (action === "reject") {
    guardPrompt.value = true;
    try {
      await messageBox.confirm(
        "驳回本批次对这张图的结果？已有正式标注会保留。",
        "驳回预标注结果",
        { type: "warning" },
      );
    } catch {
      return;
    } finally {
      guardPrompt.value = false;
    }
  }
  actionBusy.value = true;
  try {
    if (!(await review.review(action))) return;
    message.success(
      action === "reject" ? "已驳回本图结果" : "审核通过，正式标注已保存",
    );
    await review.refreshNavigation(datasetId.value);
    const next = review.nextId;
    if (next)
      await router.push({
        name: "Annotation",
        params: { datasetId: datasetId.value },
        query: contextQuery({ image: next }),
      });
    else {
      await review.load(datasetId.value, review.task.id, undefined, {
        ...review.queue,
      });
      await syncLocation();
      if (!review.image) message.info("当前审核队列已处理完毕");
    }
    await loadProgress();
  } catch {
    /* 保留可恢复状态，不把错误当作审核通过 */
  } finally {
    actionBusy.value = false;
  }
}
function undo() {
  if (editable.value) isReviewMode.value ? review.undo() : store.undo();
}
function redo() {
  if (editable.value) isReviewMode.value ? review.redo() : store.redo();
}
function handleAnnotationUpdate(id, changes) {
  if (editable.value)
    isReviewMode.value
      ? review.update(id, changes)
      : store.updateAnnotation(id, changes);
}
function handleAnnotationDelete(id) {
  if (editable.value)
    isReviewMode.value ? review.remove(id) : store.removeAnnotation(id);
}
function addWithCategory(ann, id) {
  if (isReviewMode.value) review.add(ann, id);
  else store.addAnnotationWithCategory(ann, id);
}
function changeCandidateCategory(ann, id) {
  review.update(review.canvasId(ann), { category_id: id });
}
function selectBox(ann) {
  canvasMode.value = "annotate";
  canvasRef.value?.selectAnnotation(
    isReviewMode.value ? review.canvasId(ann) : ann.id,
  );
}
function showTaskManager() {
  router.push({
    name: "Preannotation",
    params: { datasetId: datasetId.value },
    query: {
      task: review.task?.id,
      review_status: isReviewMode.value
        ? review.queue.review_status === "all"
          ? ""
          : review.queue.review_status
        : "",
      has_candidates: review.queue.has_candidates,
      page: route.query.returnPage || 1,
    },
  });
}
function showInferenceTrace() {
  if (review.task && currentImage.value) {
    traceContext.value = {
      datasetId: datasetId.value,
      taskId: review.task.id,
      imageId: currentImage.value.id,
    };
    traceOpen.value = true;
  }
}

async function loadProgress() {
  try {
    const response = await api.get(
      `/images/dataset/${datasetId.value}/progress`,
    );
    progress.value = response.data;
  } catch (error) {
    console.error("Failed to load progress", error);
  }
}

async function handleSave() {
  if (isReviewMode.value) {
    if (!editable.value) return;
    try {
      if (await review.saveDraft())
        message.success("审核草稿已保存；尚未审核通过");
    } catch {}
    return;
  }
  try {
    const savedCount = await store.saveAnnotations(false);
    message.success(`保存成功 (${savedCount} 个标注)`);
    // 如果在历史模式，不自动跳转下一张
    if (!store.isInHistory) {
      await store.fetchNextImage(datasetId.value);
      // 进入下一张图片后重置为拖动模式
      canvasMode.value = "pan";
    }
    manualSnapshot.value = JSON.stringify(store.annotations);
    await syncLocation();
    await loadProgress();
  } catch (error) {
    console.error("Save failed:", error);
    message.error(
      "保存失败: " + (error.response?.data?.detail || error.message),
    );
  }
}

async function handleSkip() {
  if (isReviewMode.value) return approveReview("empty");
  try {
    await store.saveAnnotations(true);
    message.info("已标记为未见");
    await store.fetchNextImage(datasetId.value);
    await loadProgress();
    // 进入下一张图片后重置为拖动模式
    canvasMode.value = "pan";
    manualSnapshot.value = JSON.stringify(store.annotations);
    await syncLocation();
  } catch (error) {
    message.error("操作失败");
  }
}

async function handlePrevious() {
  if (isReviewMode.value) return reviewNavigate("previous");
  try {
    // 如果已经在历史模式中，先保存当前标注再返回
    if (store.isInHistory) {
      const savedCount = await store.saveAnnotations(false);
      message.success(`保存成功 (${savedCount} 个标注)`);
    }
    await store.goToPreviousImage();
    manualSnapshot.value = JSON.stringify(store.annotations);
    await syncLocation();
  } catch (error) {
    console.error("Save or navigate failed:", error);
    message.error(
      "操作失败: " + (error.response?.data?.detail || error.message),
    );
  }
}

async function handleNext() {
  if (isReviewMode.value) return reviewNavigate("next");
  if (store.isInHistory) {
    // 在历史模式中，先保存当前标注，再前往下一张
    try {
      const savedCount = await store.saveAnnotations(false);
      message.success(`保存成功 (${savedCount} 个标注)`);
      await store.goToNextImage();
      manualSnapshot.value = JSON.stringify(store.annotations);
      await syncLocation();
    } catch (error) {
      console.error("Save or navigate failed:", error);
      message.error(
        "操作失败: " + (error.response?.data?.detail || error.message),
      );
    }
  } else {
    // 正常流程，继续获取新图片
    await handleSaveAndNext();
  }
}

async function handleSaveAndNext() {
  try {
    await store.saveAnnotations(false);
    message.success("保存成功");
    store.exitHistoryMode();
    await store.fetchNextImage(datasetId.value);
    await loadProgress();
    // 进入下一张图片后重置为拖动模式
    canvasMode.value = "pan";
    manualSnapshot.value = JSON.stringify(store.annotations);
    await syncLocation();
  } catch (error) {
    message.error("保存失败");
  }
}

function handleKeydown(e) {
  if (
    e.target.closest(
      '[role="dialog"],[role="alertdialog"],[role="listbox"],[role="menu"],[data-reka-popper-content-wrapper]',
    )
  )
    return;
  // 如果类别选择弹窗打开，不处理全局快捷键
  if (
    traceOpen.value ||
    showCategoryPopup.value ||
    guardPrompt.value ||
    showRawOutput.value ||
    showHelp.value ||
    showShortcutSettings.value
  )
    return;

  // 忽略输入框中的按键
  if (
    ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName) ||
    e.target.isContentEditable
  ) {
    return;
  }

  // 正在编辑类别快捷键时，交给对应的处理器
  if (editingCategoryShortcut.value) {
    return;
  }

  if (isReviewMode.value && (e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    approveReview();
    return;
  }
  // 使用自定义快捷键
  if (shortcutsStore.matchShortcut(e, "save")) {
    e.preventDefault();
    handleSave();
    return;
  }

  if (shortcutsStore.matchShortcut(e, "skip")) {
    handleSkip();
    return;
  }

  if (shortcutsStore.matchShortcut(e, "undo")) {
    e.preventDefault();
    undo();
    return;
  }

  if (shortcutsStore.matchShortcut(e, "redo")) {
    e.preventDefault();
    redo();
    return;
  }

  if (shortcutsStore.matchShortcut(e, "help")) {
    showHelp.value = !showHelp.value;
    return;
  }

  const key = e.key.toLowerCase();

  if (key === "escape") {
    showHelp.value = false;
    showShortcutSettings.value = false;
    return;
  }

  // 模式切换快捷键
  if (key === "v" && !e.ctrlKey && !e.metaKey && !e.altKey) {
    canvasMode.value = "annotate";
    return;
  }
  if (key === "h" && !e.ctrlKey && !e.metaKey && !e.altKey) {
    canvasMode.value = "pan";
    return;
  }

  // 数字或字母快捷键选择类别
  const selected = store.selectCategoryByKey(eventShortcut(e));
  if (selected) {
    canvasMode.value = "annotate";
  }
}

// 处理标注添加事件
function handleAnnotationAdd(annotation) {
  if (!editable.value) return;
  const category =
    store.selectedCategory ||
    (store.categories.length === 1 ? store.categories[0] : null);
  if (!category) {
    // 未选择类别：暂存标注，弹出类别选择弹窗
    pendingAnnotation.value = annotation;
    showCategoryPopup.value = true;
  } else {
    // 已选择类别：直接添加
    addWithCategory(annotation, category.id);
  }
}

// 类别选择弹窗：选中类别
function handleCategorySelected(category) {
  if (pendingAnnotation.value) {
    addWithCategory(pendingAnnotation.value, category.id);
    pendingAnnotation.value = null;
  }
  showCategoryPopup.value = false;
}

// 类别选择弹窗：取消
function handleCategoryPopupCancel() {
  pendingAnnotation.value = null;
  showCategoryPopup.value = false;
}

// 快捷键设置相关
function startEditShortcut(action) {
  editingShortcut.value = action;
}

function handleShortcutKeydown(e) {
  e.preventDefault();
  if (!editingShortcut.value) return;

  if (e.key === "Escape") {
    editingShortcut.value = null;
    return;
  }

  const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  shortcutsStore.updateShortcut(editingShortcut.value, {
    key,
    ctrl: e.ctrlKey || e.metaKey,
    shift: e.shiftKey,
  });
  editingShortcut.value = null;
  message.success("快捷键已更新");
}

function resetShortcuts() {
  shortcutsStore.resetToDefault();
  message.success("快捷键已重置为默认");
}

function selectCategory(category) {
  // 如果正在编辑快捷键，不选择类别
  if (editingCategoryShortcut.value) return;
  store.selectedCategory = category;
  canvasMode.value = "annotate";
}

function startEditCategoryShortcut(category, e) {
  e.stopPropagation();
  editingCategoryShortcut.value = category.id;
}

function handleCategoryShortcutKeydown(category, e) {
  e.preventDefault();
  e.stopPropagation();

  if (e.key === "Escape") {
    editingCategoryShortcut.value = null;
    return;
  }

  // 只接受单个字符或数字
  if (e.key.length === 1) {
    const newKey = eventShortcut(e);
    if (!newKey || reservedCategoryKeys.includes(newKey))
      return message.warning("该快捷键与工作台操作冲突");
    // 检查是否与其他类别快捷键冲突
    const conflict = categoryShortcutConflict(store.categories, category.id, [
      newKey,
    ]);
    if (conflict) {
      message.warning(`快捷键 "${newKey}" 已被 "${conflict.name}" 使用`);
      return;
    }

    // 更新快捷键
    updateCategoryShortcut(category.id, newKey);
  }
}

async function updateCategoryShortcut(categoryId, shortcutKey) {
  try {
    await api.put(`/categories/${categoryId}`, { shortcut_key: shortcutKey });
    // 更新本地数据
    const cat = store.categories.find((c) => c.id === categoryId);
    if (cat) {
      cat.shortcut_key = shortcutKey;
    }
    message.success("快捷键已更新");
  } catch (error) {
    message.error("更新快捷键失败");
  }
  editingCategoryShortcut.value = null;
}

function goBack() {
  if (isReviewMode.value) showTaskManager();
  else router.push("/");
}

function fitToView() {
  if (canvasRef.value) {
    canvasRef.value.fitToContainer();
    zoomLevel.value = canvasRef.value.scale;
  }
}

function handleZoomChange(zoom) {
  zoomLevel.value = zoom;
}
</script>

<template>
  <div
    class="annotation-container"
    :class="{ 'inspector-open': inspectorOpen }"
  >
    <h1 class="sr-only">
      {{ isReviewMode ? "预标注审核工作台" : "人工标注工作台" }}
    </h1>
    <!-- 首次加载全屏进度 -->
    <div
      v-if="!isReviewMode && store.isInitialLoad && store.isPrefetching"
      class="initial-loading"
    >
      <div class="loading-content">
        <h2>正在加载图片...</h2>
        <ui-progress
          :percentage="store.prefetchProgress"
          :stroke-width="20"
          :text-inside="true"
          style="width: 400px"
        />
        <p>预加载中，请稍候</p>
      </div>
    </div>

    <!-- 顶部工具栏 -->
    <header
      class="toolbar"
      v-show="isReviewMode || !store.isInitialLoad || !store.isPrefetching"
    >
      <div class="left">
        <ui-button @click="goBack" :icon="'ArrowLeft'">返回</ui-button>
        <span class="image-info" v-if="currentImage">
          {{ currentImage.filename }}
          <span v-if="currentImage.width">
            ({{ currentImage.width }} x {{ currentImage.height }})
          </span>
        </span>
      </div>
      <div class="center">
        <ui-button-group>
          <ui-button @click="undo()" :disabled="!canUndo" :icon="'RefreshLeft'">
            撤销
          </ui-button>
          <ui-button
            @click="redo()"
            :disabled="!canRedo"
            :icon="'RefreshRight'"
          >
            重做
          </ui-button>
        </ui-button-group>

        <div class="mode-toolbar">
          <ui-radio-group v-model="canvasMode" size="small">
            <ui-radio-button value="annotate">
              <span class="mode-btn"
                ><ui-icon name="MousePointer2" /> 标注 (V)</span
              >
            </ui-radio-button>
            <ui-radio-button value="pan">
              <span class="mode-btn"><ui-icon name="Hand" /> 拖动 (H)</span>
            </ui-radio-button>
          </ui-radio-group>

          <!-- 形状模式切换 -->
          <ui-radio-group
            v-model="shapeMode"
            size="small"
            class="shape-mode-group"
          >
            <ui-radio-button value="bbox">矩形</ui-radio-button>
            <ui-radio-button value="4point">4点</ui-radio-button>
            <ui-radio-button value="8point">8点</ui-radio-button>
          </ui-radio-group>

          <span class="zoom-info">{{ Math.round(zoomLevel * 100) }}%</span>
          <ui-button size="small" @click="fitToView">适应</ui-button>
        </div>
      </div>
      <div class="right">
        <ui-button-group class="nav-buttons">
          <ui-button
            @click="handlePrevious"
            :disabled="
              !canPrevious || actionBusy || review.busy || imageLoading
            "
            :icon="'ArrowLeft'"
          >
            上一张
          </ui-button>
          <ui-button
            @click="handleNext"
            :disabled="!canNext || actionBusy || review.busy || imageLoading"
            :icon="'ArrowRight'"
          >
            下一张
          </ui-button>
        </ui-button-group>
        <span
          v-if="!isReviewMode && store.isInHistory"
          class="history-indicator"
          >浏览历史中</span
        >
        <ui-button @click="showShortcutSettings = true" :icon="'Setting'"
          >快捷键</ui-button
        >
        <ui-button @click="showHelp = true" :icon="'QuestionFilled'"
          >帮助</ui-button
        >
      </div>
    </header>

    <div class="source-bar">
      <div class="source-control">
        <span>标注方式</span>
        <ui-radio-group
          :model-value="source"
          size="small"
          :disabled="workspaceLoading || actionBusy || review.busy"
          @change="changeSource"
        >
          <ui-radio-button value="preannotation" :disabled="!batches.length"
            >预标注审核</ui-radio-button
          >
          <ui-radio-button value="manual">人工标注</ui-radio-button>
        </ui-radio-group>
      </div>
      <template v-if="isReviewMode">
        <ui-select
          class="batch-select"
          aria-label="预标注批次"
          :model-value="review.task?.id"
          :disabled="workspaceLoading || actionBusy || review.busy"
          @change="changeBatch"
        >
          <ui-option
            v-for="batch in batches"
            :key="batch.id"
            :value="batch.id"
            :label="`#${batch.id} ${batch.is_sample ? '抽样' : '全量'} · ${batch.prompt.slice(0, 30)}`"
          />
        </ui-select>
        <ui-select
          class="queue-select"
          aria-label="审核队列"
          :model-value="review.queue.review_status"
          :disabled="workspaceLoading || actionBusy || review.busy"
          @change="(value) => changeReviewFilter('review_status', value)"
        >
          <ui-option label="待审核（含草稿）" value="pending" /><ui-option
            label="尚未编辑"
            value="unreviewed"
          /><ui-option label="审核草稿" value="draft" /><ui-option
            label="已通过"
            value="approved"
          /><ui-option label="已驳回" value="rejected" /><ui-option
            label="全部结果"
            value="all"
          />
        </ui-select>
        <ui-select
          class="queue-select"
          aria-label="候选框筛选"
          :model-value="review.queue.has_candidates"
          placeholder="全部候选结果"
          :disabled="workspaceLoading || actionBusy || review.busy"
          @change="(value) => changeReviewFilter('has_candidates', value)"
        >
          <ui-option label="全部候选结果" value="" /><ui-option
            label="存在候选框"
            value="true"
          /><ui-option label="无候选框" value="false" />
        </ui-select>
        <ui-tag
          :type="
            review.item?.review_status === 'approved' ? 'success' : 'warning'
          "
          >{{ statusText }}</ui-tag
        >
        <span v-if="dirty" class="unsaved-marker">有未保存修改</span>
        <span class="queue-summary">当前队列 {{ review.queueTotal }} 张</span>
      </template>
      <span v-else class="source-description">保存后完成当前人工标注</span>
      <ui-button class="task-link" size="small" @click="showTaskManager"
        >管理预标注任务</ui-button
      >
    </div>

    <!-- 主内容区 -->
    <main
      class="main-content"
      v-show="isReviewMode || !store.isInitialLoad || !store.isPrefetching"
    >
      <nav class="editor-tools" aria-label="画布工具">
        <ui-button
          circle
          variant="ghost"
          :class="{ active: canvasMode === 'annotate' }"
          aria-label="选择与绘制 V"
          @click="canvasMode = 'annotate'"
          ><ui-icon name="MousePointer2" /></ui-button
        ><ui-button
          circle
          variant="ghost"
          :class="{ active: canvasMode === 'pan' }"
          aria-label="平移 H"
          @click="canvasMode = 'pan'"
          ><ui-icon name="Hand" /></ui-button
        ><ui-divider /><ui-button
          circle
          variant="ghost"
          :class="{ active: shapeMode === 'bbox' }"
          aria-label="矩形工具"
          @click="
            shapeMode = 'bbox';
            canvasMode = 'annotate';
          "
          ><ui-icon name="Square" /></ui-button
        ><ui-button
          circle
          variant="ghost"
          :class="{ active: shapeMode === '4point' }"
          aria-label="四点工具"
          @click="
            shapeMode = '4point';
            canvasMode = 'annotate';
          "
          ><ui-icon name="Pentagon" /></ui-button
        ><ui-button
          circle
          variant="ghost"
          :class="{ active: shapeMode === '8point' }"
          aria-label="八点工具"
          @click="
            shapeMode = '8point';
            canvasMode = 'annotate';
          "
          ><ui-icon name="Layers" /></ui-button
        ><ui-divider /><ui-button
          circle
          variant="ghost"
          aria-label="放大"
          @click="canvasRef?.zoomBy(1.1)"
          ><ui-icon name="ZoomIn" /></ui-button
        ><ui-button
          circle
          variant="ghost"
          aria-label="缩小"
          @click="canvasRef?.zoomBy(0.9)"
          ><ui-icon name="ZoomOut" /></ui-button
        ><ui-button
          circle
          variant="ghost"
          aria-label="适应画布"
          @click="fitToView"
          ><ui-icon name="Maximize" /></ui-button
        ><ui-button
          class="inspector-toggle"
          circle
          variant="ghost"
          aria-label="对象与图层"
          @click="inspectorOpen = !inspectorOpen"
          ><ui-icon name="PanelLeft"
        /></ui-button>
      </nav>
      <!-- 画布区域 -->
      <div class="canvas-container">
        <div v-if="imageLoading" class="loading-overlay">
          <ui-icon class="is-loading" :size="48"><Loading /></ui-icon>
        </div>

        <div v-else-if="!currentImage" class="empty-state">
          <ui-empty :description="emptyDescription">
            <ui-button v-if="isReviewMode" @click="refreshResults"
              >刷新结果</ui-button
            >
            <ui-button
              v-if="isReviewMode && review.queue.review_status !== 'all'"
              type="primary"
              @click="changeReviewFilter('review_status', 'all')"
              >查看全部结果</ui-button
            >
            <ui-button @click="goBack">{{
              isReviewMode ? "返回任务列表" : "返回首页"
            }}</ui-button>
          </ui-empty>
        </div>

        <AnnotationCanvas
          v-else
          ref="canvasRef"
          :image-id="currentImage.id"
          :annotations="canvasAnnotations"
          :categories="store.categories"
          :selected-category="store.selectedCategory"
          :mode="canvasMode"
          :readonly="!editable"
          :allow-draw-without-category="true"
          :shape-mode="shapeMode"
          @add="handleAnnotationAdd"
          @update="handleAnnotationUpdate"
          @delete="handleAnnotationDelete"
          @zoom-change="handleZoomChange"
        />
      </div>

      <div class="editor-inspector">
        <!-- 左侧类别面板 -->
        <aside class="category-panel">
          <h3>类别选择</h3>
          <div class="mode-hint">
            {{
              isReviewMode
                ? "调整候选框；选择类别可补画漏检目标"
                : "画框后选择类别"
            }}
          </div>
          <div class="category-list">
            <ui-card
              as="div"
              role="button"
              tabindex="0"
              @keydown.enter.self="selectCategory(category)"
              v-for="category in store.categories"
              :key="category.id"
              class="category-item"
              :class="{ active: store.selectedCategory?.id === category.id }"
              @click="selectCategory(category)"
            >
              <span
                class="color-dot"
                :style="{ background: category.color }"
              ></span>
              <span class="name">{{ category.name }}</span>
              <img
                v-if="category.template_image_path"
                :src="`/api/categories/${category.id}/template-image`"
                class="category-thumb"
                alt=""
              />
              <ui-button
                variant="ghost"
                class="shortcut"
                :class="{ editing: editingCategoryShortcut === category.id }"
                @click="startEditCategoryShortcut(category, $event)"
                @keydown="handleCategoryShortcutKeydown(category, $event)"
                tabindex="0"
              >
                <template v-if="editingCategoryShortcut === category.id">
                  ...
                </template>
                <template v-else>
                  {{ category.shortcut_key || "+" }}
                </template>
              </ui-button>
            </ui-card>
          </div>

          <div class="annotations-list" v-if="workAnnotations.length > 0">
            <h3>
              {{
                isReviewMode
                  ? review.editable
                    ? "候选框"
                    : "候选记录"
                  : "当前标注"
              }}
              ({{ workAnnotations.length }})
            </h3>
            <ui-card
              as="div"
              role="group"
              tabindex="0"
              @keydown.enter.self="selectBox(ann)"
              v-for="(ann, index) in workAnnotations"
              :key="ann.id || ann.client_id"
              class="annotation-item"
              @click="selectBox(ann)"
            >
              <span class="index">#{{ index + 1 }}</span>
              <ui-select
                v-if="isReviewMode"
                aria-label="候选框类别"
                class="candidate-category"
                size="small"
                :model-value="ann.category_id"
                :disabled="!editable"
                @click.stop
                @change="(value) => changeCandidateCategory(ann, value)"
              >
                <ui-option
                  v-for="category in store.categories"
                  :key="category.id"
                  :value="category.id"
                  :label="category.name"
                />
              </ui-select>
              <span v-else class="category">{{
                store.categories.find((c) => c.id === ann.category_id)?.name ||
                "未知"
              }}</span>
              <span
                class="annotation-type-badge"
                v-if="ann.annotation_type === 'parallelogram'"
                >⬡</span
              >
              <ui-button
                type="danger"
                size="small"
                :icon="'Delete'"
                circle
                :disabled="!editable"
                aria-label="删除标注框"
                @click.stop="
                  handleAnnotationDelete(
                    isReviewMode ? review.canvasId(ann) : ann.id,
                  )
                "
              />
            </ui-card>
            <small v-if="isReviewMode" class="panel-note">{{
              review.editable
                ? "点击列表定位框；可修改类别、拖动调整或删除。"
                : "本批次候选记录只读；通过的框已归入正式标注。"
            }}</small>
          </div>
          <div
            v-if="isReviewMode && review.editable && !workAnnotations.length"
            class="panel-note empty-candidates"
          >
            {{
              review.item?.original_count
                ? "候选框已全部删除。请检查是否需要补画。"
                : "模型未发现目标。请检查图片后确认或补画漏检目标。"
            }}
          </div>
          <div
            v-if="isReviewMode && review.formal.length"
            class="annotations-list formal-list"
          >
            <h3>正式标注 ({{ review.formal.length }})</h3>
            <div
              v-for="ann in review.formal"
              :key="ann.id"
              class="annotation-item"
            >
              <span class="category">{{
                store.categories.find((c) => c.id === ann.category_id)?.name ||
                "未知"
              }}</span
              ><ui-tag size="small" type="info">已保存</ui-tag>
            </div>
            <small class="panel-note"
              >审核时作为只读参考，已有结果会保留。</small
            >
          </div>
        </aside>

        <!-- 右侧进度面板 -->
        <aside class="progress-panel">
          <template v-if="isReviewMode">
            <h3>预标注审核进度</h3>
            <div v-if="review.task" class="progress-info">
              <ui-progress
                type="circle"
                :percentage="reviewProgress"
                :width="120"
              />
              <div class="stats">
                <div class="stat-row">
                  <span>当前批次</span><span>#{{ review.task.id }}</span>
                </div>
                <div class="stat-row">
                  <span>已产出图片</span
                  ><span>{{ review.task.counts.succeeded || 0 }}</span>
                </div>
                <div class="stat-row">
                  <span>待审核 / 草稿</span
                  ><span class="warning">{{ pendingReviews }}</span>
                </div>
                <div class="stat-row">
                  <span>已通过</span
                  ><span class="success">{{ review.task.approved }}</span>
                </div>
                <div class="stat-row">
                  <span>已驳回</span><span>{{ review.task.rejected }}</span>
                </div>
              </div>
            </div>
            <div class="review-layers">
              <h4>显示图层</h4>
              <ui-checkbox v-model="review.showCandidates"
                >候选框 · 虚线</ui-checkbox
              ><ui-checkbox v-model="review.showFormal"
                >正式标注 · 实线</ui-checkbox
              >
            </div>
            <div class="review-guidance">
              <strong>{{ statusText }}</strong>
              <p v-if="!review.ready && currentImage">
                {{
                  review.item?.error_message ||
                  "这张图片尚未产生可审核的结果，请返回任务页检查。"
                }}
              </p>
              <p v-else-if="!review.editable && currentImage">
                本图已审核，可查看结果；后续正式标注修改请切换人工标注。
              </p>
              <p v-else>调整候选框后可保存草稿。审核通过才计入正式标注。</p>
            </div>
            <ui-button
              v-if="review.task"
              size="small"
              class="review-refresh"
              :disabled="workspaceLoading || actionBusy || review.busy"
              @click="refreshResults"
              >刷新当前结果</ui-button
            >
            <ui-button
              v-if="review.item?.raw_response"
              size="small"
              class="review-refresh"
              @click="showRawOutput = true"
              >查看模型输出</ui-button
            >
            <ui-button
              v-if="currentImage"
              size="small"
              class="review-refresh"
              @click="showInferenceTrace"
              >完整推理记录</ui-button
            >
          </template>
          <template v-else>
            <h3>标注进度</h3>
            <div v-if="progress" class="progress-info">
              <ui-progress
                type="circle"
                :percentage="progress.progress"
                :width="120"
              />
              <div class="stats">
                <div class="stat-row">
                  <span>总计:</span>
                  <span>{{ progress.total }}</span>
                </div>
                <div class="stat-row">
                  <span>已标注:</span>
                  <span class="success">{{ progress.labeled }}</span>
                </div>
                <div class="stat-row">
                  <span>未见:</span>
                  <span class="warning">{{ progress.skipped }}</span>
                </div>
                <div class="stat-row">
                  <span>待处理:</span>
                  <span class="info">{{ progress.pending }}</span>
                </div>
              </div>
            </div>

            <div class="queue-status" v-if="store.queueLength > 0">
              <h4>缓存队列</h4>
              <span class="queue-count">{{ store.queueLength }} 张</span>
            </div>
          </template>
        </aside>
      </div>
    </main>

    <div class="editor-filmstrip" aria-label="图片队列">
      <ui-button
        v-if="currentImage"
        variant="ghost"
        class="frame-thumbnail current"
        :aria-label="`当前图片 ${currentImage.filename}`"
        ><img
          :src="`/api/images/${currentImage.id}/file`"
          :alt="currentImage.filename"
        /><span>{{ currentImage.filename }}</span></ui-button
      ><ui-button
        v-for="frame in upcomingFrames"
        :key="frame.id"
        variant="ghost"
        class="frame-thumbnail"
        :disabled="imageLoading || actionBusy || review.busy"
        @click="
          router.push({
            name: 'Annotation',
            params: { datasetId },
            query: contextQuery({ image: frame.id }),
          })
        "
        ><img
          :src="`/api/images/${frame.id}/file`"
          :alt="frame.filename"
          loading="lazy"
          decoding="async"
        /><span>{{ frame.filename }}</span></ui-button
      ><span class="filmstrip-note"
        >{{ isReviewMode ? "审核队列" : "数据集图片" }} · 已预加载后续
        {{ upcomingFrames.length }} 张</span
      >
    </div>
    <div class="editor-actions">
      <span class="save-indicator" :class="{ dirty }"
        ><span />{{
          dirty
            ? "有未保存修改"
            : isReviewMode
              ? "草稿与审核通过独立保存"
              : "当前修改已保存"
        }}</span
      >
      <div class="editor-action-buttons">
        <ui-button
          @click="handleSkip"
          type="warning"
          :disabled="!editable || (isReviewMode && workAnnotations.length > 0)"
          >{{
            isReviewMode
              ? review.formal.length
                ? "无新增目标"
                : "确认无目标"
              : "未见"
          }}
          ({{ shortcutsStore.getShortcutText("skip") }})</ui-button
        >
        <ui-button
          @click="handleSave"
          :type="isReviewMode ? 'default' : 'primary'"
          :disabled="!editable"
          :loading="isReviewMode && review.busy"
          >{{ isReviewMode ? "保存草稿" : "保存" }} ({{
            shortcutsStore.getShortcutText("save")
          }})</ui-button
        >
        <ui-button
          v-if="isReviewMode"
          type="primary"
          :disabled="!editable"
          :loading="actionBusy"
          @click="approveReview()"
          >审核通过并下一张</ui-button
        >
        <ui-button
          v-if="isReviewMode"
          type="danger"
          plain
          :disabled="!editable"
          @click="approveReview('reject')"
          >驳回</ui-button
        >
      </div>
    </div>
    <ui-dialog v-model="traceOpen" title="推理详情" width="min(1250px,96vw)"
      ><PreannotationTrace
        v-if="traceOpen"
        :context="traceContext"
        embedded
        @close="traceOpen = false"
    /></ui-dialog>
    <!-- 后台预加载进度条（底部） -->
    <div
      v-if="!isReviewMode && !store.isInitialLoad && store.isPrefetching"
      class="prefetch-bar"
    >
      <span>缓存加载中...</span>
      <ui-progress
        :percentage="store.prefetchProgress"
        :stroke-width="6"
        style="width: 200px"
      />
      <span class="queue-info">队列: {{ store.queueLength }}</span>
    </div>

    <!-- 类别选择弹窗 -->
    <CategorySelectionPopup
      :visible="showCategoryPopup"
      :categories="store.categories"
      :current-image-url="
        currentImage ? `/api/images/${currentImage.id}/file` : ''
      "
      :pending-annotation="pendingAnnotation"
      @select="handleCategorySelected"
      @cancel="handleCategoryPopupCancel"
    />

    <ui-dialog
      v-model="showRawOutput"
      title="模型原始输出"
      width="min(720px, 94vw)"
    >
      <pre class="raw-output">{{ review.item?.raw_response }}</pre>
    </ui-dialog>
    <!-- 快捷键帮助弹窗 -->
    <ui-dialog v-model="showHelp" title="快捷键帮助" width="500px">
      <div class="help-content">
        <ui-simple-table class="shortcuts-table">
          <ui-table-row v-if="isReviewMode"
            ><ui-table-cell><ui-kbd>Ctrl / ⌘ + Enter</ui-kbd></ui-table-cell
            ><ui-table-cell>审核通过并下一张</ui-table-cell></ui-table-row
          >
          <ui-table-row>
            <ui-table-cell
              ><ui-kbd>{{
                shortcutsStore.getShortcutText("save")
              }}</ui-kbd></ui-table-cell
            >
            <ui-table-cell>{{
              isReviewMode ? "保存审核草稿，不审核通过" : "保存当前标注"
            }}</ui-table-cell>
          </ui-table-row>
          <ui-table-row>
            <ui-table-cell
              ><ui-kbd>{{
                shortcutsStore.getShortcutText("skip")
              }}</ui-kbd></ui-table-cell
            >
            <ui-table-cell>{{
              isReviewMode
                ? "确认无目标（须无候选框）"
                : "标记未见（画面中无目标）"
            }}</ui-table-cell>
          </ui-table-row>
          <ui-table-row>
            <ui-table-cell
              ><ui-kbd>{{
                shortcutsStore.getShortcutText("undo")
              }}</ui-kbd></ui-table-cell
            >
            <ui-table-cell>撤销</ui-table-cell>
          </ui-table-row>
          <ui-table-row>
            <ui-table-cell
              ><ui-kbd>{{
                shortcutsStore.getShortcutText("redo")
              }}</ui-kbd></ui-table-cell
            >
            <ui-table-cell>重做</ui-table-cell>
          </ui-table-row>
          <ui-table-row>
            <ui-table-cell
              ><ui-kbd>Delete</ui-kbd> /
              <ui-kbd>Backspace</ui-kbd></ui-table-cell
            >
            <ui-table-cell>删除选中的标注框 / 删除最后一个点</ui-table-cell>
          </ui-table-row>
          <ui-table-row>
            <ui-table-cell><ui-kbd>鼠标滚轮</ui-kbd></ui-table-cell>
            <ui-table-cell>缩放画布</ui-table-cell>
          </ui-table-row>
          <ui-table-row>
            <ui-table-cell><ui-kbd>空格</ui-kbd> + 拖动</ui-table-cell>
            <ui-table-cell>平移画布</ui-table-cell>
          </ui-table-row>
          <ui-table-row>
            <ui-table-cell><ui-kbd>V</ui-kbd></ui-table-cell>
            <ui-table-cell>切换到标注模式</ui-table-cell>
          </ui-table-row>
          <ui-table-row>
            <ui-table-cell><ui-kbd>H</ui-kbd></ui-table-cell>
            <ui-table-cell>切换到拖动模式</ui-table-cell>
          </ui-table-row>
          <ui-table-row>
            <ui-table-cell><ui-kbd>类别快捷键</ui-kbd></ui-table-cell>
            <ui-table-cell>快速切换类别并进入标注模式</ui-table-cell>
          </ui-table-row>
          <ui-table-row>
            <ui-table-cell><ui-kbd>Escape</ui-kbd></ui-table-cell>
            <ui-table-cell>取消当前点标注（4点/8点模式）</ui-table-cell>
          </ui-table-row>
          <ui-table-row>
            <ui-table-cell
              ><ui-kbd>{{
                shortcutsStore.getShortcutText("help")
              }}</ui-kbd></ui-table-cell
            >
            <ui-table-cell>显示/隐藏帮助</ui-table-cell>
          </ui-table-row>
        </ui-simple-table>
        <div class="help-tip">
          <ui-button
            text
            type="primary"
            @click="
              showHelp = false;
              showShortcutSettings = true;
            "
          >
            自定义快捷键
          </ui-button>
        </div>
      </div>
    </ui-dialog>

    <!-- 快捷键设置弹窗 -->
    <ui-dialog v-model="showShortcutSettings" title="快捷键设置" width="500px">
      <div class="shortcut-settings">
        <ui-simple-table class="shortcuts-table">
          <ui-table-row
            v-for="(config, action) in shortcutsStore.shortcuts"
            :key="action"
          >
            <ui-table-cell class="action-name">{{
              config.description
            }}</ui-table-cell>
            <ui-table-cell class="shortcut-key">
              <ui-button
                variant="outline"
                class="key-input"
                :class="{ editing: editingShortcut === action }"
                @click="startEditShortcut(action)"
                @keydown="handleShortcutKeydown"
                tabindex="0"
              >
                <template v-if="editingShortcut === action">
                  按下新快捷键...
                </template>
                <template v-else>
                  <ui-kbd>{{ shortcutsStore.getShortcutText(action) }}</ui-kbd>
                </template>
              </ui-button>
            </ui-table-cell>
          </ui-table-row>
        </ui-simple-table>
        <div class="settings-footer">
          <ui-button @click="resetShortcuts">恢复默认</ui-button>
        </div>
      </div>
    </ui-dialog>
  </div>
</template>

<style scoped>
.annotation-container {
  height: calc(100dvh - 30px);
  display: flex;
  flex-direction: column;
  background: var(--background);
  color: var(--foreground);
  min-height: 550px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  gap: 10px;
}
.toolbar .left,
.toolbar .center,
.toolbar .right,
.mode-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.toolbar .left {
  min-width: 0;
}
.toolbar .image-info {
  font-size: 11px;
  max-width: 230px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--muted);
}
.image-info > span {
  font-size: 9px;
  margin-left: 8px;
}
.mode-toolbar {
  gap: 10px;
}
.mode-btn {
  display: inline-flex;
  gap: 5px;
  align-items: center;
}
.zoom-info {
  font-size: 10px;
  color: var(--muted);
  min-width: 32px;
}
.toolbar .ui-button {
  font-size: 11px;
  min-height: 30px;
  padding: 6px 9px;
}
.toolbar :deep(.ui-segment) {
  font-size: 10px;
  padding: 6px 8px;
}
.toolbar .shape-mode-group {
  display: none;
}
.history-indicator {
  font-size: 10px;
  color: #edbf6c;
}
.source-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 9px 15px;
  font-size: 10px;
}
.source-control {
  display: flex;
  align-items: center;
  gap: 10px;
}
.source-control > span {
  color: var(--muted);
}
.source-bar .batch-select {
  width: 220px;
}
.source-bar .queue-select {
  width: 150px;
}
.source-bar .ui-select {
  font-size: 10px;
  min-height: 30px;
  padding: 6px 9px;
}
.source-bar .task-link {
  margin-left: auto;
  font-size: 10px;
}
.source-description,
.queue-summary {
  color: var(--muted);
}
.unsaved-marker {
  color: #edbf6c;
}
.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
  position: relative;
}
.canvas-container {
  flex: 1;
  min-width: 0;
  position: relative;
  background: #15191f;
  overflow: hidden;
}
.editor-tools {
  width: 49px;
  flex-shrink: 0;
  padding: 12px 6px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  overflow: auto;
}
.editor-tools > .ui-button {
  min-height: 33px;
  padding: 6px;
}
.editor-tools .active {
  background: #3a61ed33;
  color: #8da9ff;
}
.editor-tools > .ui-divider {
  width: 23px;
  margin: 4px;
}
.editor-inspector {
  width: 280px;
  flex-shrink: 0;
  border-left: 1px solid var(--border);
  overflow-y: auto;
  background: var(--surface);
}
.category-panel,
.progress-panel {
  padding: 19px 17px;
}
.category-panel h3,
.progress-panel h3 {
  font-size: 12px;
  margin-bottom: 15px;
}
.progress-panel {
  border-top: 1px solid var(--border);
}
.mode-hint,
.panel-note,
.review-guidance {
  font-size: 10px;
  line-height: 1.8;
  color: var(--muted);
}
.mode-hint {
  margin: 0 0 14px;
}
.category-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.category-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px;
  background: var(--surface-muted);
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
}
.category-item:hover {
  border-color: #5b6b89;
}
.category-item.active {
  background: #3a61ed20;
  border-color: #6382ef80;
}
.category-item .color-dot {
  height: 8px;
  width: 8px;
  flex-shrink: 0;
  border-radius: 3px;
}
.category-item .name {
  font-size: 11px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.category-item .shortcut {
  font-size: 9px;
  padding: 3px 5px;
  min-height: 20px;
  background: #ffffff0c;
  border-radius: 4px;
}
.category-thumb {
  width: 23px;
  height: 23px;
  object-fit: contain;
  border-radius: 4px;
}
.annotations-list {
  margin-top: 24px;
}
.annotation-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 0;
  font-size: 11px;
  border: 0;
  border-bottom: 1px solid var(--border);
  border-radius: 0;
  background: none;
}
.annotation-item .index {
  font-size: 9px;
  color: var(--muted);
}
.annotation-item .category {
  flex: 1;
}
.annotation-item .candidate-category {
  flex: 1;
  font-size: 10px;
}
.annotation-item .ui-button--icon {
  min-height: 23px;
  width: 23px;
  padding: 4px;
}
.annotation-item .ui-button--icon > svg {
  width: 12px;
}
.annotation-type-badge {
  font-size: 12px;
  color: var(--muted);
}
.panel-note {
  display: block;
  margin-top: 12px;
}
.formal-list {
  opacity: 0.65;
}
.review-layers {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 24px 0;
}
.review-layers h4 {
  font-size: 11px;
}
.review-layers .ui-check-label {
  font-size: 10px;
}
.review-guidance {
  padding: 12px;
  background: var(--surface-muted);
  border-radius: 6px;
  margin-top: 16px;
}
.review-guidance strong {
  font-size: 11px;
  color: var(--foreground);
}
.review-guidance p {
  margin-top: 7px;
}
.review-refresh {
  display: flex;
  justify-content: center;
  width: 100%;
  margin-top: 9px;
  font-size: 10px;
}
.stats {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
  font-size: 11px;
}
.stat-row {
  display: flex;
  justify-content: space-between;
  color: var(--muted);
}
.stat-row .success {
  color: #68bd9f;
}
.stat-row .warning {
  color: #edbf6c;
}
.stat-row .info {
  color: #8da9ff;
}
.queue-status {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 24px;
  font-size: 11px;
}
.queue-status h4 {
  font-weight: 500;
  color: var(--muted);
}
.queue-count {
  color: #8da9ff;
}
.editor-filmstrip {
  height: 91px;
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 9px 15px;
  background: var(--surface);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
  overflow-x: auto;
}
.frame-thumbnail {
  padding: 2px;
  width: 90px;
  min-width: 90px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-radius: 5px;
  border: 1px solid transparent;
  position: relative;
}
.frame-thumbnail img {
  width: 84px;
  height: 47px;
  object-fit: cover;
  border-radius: 3px;
}
.frame-thumbnail > span {
  font-size: 8px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 84px;
  white-space: nowrap;
}
.frame-thumbnail.current {
  border-color: var(--primary);
  background: #3a61ed20;
}
.filmstrip-note {
  font-size: 10px;
  color: var(--muted);
  margin-left: 12px;
  white-space: nowrap;
}
.editor-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  padding: 13px 17px;
  background: var(--surface);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
.editor-action-buttons {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.editor-actions .ui-button {
  font-size: 11px;
}
.save-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: var(--muted);
  white-space: nowrap;
}
.save-indicator > span {
  height: 5px;
  width: 5px;
  background: #68bd9f;
  border-radius: 50%;
}
.save-indicator.dirty > span {
  background: #edbf6c;
}
.prefetch-overlay {
  position: absolute;
  inset: 0;
  z-index: 100;
  background: var(--background);
  display: flex;
  align-items: center;
  justify-content: center;
}
.prefetch-content {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}
.prefetch-content h2 {
  font-size: 20px;
}
.prefetch-content p {
  font-size: 12px;
  color: var(--muted);
}
.prefetch-content > .ui-progress {
  max-width: 85vw;
}
.loading-overlay,
.empty-state {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.loading-overlay {
  color: var(--primary);
}
.empty-state .ui-empty {
  max-width: 500px;
}
.prefetch-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 20px;
  background: var(--surface);
  font-size: 10px;
  color: var(--muted);
}
.help-content .shortcuts-table {
  font-size: 11px;
}
.help-tip {
  margin-top: 16px;
}
.settings-footer {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
.key-input {
  font-size: 11px;
  min-width: 110px;
}
.key-input.editing {
  border-color: var(--primary);
}
.raw-output {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 11px;
  color: var(--muted);
}
.inspector-toggle {
  display: none;
}
@media (max-width: 1250px) {
  .toolbar .image-info {
    max-width: 160px;
  }
  .toolbar .center {
    margin-left: auto;
  }
  .toolbar .right {
    margin-left: auto;
  }
  .editor-inspector {
    width: 240px;
  }
  .source-bar {
    gap: 8px;
  }
  .source-bar .batch-select {
    width: 185px;
  }
  .source-bar .queue-select {
    width: 130px;
  }
  .toolbar .mode-toolbar .ui-radio-group {
    max-width: 100%;
  }
  .filmstrip-note {
    font-size: 9px;
  }
  .editor-actions {
    gap: 8px;
  }
  .save-indicator {
    display: none;
  }
}
@media (max-width: 800px) {
  .annotation-container {
    min-height: 600px;
    height: calc(100dvh - 45px);
  }
  .toolbar {
    padding: 8px;
    gap: 7px;
  }
  .toolbar .left .image-info > span {
    display: none;
  }
  .toolbar .center {
    order: 3;
    width: 100%;
    justify-content: center;
  }
  .toolbar .right .nav-buttons {
    display: none;
  }
  .source-bar {
    padding: 8px;
    max-height: 132px;
    overflow: auto;
  }
  .source-control > span {
    display: none;
  }
  .source-bar .queue-summary,
  .source-bar .unsaved-marker {
    display: none;
  }
  .source-bar .ui-select {
    flex: 1;
    min-width: 110px;
  }
  .source-bar .task-link {
    margin-left: 0;
  }
  .editor-inspector {
    display: none;
    position: absolute;
    right: 0;
    top: 0;
    bottom: 0;
    z-index: 30;
    box-shadow: -15px 0 40px #0005;
  }
  .inspector-open .editor-inspector {
    display: block;
    width: 260px;
    max-width: 80%;
  }
  .inspector-toggle {
    display: inline-flex;
  }
  .editor-tools {
    width: 41px;
    padding: 8px 3px;
    gap: 6px;
  }
  .editor-tools > .ui-button {
    width: 31px;
    min-height: 30px;
  }
  .editor-filmstrip {
    height: 79px;
    padding: 6px 10px;
  }
  .frame-thumbnail img {
    height: 39px;
  }
  .frame-thumbnail {
    min-width: 76px;
    width: 76px;
  }
  .filmstrip-note {
    display: none;
  }
  .editor-actions {
    padding: 8px;
  }
  .editor-action-buttons {
    width: 100%;
    gap: 5px;
  }
  .editor-actions .ui-button {
    font-size: 10px;
    min-height: 32px;
    padding: 6px 8px;
  }
  .source-bar :deep(.ui-segment) {
    font-size: 10px;
  }
  .toolbar .mode-toolbar {
    gap: 7px;
  }
  .toolbar .center > .ui-button-group .ui-button {
    font-size: 10px;
  }
  .toolbar .image-info {
    max-width: 140px;
  }
  .toolbar .left > .ui-button {
    font-size: 10px;
  }
  .toolbar .right > .ui-button {
    font-size: 10px;
  }
}
</style>

<style scoped>
@media (max-width: 800px) {
  .source-bar {
    max-height: none;
    overflow: visible;
  }
  .source-bar .task-link {
    display: none;
  }
}
</style>
