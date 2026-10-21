<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import WorkspaceLayout from "../layouts/WorkspaceLayout.vue";
const router = useRouter(),
  currentStep = ref(0);
const steps = [
  {
    title: "选择数据集",
    description:
      "从首页选择需要处理的数据集。通过进度与状态，找到可以继续的工作。",
    tips: [
      "查看数据集总量与已完成数量",
      "人工标注直接进入画布；预标注先进入批次页面",
    ],
  },
  {
    title: "配置目标类别",
    description:
      "每个类别都有独立的名称、颜色、模板和快捷键，画布与对象列表保持一致。",
    tips: [
      "默认画后选择类别，主动选类或单类别时自动应用",
      "使用类别快捷键快速切换标注目标",
    ],
  },
  {
    title: "绘制与调整",
    description: "使用矩形、四点或八点工具标出目标，再检查边缘是否贴合。",
    tips: [
      "V 标注 · H 平移 · 滚轮缩放",
      "拖动对象或角点调整位置与尺寸；Esc 取消当前绘制",
    ],
  },
  {
    title: "保存与审核",
    description: "人工标注保存正式框；预标注先保存草稿，再显式通过审核。",
    tips: [
      "保存草稿不会通过审核",
      "通过并下一张才会将候选结果纳入正式标注；已有正式框保持只读",
    ],
  },
  {
    title: "使用快捷键",
    description: "让常用操作留在手边，减少在画布与面板之间来回切换。",
    tips: [
      "⌘ / Ctrl + S 保存；⌘ / Ctrl + Enter 通过审核",
      "← / → 切换图片；工作台「快捷键」中可自定义操作",
    ],
  },
];
const shortcuts = [
  ["保存标注 / 草稿", "⌘ / Ctrl + S"],
  ["通过并下一张", "⌘ / Ctrl + Enter"],
  ["撤销 / 重做", "⌘ / Ctrl + Z / ⇧ Z"],
  ["选择 / 平移工具", "V / H"],
  ["取消当前绘制", "Esc"],
  ["上一张 / 下一张", "← / →"],
  ["搜索工作空间", "⌘ / Ctrl + K"],
  ["显示帮助", "?"],
];
</script>
<template>
  <WorkspaceLayout
    ><header class="page-heading">
      <div>
        <h1>让标注顺手起来。</h1>
        <p>五个步骤，熟悉从数据集到审核完成的工作流程。</p>
      </div>
      <ui-button type="primary" icon="ArrowRight" @click="router.push('/')"
        >选择数据集开始标注</ui-button
      >
    </header>
    <div class="tutorial-layout">
      <nav class="tutorial-nav" aria-label="教程步骤">
        <ui-button
          v-for="(step, index) in steps"
          :key="step.title"
          variant="ghost"
          :class="{ active: currentStep === index }"
          @click="currentStep = index"
          ><span>{{ index + 1 }}</span
          >{{ step.title }}<ui-icon name="ArrowRight"
        /></ui-button>
      </nav>
      <ui-card class="panel-padding"
        ><div class="section-heading">
          <h2>{{ steps[currentStep].title }}</h2>
          <ui-tag>{{ currentStep + 1 }} / 5</ui-tag>
        </div>
        <p class="tutorial-description">{{ steps[currentStep].description }}</p>
        <div class="tutorial-demo">
          <img
            src="/design/arena-3591.jpg"
            alt="MVM3D 机器人多目标标注示意"
          /><span class="tutorial-box">蓝方机器人</span>
          <div class="demo-toolbar">
            <ui-icon name="MousePointer2" /><ui-icon name="Hand" /><ui-icon
              name="Square"
            /><ui-icon name="Pentagon" />
          </div>
          <small>MVM3D · MIT License · 示例图片</small>
        </div>
        <ul class="tutorial-tips">
          <li v-for="tip in steps[currentStep].tips" :key="tip">{{ tip }}</li>
        </ul>
        <div class="tutorial-actions">
          <ui-button
            icon="ArrowLeft"
            :disabled="currentStep === 0"
            @click="currentStep--"
            >上一步</ui-button
          ><span class="muted">{{ currentStep + 1 }} / 5</span
          ><ui-button
            v-if="currentStep < 4"
            type="primary"
            @click="currentStep++"
            >下一步 <ui-icon name="ArrowRight" /></ui-button
          ><ui-button v-else type="primary" @click="router.push('/')"
            >开始标注</ui-button
          >
        </div></ui-card
      >
    </div>
    <ui-card class="panel-padding shortcut-panel"
      ><div class="section-heading">
        <h2>常用快捷键</h2>
        <span class="form-tip">在工作台中可自定义</span>
      </div>
      <div class="shortcut-grid">
        <div v-for="[label, key] in shortcuts" :key="label">
          <span>{{ label }}</span
          ><ui-kbd>{{ key }}</ui-kbd>
        </div>
      </div></ui-card
    ></WorkspaceLayout
  >
</template>
<style scoped>
.tutorial-layout {
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr);
  gap: var(--space-5);
}
.tutorial-nav {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.tutorial-nav .ui-button {
  justify-content: flex-start;
  padding: var(--space-4);
  font-size: 12px;
  gap: var(--space-4);
}
.tutorial-nav .ui-button > span {
  width: 23px;
  height: 23px;
  border: 1px solid var(--border);
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 10px;
}
.tutorial-nav .ui-button > svg {
  margin-left: auto;
  width: 12px;
}
.tutorial-nav .active {
  background: #edf1ff;
  color: var(--primary);
}
.tutorial-description {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.8;
}
.tutorial-demo {
  position: relative;
  margin: var(--space-5) 0;
  overflow: hidden;
  border-radius: 8px;
  background: #182132;
}
.tutorial-demo > img {
  display: block;
  width: 100%;
  aspect-ratio: 2.5;
  object-fit: cover;
  opacity: 0.9;
}
.tutorial-box {
  position: absolute;
  top: 31%;
  left: 42%;
  width: 19%;
  height: 45%;
  border: 2px solid #7da6ff;
  color: #b9d0ff;
  font-size: 10px;
  padding: 4px;
}
.demo-toolbar {
  position: absolute;
  left: 12px;
  top: 12px;
  background: #1d222bcc;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3);
  color: #cdd5e3;
  border-radius: 6px;
}
.tutorial-demo > small {
  position: absolute;
  right: 10px;
  bottom: 10px;
  font-size: 8px;
  color: #d4dbea;
}
.tutorial-tips {
  font-size: 12px;
  line-height: 2.1;
  color: var(--muted);
  padding-left: 18px;
}
.tutorial-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--space-5);
  border-top: 1px solid var(--border);
  padding-top: var(--space-5);
  font-size: 11px;
}
.shortcut-panel {
  margin-top: var(--space-5);
}
.shortcut-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 var(--space-7);
}
.shortcut-grid > div {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  border-bottom: 1px solid var(--border);
  padding: var(--space-4) 0;
  font-size: 11px;
}
@media (max-width: 900px) {
  .tutorial-layout {
    grid-template-columns: 1fr;
  }
  .tutorial-nav {
    flex-direction: row;
    flex-wrap: wrap;
  }
  .tutorial-nav .ui-button {
    padding: var(--space-2);
    font-size: 11px;
  }
  .tutorial-nav .ui-button > svg {
    display: none;
  }
}
@media (max-width: 600px) {
  .shortcut-grid {
    grid-template-columns: 1fr;
  }
  .tutorial-demo > img {
    aspect-ratio: 1.6;
  }
}
</style>
