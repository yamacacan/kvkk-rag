<script setup>
// Yukleme iskeleti (shimmer). Boyutu Tailwind siniflariyla ver: <Iskelet class="h-4 w-32" />
defineProps({ daire: { type: Boolean, default: false } });
</script>

<template>
  <div class="iskelet" :class="daire ? 'rounded-full' : 'rounded-md'" aria-hidden="true"></div>
</template>
