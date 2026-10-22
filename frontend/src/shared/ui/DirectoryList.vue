<script setup lang="ts">
import { ListboxRoot, ListboxContent, ListboxItem } from "reka-ui";
import { Folder, ChevronRight } from "@lucide/vue";
import type { DirectoryEntry } from "../api/filesystem";
defineProps<{ entries: DirectoryEntry[]; disabled?: boolean }>();
const emit = defineEmits<{ open: [path: string] }>();
</script>
<template>
  <ListboxRoot :disabled="disabled" selection-behavior="replace" class="directory-list">
    <ListboxContent aria-label="服务器子目录">
      <ListboxItem
        v-for="entry in entries"
        :key="entry.path + entry.name"
        :value="entry.path"
        :text-value="entry.name"
        class="directory-entry"
        @select.prevent="!disabled && emit('open', entry.path)"
      >
        <Folder :size="18" aria-hidden="true" />
        <span>{{ entry.name }}</span>
        <ChevronRight :size="15" aria-hidden="true" />
      </ListboxItem>
    </ListboxContent>
  </ListboxRoot>
</template>
<style scoped>
.directory-entry {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
  outline: none;
  font-size: 13px;
}
.directory-entry > span { flex: 1; overflow-wrap: anywhere; }
.directory-entry > svg { flex-shrink: 0; color: var(--muted); }
.directory-entry[data-highlighted], .directory-entry:hover {
  background: var(--surface-muted);
  box-shadow: inset 0 0 0 1px var(--border);
}
.directory-entry[data-disabled] { pointer-events: none; opacity: .5; }
</style>
