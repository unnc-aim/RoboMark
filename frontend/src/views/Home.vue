<script setup>
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import WorkspaceLayout from "../layouts/WorkspaceLayout.vue";
import DatasetCard from "../components/DatasetCard.vue";
import { useDatasets } from "../shared/api/datasets";
import { useUserStore } from "../stores/user";
const router = useRouter(),
  user = useUserStore(),
  query = useDatasets();
const search = ref(""),
  status = ref("all"),
  layout = ref("grid");
const datasets = computed(() => query.data.value || []);
const filtered = computed(() =>
  datasets.value.filter(
    (d) =>
      `${d.name} ${d.description || ""}`
        .toLowerCase()
        .includes(search.value.toLowerCase()) &&
      (status.value === "all" ||
        (status.value === "done"
          ? d.total_images > 0 && d.labeled_images >= d.total_images
          : d.labeled_images < d.total_images)),
  ),
);
</script>
<template>
  <WorkspaceLayout>
    <header class="page-heading">
      <div>
        <h1>选择数据集，开始工作。</h1>
        <p>从一张图片开始，让每个目标得到可靠的标注。</p>
      </div>
      <ui-button
        v-if="user.isAdmin"
        type="primary"
        icon="Plus"
        @click="router.push('/admin/datasets?create=1')"
        >新建数据集</ui-button
      >
    </header>
    <div class="summary-strip">
      <span
        ><strong>{{ datasets.length }}</strong> 个数据集</span
      ><span
        ><strong>{{
          datasets.reduce((s, d) => s + d.total_images, 0).toLocaleString()
        }}</strong>
        张图片</span
      ><span
        ><strong>{{
          datasets.reduce((s, d) => s + d.labeled_images, 0).toLocaleString()
        }}</strong>
        张已标注</span
      >
    </div>
    <div class="collection-toolbar">
      <ui-radio-group v-model="status" aria-label="数据集状态"
        ><ui-radio-button value="all">全部数据集</ui-radio-button
        ><ui-radio-button value="active">进行中</ui-radio-button
        ><ui-radio-button value="done">已完成</ui-radio-button></ui-radio-group
      >
      <div class="collection-controls">
        <ui-input
          v-model="search"
          prefix-icon="Search"
          placeholder="搜索数据集…"
        /><ui-radio-group v-model="layout" aria-label="布局"
          ><ui-radio-button value="grid" aria-label="网格视图"
            ><ui-icon name="LayoutGrid" /></ui-radio-button
          ><ui-radio-button value="list" aria-label="列表视图"
            ><ui-icon name="List" /></ui-radio-button
        ></ui-radio-group>
      </div>
    </div>
    <ui-alert v-if="query.isError.value" type="error" title="数据集加载失败"
      ><ui-button size="small" @click="query.refetch()"
        >重新加载</ui-button
      ></ui-alert
    >
    <div
      v-loading="query.isPending.value"
      class="dataset-collection"
      :class="{ 'list-view': layout === 'list' }"
    >
      <DatasetCard
        v-for="dataset in filtered"
        :key="dataset.id"
        :dataset="dataset"
        :list="layout === 'list'"
      />
    </div>
    <ui-empty
      v-if="!query.isPending.value && !query.isError.value && !filtered.length"
      :description="search ? '没有匹配的数据集' : '暂无可用数据集'"
      ><ui-button v-if="search" @click="search = ''"
        >清除搜索</ui-button
      ></ui-empty
    >
  </WorkspaceLayout>
</template>
