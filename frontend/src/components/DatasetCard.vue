<script setup lang="ts">
import { computed } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { useRouter } from "vue-router";
import { datasetApi, type Dataset } from "../shared/api/datasets";
const props = defineProps<{ dataset: Dataset; list?: boolean }>();
const router = useRouter();
const progress = computed(() =>
  props.dataset.total_images
    ? Math.round(
        (props.dataset.labeled_images / props.dataset.total_images) * 100,
      )
    : 0,
);
const cover = useQuery({
  queryKey: computed(() => ["dataset-cover", props.dataset.id]),
  queryFn: ({ signal }) => datasetApi.images(props.dataset.id, 1, 1, signal),
  staleTime: 60_000,
});
function open() {
  router.push(`/datasets/${props.dataset.id}`);
}
</script>
<template>
  <ui-card
    as="article"
    class="dataset-card"
    :class="{ 'dataset-card-list': list }"
    role="link"
    tabindex="0"
    :aria-label="`打开数据集 ${dataset.name}`"
    @click="open"
    @keydown.enter.self="open"
  >
    <div class="dataset-cover">
      <img
        v-if="cover.data.value?.items[0]"
        :src="`/api/images/${cover.data.value.items[0].id}/file`"
        :alt="dataset.name"
        loading="lazy"
        decoding="async"
      /><ui-icon v-else name="Image" :size="34" /><span
        class="dataset-cover-count"
        ><ui-icon name="Picture" :size="12" />{{
          dataset.total_images.toLocaleString()
        }}
        张图片</span
      ><ui-tag :type="progress === 100 ? 'success' : 'primary'">{{
        progress === 100 ? "已完成" : progress > 0 ? "标注中" : "待开始"
      }}</ui-tag>
    </div>
    <div class="dataset-card-content">
      <div class="dataset-card-title">
        <h3>{{ dataset.name }}</h3>
        <ui-icon name="ArrowRight" :size="15" />
      </div>
      <p>
        {{
          dataset.description || "为这个数据集添加描述，帮助团队了解标注目标。"
        }}
      </p>
      <div class="dataset-card-progress">
        <span>标注进度</span
        ><strong
          >{{ dataset.labeled_images.toLocaleString() }}
          <small>/ {{ dataset.total_images.toLocaleString() }}</small></strong
        >
      </div>
      <ui-progress :percentage="progress" :show-text="false" />
      <div class="dataset-card-footer">
        <span
          ><span class="status-dot" />{{
            dataset.is_active ? "可开始工作" : "已停用"
          }}</span
        >
        <div>
          <ui-button
            size="small"
            variant="ghost"
            @click.stop="router.push(`/datasets/${dataset.id}/preannotation`)"
            >预标注</ui-button
          ><ui-button
            size="small"
            variant="ghost"
            @click.stop="router.push(`/annotate/${dataset.id}`)"
            >开始标注 <ui-icon name="ArrowRight" :size="12"
          /></ui-button>
        </div>
      </div>
    </div>
  </ui-card>
</template>
<style scoped>
.dataset-card {
  cursor: pointer;
  transition: border-color 0.2s;
  min-width: 0;
}
.dataset-card:hover {
  border-color: #a4b6fb;
}
.dataset-cover {
  position: relative;
  aspect-ratio: 2.2;
  background: #e9edf4;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9da7b7;
  overflow: hidden;
}
.dataset-cover > img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.dataset-cover:after {
  content: "";
  position: absolute;
  inset: 55% 0 0;
  background: linear-gradient(transparent, #0d162d60);
  pointer-events: none;
}
.dataset-cover-count {
  position: absolute;
  left: 16px;
  bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: white;
  font-size: 10px;
  z-index: 1;
}
.dataset-cover > .ui-badge {
  position: absolute;
  right: 12px;
  top: 12px;
  z-index: 1;
}
.dataset-card-content {
  padding: var(--space-5) var(--space-5) 0;
}
.dataset-card-title {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: center;
}
.dataset-card-title h3 {
  font-size: 14px;
}
.dataset-card-title svg {
  color: #9da6b5;
}
.dataset-card-content > p {
  font-size: 11px;
  line-height: 1.8;
  color: var(--muted);
  margin: var(--space-2) 0 var(--space-5);
  min-height: 0;
}
.dataset-card-progress {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  margin-bottom: var(--space-3);
  color: var(--muted);
}
.dataset-card-progress strong {
  font-size: 11px;
  color: var(--foreground);
  font-weight: 550;
}
.dataset-card-progress small {
  color: var(--muted);
  font-size: 10px;
  font-weight: 400;
}
.dataset-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid var(--border);
  margin-top: var(--space-5);
  padding: var(--space-3) 0;
  gap: 5px;
}
.dataset-card-footer > span {
  font-size: 10px;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 5px;
}
.dataset-card-footer .ui-button {
  font-size: 10px;
  padding: 5px;
}
.status-dot {
  width: 5px;
  height: 5px;
  background: var(--success);
  border-radius: 50%;
}
.dataset-card-list {
  display: flex;
  align-items: stretch;
}
.dataset-card-list .dataset-cover {
  width: 200px;
  aspect-ratio: auto;
  flex-shrink: 0;
}
.dataset-card-list .dataset-card-content {
  flex: 1;
}
.dataset-card-list .dataset-card-content > p {
  min-height: 0;
  margin: 7px 0 var(--space-3);
}
@media (max-width: 700px) {
  .dataset-card-list .dataset-cover {
    width: 100px;
  }
  .dataset-card-list .dataset-cover-count {
    display: none;
  }
  .dataset-card-list .dataset-card-content {
    padding: var(--space-4) var(--space-3) 0;
  }
  .dataset-card-footer {
    flex-wrap: wrap;
  }
}
</style>
