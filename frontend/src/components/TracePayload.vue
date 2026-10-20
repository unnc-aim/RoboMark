<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
const props = defineProps({ title: String, value: null, expanded: Boolean })
const text = computed(() => {
  if (props.value == null) return '没有记录'
  if (typeof props.value !== 'string') return JSON.stringify(props.value, null, 2)
  try { return JSON.stringify(JSON.parse(props.value), null, 2) } catch { return props.value }
})
async function copy() {
  try { await navigator.clipboard.writeText(text.value); ElMessage.success('已复制') }
  catch { ElMessage.warning('复制不可用，可展开后选择文本复制') }
}
</script>
<template>
  <details class="trace-payload" :open="expanded">
    <summary><span>{{ title }}</span><el-button link size="small" @click.stop.prevent="copy">复制</el-button></summary>
    <pre>{{ text }}</pre>
  </details>
</template>
<style scoped>
.trace-payload{margin-top:12px;border:1px solid #dde5ef;border-radius:8px;overflow:hidden;background:#f8fafc;min-width:0}.trace-payload summary{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 12px;cursor:pointer;color:#476078;font-size:12px}.trace-payload summary::before{content:'›';font-size:18px}.trace-payload[open] summary::before{transform:rotate(90deg)}.trace-payload summary span{flex:1}.trace-payload pre{margin:0;padding:12px 15px;border-top:1px solid #e4eaf2;max-height:420px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.65;color:#24394e;font:12px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace}
</style>
