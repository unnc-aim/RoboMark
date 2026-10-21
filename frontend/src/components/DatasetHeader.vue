<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useUserStore } from "../stores/user";
import type { Dataset } from "../shared/api/datasets";
import DatasetTabs from "./DatasetTabs.vue";

const props = defineProps<{
  datasetId: string | number;
  dataset?: Pick<Dataset, "name" | "description"> | null;
  loading?: boolean;
}>();
const router = useRouter();
const user = useUserStore();
const name = computed(() => props.dataset?.name || "数据集");
const description = computed(
  () =>
    props.dataset?.description?.trim() ||
    "管理图片、预标注、类别与数据集设置。",
);
</script>

<template>
  <div class="dataset-header">
    <ui-button
      class="dataset-back"
      variant="ghost"
      icon="ArrowLeft"
      @click="router.push(user.isAdmin ? '/admin/datasets' : '/')"
      >全部数据集</ui-button
    >
    <header class="dataset-heading">
      <div class="dataset-heading-copy">
        <h1 :title="name">{{ name }}</h1>
        <p :title="description">{{ description }}</p>
      </div>
      <div class="dataset-heading-actions">
        <ui-button
          type="primary"
          icon="Play"
          :disabled="loading || !dataset"
          @click="router.push(`/annotate/${datasetId}`)"
          >开始标注</ui-button
        >
      </div>
    </header>
    <DatasetTabs :dataset-id="datasetId" />
  </div>
</template>

<style scoped>
.dataset-header {
  width: 100%;
  min-width: 0;
}
.dataset-back {
  margin: 0 0 12px;
  padding: 6px 0;
  min-height: 30px;
  font-size: 11px;
}
.dataset-back:hover {
  background: transparent;
}
.dataset-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}
.dataset-heading-copy {
  flex: 1;
  min-width: 0;
}
.dataset-heading h1 {
  margin: 0;
  color: var(--foreground);
  font-size: 28px;
  font-weight: 650;
  line-height: 1.35;
  letter-spacing: -0.6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dataset-heading p {
  margin: 8px 0 0;
  min-height: 22px;
  font-size: 12px;
  line-height: 22px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dataset-heading-actions {
  display: flex;
  align-items: center;
  flex: none;
}
@media (max-width: 650px) {
  .dataset-heading {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  .dataset-heading-copy {
    width: 100%;
  }
  .dataset-heading h1 {
    font-size: 24px;
  }
}
</style>
