<script setup>
  import { ref, computed, watch, nextTick } from 'vue'

  const props = defineProps({
    visible: Boolean,
    categories: Array,
    currentImageUrl: String,
    pendingAnnotation: Object
  })

  const emit = defineEmits(['select', 'cancel'])

  const searchText = ref('')
  const highlightedIndex = ref(0)
  const inputRef = ref(null)
  const gridRef = ref(null)

  const filteredCategories = computed(() => {
    if (!searchText.value) return props.categories || []
    const query = searchText.value.toLowerCase()
    return (props.categories || []).filter(c => c.name.toLowerCase().includes(query))
  })

  watch(() => props.visible, (val) => {
    if (val) {
      searchText.value = ''
      highlightedIndex.value = 0
      nextTick(() => {
        inputRef.value?.focus()
      })
    }
  })

  function handleKeydown(e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
      e.preventDefault()
      highlightedIndex.value = Math.min(highlightedIndex.value + 1, filteredCategories.value.length - 1)
      scrollToHighlighted()
    } else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
      e.preventDefault()
      highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0)
      scrollToHighlighted()
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (filteredCategories.value.length > 0 && highlightedIndex.value < filteredCategories.value.length) {
        emit('select', filteredCategories.value[highlightedIndex.value])
      }
    } else if (e.key === 'Escape') {
      e.preventDefault()
      emit('cancel')
    }
  }

  function handleInputKeydown(e) {
    if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Enter', 'Escape'].includes(e.key)) {
      highlightedIndex.value = 0
    }
  }

  function selectCategory(category) {
    emit('select', category)
  }

  function scrollToHighlighted() {
    nextTick(() => {
      if (gridRef.value) {
        const items = gridRef.value.querySelectorAll('.category-card')
        if (items[highlightedIndex.value]) {
          items[highlightedIndex.value].scrollIntoView({ block: 'nearest' })
        }
      }
    })
  }
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="popup-overlay" @click.self="emit('cancel')">
      <div class="popup-container" @keydown="handleKeydown">
        <!-- 左侧：当前图片预览 -->
        <div class="left-panel">
          <div class="panel-label">当前图片</div>
          <div class="image-preview">
            <img v-if="currentImageUrl" :src="currentImageUrl" alt="当前图片" />
            <div v-if="pendingAnnotation" class="annotation-indicator">
              <span class="indicator-dot"></span>
              已绘制标注
            </div>
          </div>
        </div>

        <!-- 右侧：类别选择 -->
        <div class="right-panel">
          <div class="panel-header">
            <span class="panel-title">选择类别</span>
            <span class="panel-hint">输入过滤 / 方向键 / Enter</span>
          </div>
          <div class="search-bar">
            <input ref="inputRef" v-model="searchText" placeholder="搜索类别..." class="search-input"
              @keydown="handleInputKeydown" />
          </div>
          <div class="category-grid" ref="gridRef">
            <div v-for="(cat, idx) in filteredCategories" :key="cat.id" class="category-card"
              :class="{ highlighted: idx === highlightedIndex }" @click="selectCategory(cat)"
              @mouseenter="highlightedIndex = idx">
              <div class="card-image">
                <img v-if="cat.template_image_path" :src="`/api/categories/${cat.id}/template-image`" :alt="cat.name" />
                <div v-else class="color-placeholder" :style="{ background: cat.color }">
                  {{ cat.name.charAt(0) }}
                </div>
              </div>
              <div class="card-label">
                <span class="color-dot" :style="{ background: cat.color }"></span>
                <span class="name">{{ cat.name }}</span>
              </div>
            </div>
            <div v-if="filteredCategories.length === 0" class="empty-tip">
              无匹配类别
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
  .popup-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
  }

  .popup-container {
    background: #1a1a2e;
    border: 1px solid #333;
    border-radius: 16px;
    display: flex;
    width: 70vw;
    height: 70vh;
    box-shadow: 0 12px 48px rgba(0, 0, 0, 0.7);
    overflow: hidden;
  }

  /* 左侧图片预览 */
  .left-panel {
    flex: 2;
    background: #111;
    display: flex;
    flex-direction: column;
    border-right: 1px solid #2a2a3e;
    min-width: 0;
  }

  .panel-label {
    padding: 12px 16px;
    color: #888;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #2a2a3e;
  }

  .image-preview {
    flex: 1;
    /* width: 10%; */
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 12px;
    position: relative;
  }

  .image-preview img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    border-radius: 6px;
  }

  .annotation-indicator {
    position: absolute;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    background: rgba(0, 0, 0, 0.7);
    border-radius: 20px;
    color: #67c23a;
    font-size: 12px;
  }

  .indicator-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #67c23a;
  }

  /* 右侧类别选择 */
  .right-panel {
    flex: 5;
    display: flex;
    flex-direction: column;
    min-width: 0;
    overflow: hidden;
  }

  .panel-header {
    padding: 12px 16px 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .panel-title {
    color: #fff;
    font-size: 15px;
    font-weight: 600;
  }

  .panel-hint {
    color: #666;
    font-size: 11px;
  }

  .search-bar {
    padding: 4px 16px 10px;
  }

  .search-input {
    width: 100%;
    padding: 8px 12px;
    background: #16213e;
    border: 1px solid #333;
    border-radius: 8px;
    color: #fff;
    font-size: 13px;
    outline: none;
    box-sizing: border-box;
  }

  .search-input::placeholder {
    color: #555;
  }

  .search-input:focus {
    border-color: #409EFF;
  }

  .category-grid {
    flex: 1;
    overflow-y: auto;
    padding: 4px 10px 10px;
    display: grid;
    grid-template-columns: repeat(10, 1fr);
    gap: 6px;
    align-content: start;
  }

  .category-card {
    background: #16213e;
    border: 2px solid transparent;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .category-card:hover {
    background: #1e2d50;
  }

  .category-card.highlighted {
    border-color: #409EFF;
    background: #0f3460;
  }

  .card-image {
    width: 100%;
    aspect-ratio: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #0f3460;
    padding: 2px;
  }

  .card-image img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
  }

  .color-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.6);
  }

  .card-label {
    padding: 4px 6px;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .color-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .card-label .name {
    color: #ccc;
    font-size: 11px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .category-card.highlighted .card-label .name {
    color: #fff;
  }

  .empty-tip {
    grid-column: 1 / -1;
    text-align: center;
    color: #666;
    padding: 32px;
    font-size: 14px;
  }
</style>
