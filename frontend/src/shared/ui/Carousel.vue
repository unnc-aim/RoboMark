<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, computed } from "vue";
import emblaCarouselVue from "embla-carousel-vue";
import Autoplay from "embla-carousel-autoplay";
import { UiButton, UiIcon } from "./index";

interface Slide {
  src: string;
  alt: string;
}
const props = withDefaults(
  defineProps<{
    slides: Slide[];
    label?: string;
    delay?: number;
  }>(),
  { label: "图片轮播", delay: 4500 },
);
const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
const autoplay = Autoplay({
  delay: props.delay,
  playOnInit: !motionPreference.matches,
  stopOnInteraction: false,
  stopOnMouseEnter: true,
  stopOnFocusIn: true,
});
const [viewport, carousel] = emblaCarouselVue(
  {
    loop: true,
    align: "center",
    breakpoints: { "(max-width: 650px)": { active: false } },
  },
  [autoplay],
);
const selected = ref(0);
const loadedIndexes = ref(new Set<number>());
function loadNearby(index: number) {
  const total = props.slides.length;
  if (!total) return;
  for (const offset of [-1, 0, 1]) {
    loadedIndexes.value.add((index + offset + total) % total);
  }
}
watch(
  () => props.slides,
  () => loadNearby(selected.value),
  { immediate: true },
);
const visibleDots = computed(() => {
  const count = Math.min(7, props.slides.length);
  const start = Math.min(
    Math.max(0, selected.value - 3),
    props.slides.length - count,
  );
  return Array.from({ length: count }, (_, index) => start + index);
});
watch(carousel, (api, _, onCleanup) => {
  if (!api) return;
  const update = () => {
    selected.value = api.selectedScrollSnap();
    loadNearby(selected.value);
  };
  update();
  api.on("select", update).on("reInit", update);
  onCleanup(() => {
    api.off("select", update).off("reInit", update);
  });
});
function updateMotion() {
  if (motionPreference.matches) autoplay.stop();
  else if (!document.hidden) autoplay.play();
}
function previous() {
  carousel.value?.scrollPrev();
}
function next() {
  carousel.value?.scrollNext();
}
function keydown(event: KeyboardEvent) {
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    previous();
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    next();
  }
}
onMounted(() => motionPreference.addEventListener("change", updateMotion));
onUnmounted(() => motionPreference.removeEventListener("change", updateMotion));
</script>

<template>
  <div
    class="ui-carousel"
    role="region"
    aria-roledescription="轮播图"
    :aria-label="label"
    tabindex="0"
    @keydown="keydown"
  >
    <div ref="viewport" class="ui-carousel-viewport">
      <div class="ui-carousel-track">
        <div
          v-for="(slide, index) in slides"
          :key="slide.src"
          class="ui-carousel-slide"
          role="group"
          aria-roledescription="幻灯片"
          :aria-label="`${index + 1} / ${slides.length}`"
          :aria-hidden="index !== selected"
        >
          <img
            v-if="loadedIndexes.has(index)"
            :src="slide.src"
            :alt="slide.alt"
            width="640"
            height="977"
            :fetchpriority="index === 0 ? 'high' : 'auto'"
            decoding="async"
            draggable="false"
          />
        </div>
      </div>
    </div>
    <template v-if="slides.length > 1">
      <UiButton
        variant="ghost"
        circle
        class="ui-carousel-arrow previous"
        aria-label="上一张卡牌"
        @click="previous"
        ><UiIcon name="ArrowLeft" :size="18"
      /></UiButton>
      <UiButton
        variant="ghost"
        circle
        class="ui-carousel-arrow next"
        aria-label="下一张卡牌"
        @click="next"
        ><UiIcon name="ArrowRight" :size="18"
      /></UiButton>
      <div
        class="ui-carousel-dots"
        role="group"
        :aria-label="`选择卡牌，共 ${slides.length} 张`"
      >
        <UiButton
          v-for="index in visibleDots"
          :key="index"
          variant="ghost"
          class="ui-carousel-dot"
          :class="{ active: index === selected }"
          :aria-label="`查看第 ${index + 1} 张卡牌`"
          :aria-pressed="index === selected"
          @click="carousel?.scrollTo(index)"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.ui-carousel {
  position: relative;
  width: 100%;
  height: 100%;
  min-width: 0;
  outline-offset: -3px;
}
.ui-carousel-viewport {
  position: absolute;
  inset: 34px 44px 66px;
  overflow: hidden;
  touch-action: pan-y pinch-zoom;
}
.ui-carousel-track {
  display: flex;
  height: 100%;
}
.ui-carousel-slide {
  flex: 0 0 100%;
  min-width: 0;
  height: 100%;
}
.ui-carousel-slide img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  user-select: none;
}
.ui-carousel-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  color: #c4b776;
  border-radius: 50%;
  background: #ffffff07;
  border: 1px solid #d9c97a22;
}
.ui-carousel-arrow:hover {
  background: #d9c97a17;
  color: #f0dda1;
  border-color: #d9c97a55;
}
.ui-carousel-arrow.previous {
  left: 14px;
}
.ui-carousel-arrow.next {
  right: 14px;
}
.ui-carousel-dots {
  position: absolute;
  bottom: 26px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 12px;
}
.ui-carousel-dot {
  padding: 0;
  width: 6px;
  height: 6px;
  min-height: 6px;
  border: 0;
  border-radius: 50%;
  background: #ffffff38;
}
.ui-carousel-dot:hover {
  background: #d9c97a99;
}
.ui-carousel-dot.active {
  background: #d9c97a;
}
@media (max-width: 950px) {
  .ui-carousel-viewport {
    inset: 32px 26px 64px;
  }
  .ui-carousel-arrow.previous {
    left: 10px;
  }
  .ui-carousel-arrow.next {
    right: 10px;
  }
  .ui-carousel-arrow {
    width: 29px;
    min-height: 29px;
    padding: 5px;
  }
}
</style>
