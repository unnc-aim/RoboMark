<script setup>
import { useRoute, useRouter } from "vue-router";
import { useUserStore } from "../stores/user";
const route = useRoute(),
  router = useRouter(),
  user = useUserStore();
const props = defineProps({ datasetId: [String, Number] });
</script>
<template>
  <nav class="dataset-tabs" aria-label="数据集导航">
    <ui-button
      variant="ghost"
      :class="{ active: route.name === 'DatasetDetail' }"
      @click="router.push(`/datasets/${datasetId}`)"
      >图片与概览</ui-button
    ><ui-button
      variant="ghost"
      :class="{ active: route.name === 'Preannotation' }"
      @click="router.push(`/datasets/${datasetId}/preannotation`)"
      >预标注与审核</ui-button
    ><ui-button
      v-if="user.isAdmin"
      variant="ghost"
      :class="{ active: route.name === 'AdminCategories' }"
      @click="router.push(`/admin/categories/${datasetId}`)"
      >类别与模板</ui-button
    ><ui-button
      v-if="user.isAdmin"
      variant="ghost"
      :class="{ active: route.name === 'DatasetSettings' }"
      @click="router.push(`/datasets/${datasetId}/settings`)"
      >数据集设置</ui-button
    >
  </nav>
</template>
