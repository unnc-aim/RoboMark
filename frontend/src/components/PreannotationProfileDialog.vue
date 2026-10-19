<script setup>
import { ref, watch, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '../stores/user'
import api from '../utils/api'
import ConnectionTestResult from './ConnectionTestResult.vue'

const props = defineProps({ modelValue: Boolean, profile: Object })
const emit = defineEmits(['update:modelValue', 'saved'])
const user = useUserStore()
const visible = computed({ get: () => props.modelValue, set: v => emit('update:modelValue', v) })
const form = ref({})
const busy = ref(false)
const testing = ref(false), testResult = ref(null)
const connectionFeedback = ref(null)
let testGeneration = 0
const templateText = ref('')
const headersText = ref('{}')
const mappingText = ref('{}')
const defaultTemplate = { image: '{{image.data_url}}', prompt: '{{prompt}}', model: '{{model}}', schema: '{{output_schema}}' }

watch(() => props.modelValue, value => {
  testGeneration++
  testing.value = false
  testResult.value = null
  if (!value) return
  form.value = { name: '', endpoint: '', interface_type: 'openai', http_method: 'POST', model: '', api_key: '',
    clear_credentials: false, response_path: 'choices[0].message.content', annotations_path: 'annotations',
    coordinate_system: 'normalized', box_format: 'center', structured_output: 'none', timeout_seconds: 120,
    max_attempts: 3, is_shared: false, ...props.profile }
  form.value.api_key = ''
  templateText.value = JSON.stringify(props.profile?.request_template || defaultTemplate, null, 2)
  headersText.value = JSON.stringify(props.profile?.headers || {}, null, 2)
  mappingText.value = JSON.stringify(props.profile?.field_mapping || {}, null, 2)
}, { immediate: true })

function changeInterface(value) {
  form.value.response_path = value === 'openai' ? 'choices[0].message.content' : ''
}

watch([form, templateText, headersText, mappingText], () => { testResult.value = null }, { deep: true })

function payloadForRequest(test = false) {
  let payload
    payload = Object.fromEntries(['name', 'endpoint', 'interface_type', 'http_method', 'model', 'response_path', 'annotations_path',
      'coordinate_system', 'box_format', 'structured_output', 'timeout_seconds', 'max_attempts', 'is_shared', 'clear_credentials'].map(k => [k, form.value[k]]))
    payload.api_key = form.value.api_key || null
    payload.headers = JSON.parse(headersText.value)
    payload.field_mapping = JSON.parse(mappingText.value)
    payload.request_template = form.value.interface_type === 'http_json' ? JSON.parse(templateText.value) : {}
    if (test && !payload.name.trim()) payload.name = '连接测试'
  return payload
}

async function testConnection() {
  if (!form.value.endpoint.trim()) return ElMessage.warning('请先填写 endpoint')
  let payload
  try { payload = payloadForRequest(true) }
  catch { return ElMessage.error('请求头、字段映射和请求模板必须是有效 JSON') }
  const generation = ++testGeneration
  testing.value = true
  testResult.value = null
  try {
    const response = await api.post('/preannotation/profiles/test', { profile: payload, existing_profile_id: props.profile?.id || null })
    if (generation === testGeneration) {
      testResult.value = response.data
      await nextTick()
      if (generation === testGeneration && visible.value) connectionFeedback.value?.$el?.scrollIntoView?.({ block: 'nearest' })
    }
  } catch { /* 错误统一由拦截器提示 */ }
  finally { if (generation === testGeneration) testing.value = false }
}

async function save() {
  if (!form.value.name.trim() || !form.value.endpoint.trim()) return ElMessage.warning('请填写名称和 endpoint')
  let payload
  try { payload = payloadForRequest() }
  catch { return ElMessage.error('请求头、字段映射和请求模板必须是有效 JSON') }
  busy.value = true
  try {
    const response = props.profile
      ? await api.put(`/preannotation/profiles/${props.profile.id}`, payload)
      : await api.post('/preannotation/profiles', payload)
    ElMessage.success('接口配置已保存')
    emit('saved', response.data)
    visible.value = false
  } finally { busy.value = false }
}

async function remove() {
  try { await ElMessageBox.confirm('停用后，未完成任务将无法使用此配置继续推理。', '停用接口配置', { type: 'warning' }) }
  catch { return }
  busy.value = true
  try {
    await api.delete(`/preannotation/profiles/${props.profile.id}`)
    emit('saved', null)
    visible.value = false
  } finally { busy.value = false }
}
</script>

<template>
  <el-dialog v-model="visible" class="connection-profile-dialog" top="5vh" :title="profile ? '编辑推理接口' : '添加推理接口'" width="min(720px, 94vw)" :close-on-click-modal="false">
    <el-form label-position="top" class="profile-form" :disabled="busy || testing" @submit.prevent="save">
      <div class="two-cols">
        <el-form-item label="配置名称"><el-input v-model="form.name" placeholder="例如：局域网 vLLM" /></el-form-item>
        <el-form-item label="接口格式"><el-select v-model="form.interface_type" @change="changeInterface"><el-option label="OpenAI 兼容" value="openai" /><el-option label="自定义 HTTP JSON" value="http_json" /></el-select></el-form-item>
      </div>
      <el-form-item label="Endpoint（完整请求地址）"><el-input v-model="form.endpoint" placeholder="http://server:8000/v1/chat/completions" /></el-form-item>
      <div class="two-cols">
        <el-form-item label="模型名"><el-input v-model="form.model" placeholder="服务中的 model 名称" /></el-form-item>
        <el-form-item :label="profile?.has_api_key ? 'API Key（已保存，留空保留）' : 'API Key（可选）'"><el-input v-model="form.api_key" type="password" show-password autocomplete="new-password" /></el-form-item>
      </div>
      <el-form-item label="请求头 JSON"><el-input v-model="headersText" type="textarea" :rows="3" /><small>已有值显示为 [已保存]；保留该值可保留原请求头。</small></el-form-item>
      <el-checkbox v-model="form.clear_credentials">清除已保存的 API Key 和请求头</el-checkbox>
      <template v-if="form.interface_type === 'http_json'">
        <el-form-item label="HTTP 方法"><el-select v-model="form.http_method"><el-option value="POST" /><el-option value="PUT" /></el-select></el-form-item>
        <el-form-item label="请求模板 JSON"><el-input v-model="templateText" type="textarea" :rows="7" /><small v-pre>占位符：{{image.data_url}}、{{prompt}}、{{user_prompt}}、{{categories}}、{{output_schema}}、{{model}}。完整占位符保留对象或数组类型。</small></el-form-item>
      </template>
      <div class="two-cols">
        <el-form-item label="响应提取路径"><el-input v-model="form.response_path" placeholder="留空使用整个响应" /></el-form-item>
        <el-form-item label="候选数组路径"><el-input v-model="form.annotations_path" placeholder="annotations；顶层数组可留空" /></el-form-item>
        <el-form-item label="模型输出坐标"><el-select v-model="form.coordinate_system"><el-option label="归一化 0–1" value="normalized" /><el-option label="原图像素" value="pixels" /><el-option label="相对坐标 0–1000" value="relative_1000" /></el-select></el-form-item>
        <el-form-item label="矩形输出格式"><el-select v-model="form.box_format"><el-option label="中心点 + 宽高" value="center" /><el-option label="bbox: [x1, y1, x2, y2]" value="xyxy" /></el-select></el-form-item>
      </div>
      <el-form-item label="字段映射 JSON"><el-input v-model="mappingText" type="textarea" :rows="3" placeholder='例如：{"bbox":"bbox_2d","label":"label"}' /><small>键为平台字段，值为模型输出中每个对象的字段路径；可用类别名称 label 映射类别。</small></el-form-item>
      <el-form-item v-if="form.interface_type === 'openai'" label="结构化输出"><el-select v-model="form.structured_output"><el-option label="Prompt 约束" value="none" /><el-option label="response_format / JSON Schema" value="response_format" /><el-option label="vLLM structured_outputs" value="vllm" /></el-select></el-form-item>
      <div class="two-cols">
        <el-form-item label="连接 / 发送超时（秒）"><el-input-number v-model="form.timeout_seconds" :min="5" :max="600" /><small>不限制模型响应的总耗时与读取等待，可在任务页手动取消。</small></el-form-item>
        <el-form-item label="最大尝试次数"><el-input-number v-model="form.max_attempts" :min="1" :max="5" /></el-form-item>
      </div>
      <el-checkbox v-if="user.isAdmin" v-model="form.is_shared">共享给其他用户</el-checkbox>
    </el-form>
    <ConnectionTestResult ref="connectionFeedback" :result="testResult" />
    <template #footer>
      <el-button v-if="profile" type="danger" plain :disabled="busy || testing" @click="remove">停用配置</el-button>
      <el-button :loading="testing" :disabled="busy" @click="testConnection">测试连接</el-button>
      <el-button @click="visible = false">取消</el-button><el-button type="primary" :loading="busy" :disabled="testing" @click="save">保存配置</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
:global(.connection-profile-dialog){max-height:90vh;display:flex;flex-direction:column}
:global(.connection-profile-dialog .el-dialog__body){min-height:0;overflow-y:auto;flex:1}
:global(.connection-profile-dialog .el-dialog__header),:global(.connection-profile-dialog .el-dialog__footer){flex-shrink:0}
.two-cols{display:grid;grid-template-columns:1fr 1fr;gap:0 20px}.profile-form :deep(.el-select){width:100%}.profile-form small{display:block;color:#6b7280;line-height:1.7;margin-top:6px}.profile-form :deep(textarea){font-family:monospace}.profile-form>.el-checkbox{margin-bottom:18px}@media(max-width:600px){.two-cols{grid-template-columns:1fr}}
</style>
