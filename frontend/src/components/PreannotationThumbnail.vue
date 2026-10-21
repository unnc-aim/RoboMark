<script setup>
import { computed } from "vue";
const props = defineProps({
  image: Object,
  categories: Array,
  imageUrl: String,
  overlay: { type: Boolean, default: true },
});
const color = (id) =>
  props.categories?.find((c) => c.id === id)?.color || "#22c55e";
const shapes = computed(() =>
  (props.image.candidates || []).map((ann) => ({
    ...ann,
    points: [1, 2, 3, 4]
      .map((i) => `${ann[`p${i}_x`] * 1000},${ann[`p${i}_y`] * 1000}`)
      .join(" "),
  })),
);
</script>
<template>
  <div
    class="thumbnail"
    :style="{ aspectRatio: `${image.width || 4}/${image.height || 3}` }"
  >
    <img
      :src="imageUrl || `/api/images/${image.id}/file`"
      :alt="image.filename"
      loading="lazy"
      decoding="async"
    />
    <svg
      v-if="overlay"
      viewBox="0 0 1000 1000"
      preserveAspectRatio="none"
      aria-label="预标注候选框"
    >
      <template v-for="ann in shapes" :key="ann.id">
        <polygon
          v-if="ann.annotation_type === 'parallelogram'"
          :points="ann.points"
          :stroke="color(ann.category_id)"
        />
        <rect
          v-else
          :x="(ann.x_center - ann.width / 2) * 1000"
          :y="(ann.y_center - ann.height / 2) * 1000"
          :width="ann.width * 1000"
          :height="ann.height * 1000"
          :stroke="color(ann.category_id)"
        />
      </template>
    </svg>
  </div>
</template>
<style scoped>
.thumbnail {
  position: relative;
  background: #edf0f4;
  overflow: hidden;
}
.thumbnail img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: fill;
}
.thumbnail svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.thumbnail rect,
.thumbnail polygon {
  fill: #22c55e12;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
}
</style>
