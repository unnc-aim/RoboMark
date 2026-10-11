<script setup>
import { computed } from 'vue'
const props = defineProps({ result: Object })
const type = computed(() => props.result?.ok ? 'success' : props.result?.status === 'reachable' ? 'warning' : 'error')
</script>
<template>
  <el-alert v-if="result" :title="result.message" :type="type" :closable="false" show-icon class="connection-result">
    <span class="result-detail">耗时 {{ result.latency_ms }} ms<span v-if="result.http_status"> · HTTP {{ result.http_status }}</span></span>
    <span v-if="result.models?.length" class="result-detail model-list">服务模型：{{ result.models.join('、') }}</span>
    <span class="result-detail">图像识别效果和输出格式请通过抽样验证检查。</span>
  </el-alert>
</template>
<style scoped>
.connection-result{margin:12px 0}.result-detail{display:block;margin-top:5px;line-height:1.6}.model-list{overflow-wrap:anywhere}
</style>
