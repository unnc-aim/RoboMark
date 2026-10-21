<script setup lang="ts">
import { ref } from "vue";
const props = defineProps<{ modelValue?: string; label: string }>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();
const selection = ref("");
function selected(file: any, files: any[]) {
  const directory = file.raw.webkitRelativePath.split("/")[0];
  selection.value = `${directory} · 已读取 ${files.length} 个文件的信息`;
  emit("update:modelValue", directory);
}
</script>
<template>
  <div class="directory-picker">
    <div class="directory-controls">
      <ui-input
        :model-value="props.modelValue"
        :aria-label="label"
        placeholder="填写服务器目录路径"
        @update:model-value="emit('update:modelValue', $event)"
      /><ui-upload
        directory
        :auto-upload="false"
        :show-file-list="false"
        :on-change="selected"
        ><ui-button icon="Folder">选择目录</ui-button></ui-upload
      >
    </div>
    <p v-if="selection">{{ selection }}</p>
    <p>
      本机选择仅提供目录名和文件列表。服务器读取数据需要填写服务器可访问的完整路径。
    </p>
  </div>
</template>
<style scoped>
.directory-picker {
  width: 100%;
}
.directory-controls {
  display: flex;
  gap: 8px;
}
.directory-controls > .ui-input-wrap {
  flex: 1;
}
.directory-picker p {
  font-size: 10px;
  color: var(--muted);
  margin: 7px 0 0;
  line-height: 1.7;
}
</style>
