<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import { datasetApi, datasetKeys } from "../shared/api/datasets";
import { useUserStore } from "../stores/user";
import api from "../utils/api";
import { message, messageBox } from "../shared/ui/feedback";
import DatasetHeader from "../components/DatasetHeader.vue";
const route = useRoute(),
  router = useRouter(),
  user = useUserStore(),
  client = useQueryClient();
const id = Number(route.params.datasetId),
  page = ref(1),
  pageSize = ref(6),
  scanning = ref(false);
const dataset = useQuery({
  queryKey: datasetKeys.detail(id),
  queryFn: ({ signal }) => datasetApi.detail(id, signal),
});
const images = useQuery({
  queryKey: computed(() => [
    ...datasetKeys.images(id),
    page.value,
    pageSize.value,
  ]),
  queryFn: ({ signal }) =>
    datasetApi.images(id, page.value, pageSize.value, signal),
});
const categories = useQuery({
  queryKey: ["categories", id],
  queryFn: async () => (await api.get(`/categories/dataset/${id}`)).data,
});
watch(pageSize, () => (page.value = 1));
async function scan() {
  scanning.value = true;
  try {
    const r = await api.post(`/datasets/${id}/scan`);
    message.success(
      `扫描完成：导入 ${r.data.imported_images} 张，跳过 ${r.data.skipped_images} 张`,
    );
    client.invalidateQueries({ queryKey: datasetKeys.all });
  } finally {
    scanning.value = false;
  }
}
async function remove() {
  try {
    await messageBox.confirm(
      `确定删除数据集「${dataset.data.value?.name}」及其所有图片与标注？`,
      "删除数据集",
    );
    await api.delete(`/datasets/${id}`);
    await client.invalidateQueries({ queryKey: datasetKeys.all });
    router.push("/admin/datasets");
  } catch {}
}
</script>
<template>
  <div v-loading="dataset.isPending.value">
    <DatasetHeader
      :dataset-id="id"
      :dataset="dataset.data.value"
      :loading="dataset.isPending.value"
    />
    <ui-alert
      v-if="dataset.isError.value"
      type="error"
      title="无法加载数据集，请检查权限与服务状态"
      ><ui-button @click="dataset.refetch()">重新加载</ui-button></ui-alert
    >
    <template v-if="dataset.data.value">
      <div class="summary-strip">
        <span
          ><strong>{{ dataset.data.value.total_images }}</strong> 张图片</span
        ><span
          ><strong>{{ dataset.data.value.labeled_images }}</strong> 已标注</span
        ><span
          ><strong>{{ categories.data.value?.length || 0 }}</strong>
          个类别</span
        ><span
          ><strong
            >{{
              dataset.data.value.total_images
                ? Math.round(
                    (dataset.data.value.labeled_images /
                      dataset.data.value.total_images) *
                      100,
                  )
                : 0
            }}%</strong
          >
          完成度</span
        >
      </div>
      <ui-card class="panel-padding"
        ><div class="section-heading">
          <div>
            <h2>图片浏览</h2>
            <p>选择图片进入人工标注工作台</p>
          </div>
          <div class="image-browser-actions">
            <ui-button
              v-if="user.isAdmin"
              :loading="scanning"
              icon="Folder"
              @click="scan"
              >扫描图片</ui-button
            >
            <ui-select
              v-model="pageSize"
              aria-label="每页图片数量"
              style="width: 120px"
              ><ui-option :value="6" label="每页 6 张" /><ui-option
                :value="12"
                label="每页 12 张"
            /></ui-select>
          </div>
        </div>
        <ui-alert v-if="images.isError.value" type="error" title="图片加载失败"
          ><ui-button @click="images.refetch()">重试</ui-button></ui-alert
        >
        <div v-loading="images.isPending.value" class="detail-images">
          <ui-button
            v-for="image in images.data.value?.items"
            :key="image.id"
            class="detail-image"
            variant="ghost"
            @click="
              router.push({
                name: 'Annotation',
                params: { datasetId: id },
                query: { image: image.id },
              })
            "
            ><img
              :src="`/api/images/${image.id}/preview?width=640`"
              :alt="image.filename"
              loading="lazy"
              decoding="async"
            /><span
              ><strong>{{ image.filename }}</strong
              ><ui-tag
                :type="image.status === 'labeled' ? 'success' : 'info'"
                >{{
                  image.status === "labeled"
                    ? "已标注"
                    : image.status === "skipped"
                      ? "无目标"
                      : "待标注"
                }}</ui-tag
              ></span
            ><small>{{ image.width }} × {{ image.height }}</small></ui-button
          >
        </div>
        <ui-empty
          v-if="images.data.value && !images.data.value.items.length"
          description="目录中还没有图片，可扫描目录导入" /><ui-pagination
          v-model:current-page="page"
          :total="images.data.value?.total || 0"
          :page-size="pageSize"
      /></ui-card>
      <div class="detail-bottom">
        <span class="muted">图片来源：{{ dataset.data.value.image_path }}</span
        ><ui-button
          v-if="user.isAdmin"
          type="danger"
          size="small"
          @click="remove"
          >删除数据集</ui-button
        >
      </div></template
    >
  </div>
</template>
<style scoped>
.image-browser-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.detail-images {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}
.detail-image {
  padding: 0;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  text-align: left;
  gap: 0;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.detail-image img {
  width: 100%;
  aspect-ratio: 1.8;
  object-fit: cover;
  background: var(--surface-muted);
}
.detail-image > span {
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4) 6px;
}
.detail-image strong {
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.detail-image > small {
  padding: 0 var(--space-4) var(--space-4);
  color: var(--muted);
  font-size: 10px;
}
.detail-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 10px;
  gap: var(--space-4);
  margin-top: var(--space-5);
  overflow-wrap: anywhere;
}
@media (max-width: 1000px) {
  .detail-images {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 500px) {
  .detail-images {
    grid-template-columns: 1fr;
  }
}
</style>
