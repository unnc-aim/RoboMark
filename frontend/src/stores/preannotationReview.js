import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import api from '../utils/api'

const fields = ['category_id','annotation_type','x_center','y_center','width','height',
  'p1_x','p1_y','p2_x','p2_y','p3_x','p3_y','p4_x','p4_y']

export const usePreannotationReviewStore = defineStore('preannotationReview', () => {
  const state = ref(null), task = ref(null), candidates = ref([])
  const loading = ref(false), busy = ref(false), loadError = ref(false)
  const showFormal = ref(true), showCandidates = ref(true)
  const history = ref([]), historyIndex = ref(-1), savedSnapshot = ref('[]')
  const queue = ref({ review_status: 'pending', execution_status: 'succeeded', has_candidates: '' })
  const queueTotal = ref(0), previousId = ref(null), nextId = ref(null)
  let generation = 0
  const image = computed(() => state.value?.image || null)
  const item = computed(() => state.value?.task_image || null)
  const ready = computed(() => item.value?.execution_status === 'succeeded')
  const editable = computed(() => ready.value && ['unreviewed','draft'].includes(item.value.review_status))
  const activeCandidates = computed(() => candidates.value.filter(a => !a.is_deleted))
  const formal = computed(() => state.value?.annotations || [])
  const dirty = computed(() => JSON.stringify(candidates.value) !== savedSnapshot.value)
  const canUndo = computed(() => historyIndex.value > 0)
  const canRedo = computed(() => historyIndex.value < history.value.length - 1)
  const canvasAnnotations = computed(() => [
    ...(showFormal.value ? formal.value.map(a => ({ ...a, id: `formal-${a.id}`, is_readonly: true })) : []),
    ...(showCandidates.value && item.value?.review_status !== 'approved'
      ? activeCandidates.value.map(a => ({ ...a, id: canvasId(a), is_candidate: true, is_readonly: !editable.value })) : [])
  ])
  const endpoint = () => `/preannotation/tasks/${task.value.id}/images/${image.value.id}`
  const canvasId = a => `candidate-${a.id || a.client_id}`

  function apply(data) {
    state.value = data
    candidates.value = data.candidates
    savedSnapshot.value = JSON.stringify(candidates.value)
    history.value = [savedSnapshot.value]
    historyIndex.value = 0
  }
  function record() {
    history.value = history.value.slice(0,historyIndex.value+1)
    history.value.push(JSON.stringify(candidates.value))
    if (history.value.length > 50) history.value.shift()
    historyIndex.value = history.value.length-1
  }
  function undo() { if (editable.value && !busy.value && canUndo.value) candidates.value = JSON.parse(history.value[--historyIndex.value]) }
  function redo() { if (editable.value && !busy.value && canRedo.value) candidates.value = JSON.parse(history.value[++historyIndex.value]) }
  function update(id, changes) {
    if (!editable.value || busy.value) return
    const ann = candidates.value.find(a => canvasId(a) === id)
    if (ann) { Object.assign(ann,changes); record() }
  }
  function remove(id) { update(id,{is_deleted:true}) }
  function add(ann,categoryId) {
    if (!editable.value || busy.value || !categoryId) return
    candidates.value.push({...ann,category_id:categoryId,client_id:crypto.randomUUID(),is_deleted:false,is_manual:true})
    record()
  }
  function params() {
    const values = { task_id: task.value.id, execution_status: queue.value.execution_status }
    if (queue.value.review_status !== 'all') values.review_status = queue.value.review_status
    if (queue.value.has_candidates !== '') values.has_candidates = queue.value.has_candidates
    return values
  }
  async function load(datasetId, taskId, imageId, filters = {}) {
    const token = ++generation
    loading.value = true; loadError.value = false
    state.value = null; task.value = null; candidates.value = []; savedSnapshot.value = '[]'
    history.value = []; historyIndex.value = -1; queueTotal.value = 0
    previousId.value = null; nextId.value = null
    queue.value = { review_status:'pending',execution_status:'succeeded',has_candidates:'',...filters }
    try {
      const info = (await api.get(`/preannotation/tasks/${taskId}`)).data
      if (token !== generation) return
      if (info.dataset_id !== datasetId) throw new Error('批次不属于当前数据集')
      task.value = info
      const rows = (await api.get(`/datasets/${datasetId}/images`,{params:{...params(),page_size:1}})).data
      if (token !== generation) return
      queueTotal.value = rows.total
      const id = imageId || rows.items[0]?.id
      if (id) {
        const data = (await api.get(`/preannotation/tasks/${taskId}/images/${id}`)).data
        if (token !== generation) return
        apply(data)
        await refreshNavigation(datasetId, token)
      }
    } catch (error) {
      if (token === generation) loadError.value = true
      throw error
    } finally { if (token === generation) loading.value = false }
  }
  async function refreshNavigation(datasetId, token = generation) {
    if (!image.value || !task.value) return
    const values = params(), id = image.value.id
    const [before,after] = await Promise.all([
      api.get(`/datasets/${datasetId}/images`,{params:{...values,page_size:1,before_id:id}}),
      api.get(`/datasets/${datasetId}/images`,{params:{...values,page_size:1,after_id:id}})
    ])
    if (token !== generation) return
    previousId.value = before.data.items[0]?.id || null
    nextId.value = after.data.items[0]?.id || null
  }
  async function refreshTask() {
    const token = generation, id = task.value?.id
    if (!id) return
    const info = (await api.get(`/preannotation/tasks/${id}`)).data
    if (token === generation) task.value = info
  }
  async function refreshAfterWrite() {
    // 已成功保存的结果不因进度刷新失败而被当作写入失败。
    try { await refreshTask() } catch (error) { console.warn('刷新审核进度失败', error) }
  }
  async function saveDraft() {
    if (!editable.value || busy.value) return false
    if (!dirty.value) return true
    busy.value = true
    try {
      const annotations = candidates.value.map(a => ({
        ...Object.fromEntries(fields.filter(k=>a[k]!==undefined).map(k=>[k,a[k]])),
        ...(a.id ? {id:a.id} : {}),is_deleted:!!a.is_deleted
      }))
      apply((await api.put(endpoint()+'/draft',{revision:item.value.revision,annotations})).data)
      await refreshAfterWrite()
      return true
    } finally { busy.value = false }
  }
  async function review(action) {
    if (!editable.value || busy.value) return false
    if (action === 'empty' && activeCandidates.value.length) throw new Error('请先删除全部候选框，再确认无目标')
    if (!await saveDraft()) return false
    busy.value = true
    try {
      apply((await api.post(endpoint()+'/review',{
        revision:item.value.revision,image_revision:image.value.annotation_revision,action
      })).data)
      await refreshAfterWrite()
      return true
    } finally { busy.value = false }
  }
  function reset() {
    generation++; state.value = null; task.value = null; candidates.value = []
    savedSnapshot.value = '[]'; history.value = []; historyIndex.value = -1
    loading.value = false; busy.value = false; queueTotal.value = 0
    previousId.value = null; nextId.value = null; loadError.value = false
  }
  return { state,task,image,item,candidates,formal,activeCandidates,canvasAnnotations,dirty,ready,editable,
    loading,busy,loadError,showFormal,showCandidates,queue,queueTotal,previousId,nextId,canUndo,canRedo,
    load,reset,undo,redo,update,remove,add,canvasId,saveDraft,review,refreshTask,refreshNavigation }
})
