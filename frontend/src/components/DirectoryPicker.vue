<script setup lang="ts">
import { computed, onUnmounted, ref, useId, watch } from "vue";
import { listDirectories, type DirectoryListing } from "../shared/api/filesystem";
import { getErrorMessage } from "../utils/apiErrors";
import UiDirectoryList from "../shared/ui/DirectoryList.vue";

const props = defineProps<{ modelValue?: string; label: string }>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();
const pickerId = useId();
const visible = ref(false);
const listing = ref<DirectoryListing | null>(null);
const pathInput = ref("");
const search = ref("");
const showHidden = ref(false);
const loading = ref(false);
const errorMessage = ref("");
const page = computed(() => listing.value ? Math.floor(listing.value.offset / listing.value.limit) + 1 : 1);
let controller: AbortController | undefined;
let generation = 0;
let searchTimer: ReturnType<typeof setTimeout> | undefined;

async function load(path?: string, offset = 0) {
  clearTimeout(searchTimer);
  controller?.abort();
  controller = new AbortController();
  const request = ++generation;
  loading.value = true;
  errorMessage.value = "";
  try {
    const result = await listDirectories({
      path: path || undefined,
      search: search.value.trim(),
      show_hidden: showHidden.value,
      offset,
    }, controller.signal);
    if (request !== generation || !visible.value) return;
    listing.value = result;
    pathInput.value = result.path;
  } catch (error) {
    if (request === generation && visible.value)
      errorMessage.value = await getErrorMessage(error, "服务器目录加载失败");
  } finally {
    if (request === generation) loading.value = false;
  }
}
function navigate(path?: string) {
  search.value = "";
  if (path) pathInput.value = path;
  void load(path);
}
function searchChanged() {
  clearTimeout(searchTimer);
  if (!listing.value) return;
  generation++;
  controller?.abort();
  // Do not allow confirmation while a different directory filter is still pending.
  loading.value = true;
  searchTimer = setTimeout(() => void load(listing.value!.path), 250);
}
function select() {
  if (!listing.value || loading.value || errorMessage.value) return;
  emit("update:modelValue", listing.value.path);
  visible.value = false;
}
function stop() {
  generation++;
  clearTimeout(searchTimer);
  controller?.abort();
  loading.value = false;
}
watch(visible, value => {
  if (!value) return stop();
  listing.value = null;
  search.value = "";
  errorMessage.value = "";
  pathInput.value = props.modelValue?.trim() || "";
  void load(pathInput.value);
});
onUnmounted(stop);
</script>
<template>
  <div class="directory-picker">
    <div class="directory-controls">
      <ui-input
        :model-value="props.modelValue"
        :aria-label="label"
        placeholder="填写或选择服务器目录路径"
        @update:model-value="emit('update:modelValue', $event)"
      />
      <ui-button icon="Folder" :aria-label="`选择服务器${label}`" @click="visible = true">选择目录</ui-button>
    </div>
    <p class="directory-tip">浏览并选择服务器上的目录，也可直接填写绝对路径。</p>
    <ui-dialog v-model="visible" :title="`选择服务器${label}`" width="720px" class="server-directory-dialog">
      <div class="directory-browser">
        <div class="directory-path-bar">
          <ui-input :id="`directory-address-${pickerId}`" v-model="pathInput" aria-label="服务器目录地址" placeholder="输入服务器上的绝对目录路径" @keydown.enter.prevent="navigate(pathInput)" />
          <ui-button :loading="loading" @click="navigate(pathInput)">跳转</ui-button>
        </div>
        <div v-if="listing" class="directory-navigation">
          <ui-button size="small" icon="ArrowLeft" :disabled="loading || !listing.parent_path" @click="navigate(listing.parent_path!)">上一级</ui-button>
          <ui-button v-for="root in listing.roots" :key="root.path" size="small" icon="Server" :disabled="loading" :title="root.path" @click="navigate(root.path)">{{ listing.roots.length > 1 ? root.name : '浏览根目录' }}</ui-button>
          <ui-button size="small" icon="RefreshCw" :disabled="loading" @click="load(listing.path, listing.offset)">刷新</ui-button>
        </div>
        <nav v-if="listing" class="directory-breadcrumbs" aria-label="服务器目录层级">
          <template v-for="(part, index) in listing.breadcrumbs" :key="part.path">
            <span v-if="index" aria-hidden="true">/</span>
            <ui-button link size="small" :disabled="loading" :aria-current="index === listing.breadcrumbs.length - 1 ? 'location' : undefined" @click="navigate(part.path)">{{ part.name }}</ui-button>
          </template>
        </nav>
        <div class="directory-filters">
          <ui-input :id="`directory-filter-${pickerId}`" v-model="search" aria-label="筛选子目录" placeholder="按名称筛选当前目录下的文件夹" :disabled="!listing || !!errorMessage" @input="searchChanged" />
          <ui-checkbox :id="`directory-hidden-${pickerId}`" v-model="showHidden" :disabled="!listing || loading" @change="load(listing?.path)">显示隐藏目录</ui-checkbox>
        </div>
        <ui-alert v-if="errorMessage" type="error" :title="errorMessage">
          <ui-button size="small" @click="load(pathInput)">重试</ui-button>
          <ui-button size="small" @click="navigate()">返回浏览根目录</ui-button>
        </ui-alert>
        <div v-loading="loading" class="directory-contents" :aria-busy="loading">
          <ui-directory-list v-if="listing && !errorMessage && listing.entries.length" :key="listing.path" :entries="listing.entries" :disabled="loading" @open="navigate" />
          <ui-empty v-else-if="!loading && !errorMessage" :description="search ? '没有匹配的子目录' : '此目录没有可浏览的子目录，可直接选择当前目录'" />
          <p v-if="loading" class="directory-loading" role="status">正在读取服务器目录…</p>
        </div>
        <ui-pagination v-if="listing && listing.total > listing.limit && !errorMessage" :current-page="page" :page-size="listing.limit" :total="listing.total" :disabled="loading" @current-change="(value: number) => load(listing!.path, (value - 1) * listing!.limit)" />
      </div>
      <template #footer>
        <div class="directory-selection" role="status"><span>当前目录</span><strong>{{ listing?.path || '尚未加载' }}</strong></div>
        <ui-button @click="visible = false">取消</ui-button>
        <ui-button type="primary" :disabled="!listing || loading || !!errorMessage" @click="select">选择此目录</ui-button>
      </template>
    </ui-dialog>
  </div>
</template>
<style scoped>
.directory-picker { width: 100%; }
.directory-controls, .directory-path-bar { display: flex; gap: var(--space-2); }
.directory-controls > .ui-input-wrap, .directory-path-bar > .ui-input-wrap { flex: 1; min-width: 0; }
.directory-controls > .ui-button, .directory-path-bar > .ui-button { flex-shrink: 0; }
.directory-tip { font-size: 10px; color: var(--muted); margin: 7px 0 0; line-height: 1.7; }
.directory-browser { display: flex; flex-direction: column; gap: var(--space-3); }
.directory-navigation, .directory-breadcrumbs { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.directory-breadcrumbs { font-size: 11px; color: var(--muted); max-height: 76px; overflow-y: auto; }
.directory-breadcrumbs .ui-button { max-width: 100%; overflow-wrap: anywhere; white-space: normal; text-align: left; }
.directory-filters { display: flex; gap: var(--space-4); align-items: center; }
.directory-filters > .ui-input-wrap { flex: 1; min-width: 0; }
.directory-filters > .ui-checkbox { flex-shrink: 0; }
.directory-contents { position: relative; min-height: 180px; max-height: 320px; overflow-y: auto; border: 1px solid var(--border); border-radius: 8px; padding: 4px; }
.directory-loading { padding: 14px; color: var(--muted); font-size: 12px; }
.directory-selection { flex: 1; min-width: 0; margin-right: auto; font-size: 11px; text-align: left; }
.directory-selection > span { display: block; color: var(--muted); margin-bottom: 4px; }
.directory-selection > strong { display: block; font-weight: 500; overflow-wrap: anywhere; }
@media (max-width: 560px) {
  .directory-filters { align-items: flex-start; flex-direction: column; gap: 10px; }
  .directory-filters > .ui-input-wrap { width: 100%; }
  .directory-contents { max-height: 240px; }
  .directory-selection { flex-basis: 100%; }
}
</style>
