<script setup lang="ts">
import logo from "../assets/brand/aim-premium.png";
</script>

<template>
  <img
    class="brand-logo"
    :src="logo"
    alt="AIM Premium"
    width="880"
    height="378"
    decoding="async"
  />
</template>

<style scoped>
.brand-logo {
  display: block;
  width: 128px;
  height: auto;
  flex-shrink: 0;
  object-fit: contain;
}
:global(.dark) .brand-logo {
  filter: invert(1);
}
</style>
