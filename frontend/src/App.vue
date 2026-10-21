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
  <footer class="footer-records" :class="{ 'editor-footer': editor }"><div><ui-link href="https://beian.mps.gov.cn/#/query/webSearch?code=33021202003929" target="_blank" rel="noopener noreferrer"><img alt="浙公网安备图标" width="13" height="13" src="/beian.png" />浙公网安备33021202003929号</ui-link><ui-link href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">浙ICP备2024118372号-1</ui-link></div><p>By <ui-link href="https://github.com/Gentle-Lijie">Gentle-Lijie</ui-link> · <ui-link href="https://github.com/unnc-aim">UNNC RoboMaster AIM Team</ui-link></p></footer>
  <FeedbackHost />
</template>
<style scoped>
.footer-records{padding:13px 20px 13px 244px;display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:6px 20px;font-size:9px;line-height:1.6;background:var(--background);color:var(--muted);min-height:55px}.footer-records>div{display:flex;flex-wrap:wrap;gap:12px;justify-content:center}.footer-records .ui-link{display:inline-flex;gap:4px;align-items:center}.editor-footer{padding:6px 16px;min-height:30px;font-size:9px;border-top:1px solid var(--border)}:global(body:has(.auth-layout) .footer-records){padding-left:20px}@media(max-width:1000px){.footer-records{padding-left:215px}}@media(max-width:700px){.footer-records{padding-left:20px}}.footer-records img{height:13px;width:13px}
</style>
