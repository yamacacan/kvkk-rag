<script setup>
// Sayfa gecisinde icerik alanini kaplayan yukleme katmani + veri istekleri surerken
// ust-orta "Yükleniyor" rozeti. Kisa islemler icin gecikmeli gosterim (titreme olmasin).
import { computed, ref, watch } from 'vue';
import { useUiStore } from '../stores/ui';

const ui = useUiStore();
const gecisGoster = ref(false);
const istekGoster = ref(false);
let z1 = null, z2 = null;
watch(() => ui.gecis, (a) => {
  clearTimeout(z1);
  if (a) z1 = setTimeout(() => { gecisGoster.value = true; }, 80);
  else gecisGoster.value = false;
}, { immediate: true });
watch(() => ui.aktifIstek > 0, (a) => {
  clearTimeout(z2);
  if (a) z2 = setTimeout(() => { istekGoster.value = true; }, 150);
  else z2 = setTimeout(() => { istekGoster.value = false; }, 120);
}, { immediate: true });
const rozet = computed(() => istekGoster.value && !gecisGoster.value);
</script>

<template>
  <!-- sayfa gecisi: icerik alani -->
  <transition enter-active-class="transition-opacity duration-150" leave-active-class="transition-opacity duration-200" enter-from-class="opacity-0" leave-to-class="opacity-0">
    <div v-if="gecisGoster" class="absolute inset-0 z-30 flex items-start justify-center pt-24 bg-bg-0/70 backdrop-blur-[2px]" aria-busy="true" aria-live="polite">
      <div class="flex items-center gap-3 rounded-xl border border-line bg-bg-1 px-4 py-3 shadow-2xl">
        <span class="relative flex h-5 w-5">
          <span class="absolute inset-0 rounded-full border-2 border-indigo-500/30"></span>
          <span class="absolute inset-0 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></span>
        </span>
        <div class="leading-tight">
          <p class="text-xs font-semibold text-t-1">Sayfa yükleniyor…</p>
          <p class="text-[10.5px] text-t-3">Modül hazırlanıyor</p>
        </div>
      </div>
    </div>
  </transition>
  <!-- veri istekleri: ust-orta rozet -->
  <transition enter-active-class="transition duration-150" leave-active-class="transition duration-200" enter-from-class="opacity-0 -translate-y-2" leave-to-class="opacity-0 -translate-y-2">
    <div v-if="rozet" class="pointer-events-none absolute left-1/2 top-3 z-30 -translate-x-1/2 flex items-center gap-2 rounded-full border border-line bg-bg-1/95 px-3 py-1 text-[11px] font-semibold text-t-2 shadow-lg" aria-live="polite">
      <span class="h-3 w-3 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></span>Yükleniyor…
    </div>
  </transition>
</template>
