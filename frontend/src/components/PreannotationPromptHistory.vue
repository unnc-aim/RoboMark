<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import api from '../utils/api'

const props=defineProps({modelValue:Boolean,datasetId:Number})
const emit=defineEmits(['update:modelValue','fill','closed'])
const visible=computed({get:()=>props.modelValue,set:value=>emit('update:modelValue',value)})
const query=ref(''),scope=ref('dataset'),page=ref(1),items=ref([]),total=ref(0),selected=ref(null)
const loading=ref(false),failed=ref(false)
let requestId=0,searchTimer
const characters=computed(()=>Array.from(selected.value?.prompt || '').length)
const canFill=computed(()=>!loading.value && !!selected.value && characters.value<=12000)

async function load() {
  const request=++requestId
  loading.value=true;failed.value=false
  try {
    const result=(await api.get(`/datasets/${props.datasetId}/preannotation-prompts`,{params:{scope:scope.value,q:query.value.trim(),page:page.value,page_size:10}})).data
    if(request!==requestId || !visible.value) return
    items.value=result.items;total.value=result.total;selected.value=items.value[0] || null
  } catch {if(request===requestId) {failed.value=true;items.value=[];total.value=0;selected.value=null}}
  finally {if(request===requestId) loading.value=false}
}
function reload(debounce=false) {
  clearTimeout(searchTimer);requestId++;page.value=1;items.value=[];selected.value=null;loading.value=true
  if(debounce) searchTimer=setTimeout(load,250)
  else load()
}
function searchInput() {reload(true)}
function pageChanged() {selected.value=null;load()}
function fill(item=selected.value) {
  if(loading.value || !item || Array.from(item.prompt).length>12000) return
  emit('fill',item.prompt);visible.value=false
}
function date(value) {return value?new Date(value).toLocaleString('zh-CN',{hour12:false}):'—'}
watch(()=>[props.modelValue,props.datasetId],([open])=>{
  clearTimeout(searchTimer);requestId++;loading.value=false
  if(open) {query.value='';scope.value='dataset';page.value=1;items.value=[];selected.value=null;total.value=0;load()}
})
onUnmounted(()=>{clearTimeout(searchTimer);requestId++})
</script>

<template>
  <el-dialog v-model="visible" class="prompt-history-dialog" title="历史 Prompt" width="min(960px, 96vw)" top="6vh" @closed="emit('closed')">
    <div class="history-toolbar">
      <el-radio-group v-model="scope" size="small" aria-label="历史范围" @change="reload()"><el-radio-button value="dataset">当前数据集</el-radio-button><el-radio-button value="mine">我的全部数据集</el-radio-button></el-radio-group>
      <el-input v-model="query" placeholder="搜索历史 Prompt，支持关键词" aria-label="搜索历史 Prompt" clearable :maxlength="256" prefix-icon="Search" @input="searchInput" @keyup.enter="reload()" />
    </div>
    <p class="history-hint">相同文本合并展示，按最近使用排序。填入后仍可编辑。</p>
    <div class="history-body" v-loading="loading">
      <div class="history-results">
        <div class="result-count">{{ total }} 条历史 Prompt</div>
        <el-empty v-if="!loading && !items.length" :image-size="60" :description="failed?'历史加载失败':query.trim()?'没有匹配的 Prompt':'还没有可复用的 Prompt'">
          <el-button v-if="failed" size="small" @click="load">重试加载</el-button>
        </el-empty>
        <article v-for="item in items" :key="item.task_id" class="history-item" :class="{selected:selected?.task_id===item.task_id}">
          <button class="history-select" :aria-label="`预览批次 #${item.task_id} 的 Prompt`" @click="selected=item">
            <span class="item-source">{{ item.dataset_name }} <span>批次 #{{ item.task_id }} · {{ item.is_sample?'抽样':'全量' }}</span></span>
            <span class="prompt-snippet">{{ item.prompt }}</span>
            <span class="item-meta">{{ date(item.last_used_at) }} · 用过 {{ item.usage_count }} 次</span>
          </button>
          <el-button link type="primary" size="small" class="item-fill" :disabled="loading || Array.from(item.prompt).length>12000" :aria-label="`填入批次 #${item.task_id} 的 Prompt`" @click="fill(item)">填入</el-button>
        </article>
        <el-pagination v-if="total>10" v-model:current-page="page" :total="total" :page-size="10" layout="prev,pager,next" @current-change="pageChanged" />
      </div>
      <section class="prompt-preview" aria-label="历史 Prompt 全文预览">
        <template v-if="selected"><header><strong>完整内容</strong><span>{{ characters.toLocaleString('zh-CN') }} 字</span></header><div class="preview-source">{{ selected.dataset_name }} · {{ selected.username }} · 批次 #{{ selected.task_id }}</div><pre>{{ selected.prompt }}</pre><p v-if="characters>12000" class="length-warning">内容超过当前 12,000 字限制，无法直接填入。</p></template>
        <div v-else class="preview-placeholder">选择一条历史记录查看完整内容</div>
      </section>
    </div>
    <template #footer><span class="footer-hint">填充后可继续编辑，再提交预标注任务。</span><el-button @click="visible=false">取消</el-button><el-button type="primary" :disabled="!canFill" @click="fill()">填入 Prompt</el-button></template>
  </el-dialog>
</template>

<style scoped>
:global(.prompt-history-dialog){display:flex;flex-direction:column;max-height:88dvh}:global(.prompt-history-dialog .el-dialog__body){min-height:0;overflow-y:auto}.history-toolbar{display:flex;gap:14px;align-items:center}.history-toolbar .el-radio-group{flex-shrink:0}.history-toolbar .el-input{flex:1}.history-hint{font-size:12px;color:#8a97a7;margin:12px 0 18px}.history-body{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;min-height:320px;align-items:start}.history-results{min-width:0;max-height:53dvh;overflow:auto;padding-right:4px}.result-count{font-size:12px;color:#8a97a7;margin:0 0 12px}.history-item{position:relative;border:1px solid #e1e7ef;border-radius:8px;margin-bottom:9px;background:#fff}.history-item.selected{border-color:#94bce8;background:#f4f8fe}.history-select{display:block;text-align:left;border:0;background:none;padding:13px 54px 13px 13px;width:100%;color:inherit;cursor:pointer;font:inherit}.history-select:focus-visible{outline:2px solid #409eff;outline-offset:-2px;border-radius:8px}.item-source{font-size:11px;display:block;color:#597697;line-height:1.7;overflow-wrap:anywhere}.item-source>span{color:#95a1b1}.prompt-snippet{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:13px;line-height:1.7;margin:8px 0;white-space:pre-wrap;overflow-wrap:anywhere}.item-meta{display:block;font-size:10px;color:#8c9aab;line-height:1.7}.item-fill{position:absolute;right:12px;top:44px}.history-results .el-pagination{justify-content:center;margin:16px 0 6px}.prompt-preview{position:sticky;top:0;border:1px solid #e1e7ef;background:#f8fafc;border-radius:8px;padding:17px;min-width:0;max-height:53dvh;overflow:auto}.prompt-preview header{display:flex;justify-content:space-between;gap:12px;font-size:12px;color:#526881}.prompt-preview header span{font-size:11px;color:#99a6b5}.preview-source{font-size:11px;color:#8c9aab;line-height:1.8;margin-top:12px;overflow-wrap:anywhere}.prompt-preview pre{font:inherit;font-size:13px;line-height:1.9;white-space:pre-wrap;overflow-wrap:anywhere;color:#34485f;margin:16px 0 0}.preview-placeholder{font-size:12px;color:#a1adbb;display:flex;align-items:center;justify-content:center;min-height:260px}.footer-hint{font-size:12px;color:#8c9aab;float:left;margin-top:9px}.length-warning{color:#bd663f;font-size:12px;margin-bottom:0}@media(max-width:650px){.history-toolbar{flex-direction:column;align-items:stretch}.history-body{grid-template-columns:minmax(0,1fr);min-height:0}.history-results{max-height:34dvh}.prompt-preview{position:static;max-height:26dvh}.preview-placeholder{min-height:80px}.footer-hint{float:none;display:block;text-align:left;margin:0 0 12px}.history-hint{line-height:1.7}}
</style>
