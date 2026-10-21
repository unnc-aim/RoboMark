<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import WorkspaceLayout from "../../layouts/WorkspaceLayout.vue";
const route = useRoute();
const viewKey = computed(
  () =>
    `${route.name}:${route.params.datasetId || ""}:${route.params.taskId || ""}`,
);
</script>
<template>
  <WorkspaceLayout><router-view :key="viewKey" /></WorkspaceLayout>
</template>
