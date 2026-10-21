<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useQueryClient } from "@tanstack/vue-query";
import api from "../utils/api";
import { message } from "../shared/ui/feedback";
import DatasetHeader from "../components/DatasetHeader.vue";
import DirectoryPicker from "../components/DirectoryPicker.vue";
const route = useRoute(),
  router = useRouter(),
  client = useQueryClient(),
  id = Number(route.params.datasetId);
const loading = ref(true),
  error = ref(false),
  busy = ref(false),
  dataset = ref<any>(null);
const form = ref({
  name: "",
  description: "",
  image_path: "",
  label_path: "",
  is_active: true,
});
const config = ref({
  format_type: "yolo",
  annotation_path: "",
  source_width: 1920,
  source_height: 1080,
  auto_import_annotations: true,
});
async function load() {
  loading.value = true;
  error.value = false;
  try {
    const [d, c] = await Promise.all([
      api.get(`/datasets/${id}`),
      api.get(`/dataset-configs/${id}`),
    ]);
    dataset.value = d.data;
    form.value = { ...d.data };
    config.value = { ...config.value, ...c.data };
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}
async function save() {
  if (!form.value.name.trim() || !form.value.image_path.trim())
    return message.warning("请填写数据集名称和图片目录");
  busy.value = true;
  try {
    const response = await api.put(`/datasets/${id}`, form.value);
    dataset.value = response.data;
    await api.post("/dataset-configs/", { dataset_id: id, ...config.value });
    await client.invalidateQueries({ queryKey: ["datasets"] });
    client.invalidateQueries({ queryKey: ["categories", id] });
    message.success("数据集设置已保存");
  } finally {
    busy.value = false;
  }
}
async function importData(kind: string) {
  busy.value = true;
  try {
    const r = await api.post(`/dataset-configs/${id}/import-${kind}`);
    message.success(r.data.message);
    client.invalidateQueries({ queryKey: ["datasets"] });
    client.invalidateQueries({ queryKey: ["categories", id] });
  } finally {
    busy.value = false;
  }
}
onMounted(load);
</script>
<template>
  <div v-loading="loading">
    <DatasetHeader :dataset-id="id" :dataset="dataset" :loading="loading" />
    <ui-alert v-if="error" type="error" title="设置加载失败"
      ><ui-button @click="load">重新加载</ui-button></ui-alert
    >
    <div v-if="dataset" class="two-column">
      <ui-card class="panel-padding"
        ><div class="section-heading"><h2>基础信息</h2></div>
        <ui-form :disabled="busy" @submit.prevent="save"
          ><ui-form-item label="数据集名称" required
            ><ui-input v-model="form.name" /></ui-form-item
          ><ui-form-item label="描述"
            ><ui-input
              v-model="form.description"
              type="textarea"
              :rows="3" /></ui-form-item
          ><ui-form-item label="图片目录" required
            ><DirectoryPicker
              v-model="form.image_path"
              label="图片目录" /></ui-form-item
          ><ui-form-item label="标签目录"
            ><DirectoryPicker v-model="form.label_path" label="标签目录"
          /></ui-form-item>
          <div class="form-grid">
            <ui-form-item label="数据格式"
              ><ui-select v-model="config.format_type"
                ><ui-option value="yolo" label="YOLO" /><ui-option
                  value="dji_roco"
                  label="DJI ROCO" /><ui-option
                  value="rc2026_wulin"
                  label="RC2026-wulin" /></ui-select></ui-form-item
            ><ui-form-item label="启用数据集"
              ><ui-switch v-model="form.is_active"
            /></ui-form-item>
          </div>
          <template v-if="config.format_type === 'dji_roco'"
            ><ui-form-item label="标注来源目录"
              ><DirectoryPicker
                v-model="config.annotation_path"
                label="标注来源目录"
            /></ui-form-item>
            <div class="form-grid">
              <ui-form-item label="原始宽度"
                ><ui-input-number
                  v-model="config.source_width"
                  :min="1" /></ui-form-item
              ><ui-form-item label="原始高度"
                ><ui-input-number v-model="config.source_height" :min="1"
              /></ui-form-item>
            </div>
            <ui-form-item label="自动导入标注"
              ><ui-switch
                v-model="
                  config.auto_import_annotations
                " /></ui-form-item></template
          ><ui-button
            native-type="submit"
            type="primary"
            icon="Save"
            :loading="busy"
            >保存设置</ui-button
          ></ui-form
        ></ui-card
      >
      <div class="stack">
        <ui-card class="panel-padding"
          ><div class="section-heading"><h2>导入与类别</h2></div>
          <p class="form-tip">
            目录选择只读取文件信息。配置服务器路径后，可在数据集详情中扫描图片。
          </p>
          <div class="settings-actions">
            <ui-button @click="router.push(`/admin/categories/${id}`)"
              >管理类别与模板</ui-button
            ><ui-button
              :disabled="busy"
              @click="importData('default-categories')"
              >从格式导入默认类别</ui-button
            ><ui-button
              v-if="config.format_type === 'dji_roco'"
              :disabled="busy"
              @click="importData('annotations')"
              >导入现有标注</ui-button
            >
          </div></ui-card
        ><ui-alert title="数据保存位置" :closable="false"
          >RoboMark
          使用服务器上的图片和标签目录。选择本机目录后，请核对服务器路径。</ui-alert
        >
      </div>
    </div>
  </div>
</template>
<style scoped>
.settings-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  margin-top: 25px;
}
</style>
