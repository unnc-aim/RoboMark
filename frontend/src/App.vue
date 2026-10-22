<script setup>
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import FeedbackHost from './shared/ui/FeedbackHost.vue'
const route = useRoute()
const editor = computed(() => route.name === 'Annotation')
watch(editor, value => document.documentElement.classList.toggle('dark', value), { immediate: true })
</script>
<template>
  <router-view />
  <footer class="footer-records" :class="{ 'editor-footer': editor }"><p><ui-link href="https://github.com/Gentle-Lijie">Gentle-Lijie</ui-link> · <ui-link href="https://github.com/unnc-aim">AIM Robotics @ UNNC</ui-link></p></footer>
  <FeedbackHost />
</template>
<style scoped>
.footer-records{padding:13px 20px 13px 244px;display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:6px 20px;font-size:9px;line-height:1.6;background:var(--background);color:var(--muted);min-height:55px}.footer-records .ui-link{display:inline-flex;gap:4px;align-items:center}.editor-footer{padding:6px 16px;min-height:30px;font-size:9px;border-top:1px solid var(--border)}:global(body:has(.auth-layout) .footer-records){padding-left:20px}@media(max-width:1000px){.footer-records{padding-left:215px}}@media(max-width:700px){.footer-records{padding-left:20px}}
</style>
