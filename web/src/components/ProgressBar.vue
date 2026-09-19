<script setup>
// Ust ilerleme cubugu: sayfa gecisi (tembel yuklenen parca dahil) ve acik API istekleri surdukce gorunur.
import { computed, ref, watch } from 'vue';
import { useUiStore } from '../stores/ui';

const ui = useUiStore();
const aktif = computed(() => ui.gecis || ui.aktifIstek > 0);
const goster = ref(false);
let zamanlayici = null;
// Cok kisa istekler icin titreme olmasin: 120 ms gecikmeyle goster, bitince kisa sure tam dolu kalsin
watch(aktif, (a) => {
  clearTimeout(zamanlayici);
  if (a) zamanlayici = setTimeout(() => { goster.value = true; }, 120);
  else zamanlayici = setTimeout(() => { goster.value = false; }, 200);
}, { immediate: true });
</script>

<template>
  <div class="fixed top-0 left-0 right-0 z-[80] h-[3px] pointer-events-none" aria-hidden="true">
    <transition enter-active-class="transition-opacity duration-150" leave-active-class="transition-opacity duration-300" enter-from-class="opacity-0" leave-to-class="opacity-0">
      <div v-if="goster" class="h-full w-full overflow-hidden bg-indigo-500/20">
        <div class="ilerleme h-full w-1/3 bg-gradient-to-r from-indigo-500 via-violet-400 to-indigo-500 shadow-[0_0_8px_rgba(99,102,241,.8)]"></div>
      </div>
    </transition>
  </div>
</template>
