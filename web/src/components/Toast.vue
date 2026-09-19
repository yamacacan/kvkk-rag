<script setup>
// Sag ust toast yigini: sol renk seridi, ikon, baslik + mesaj, kapat, otomatik gizlenme
// cubugu (uzerine gelince durur). Kaynak: ui.toastlar; ui.toast()/ui.bildir() ile eklenir.
import { onBeforeUnmount, watch } from 'vue';
import { useUiStore } from '../stores/ui';

const ui = useUiStore();
const TUR = {
  ok: { serit: 'border-l-emerald-500', kutu: 'bg-emerald-500/15 text-emerald-400', cubuk: 'bg-emerald-500', ikon: 'circle-check' },
  hata: { serit: 'border-l-rose-500', kutu: 'bg-rose-500/15 text-rose-400', cubuk: 'bg-rose-500', ikon: 'circle-xmark' },
  uyari: { serit: 'border-l-amber-500', kutu: 'bg-amber-500/15 text-amber-400', cubuk: 'bg-amber-500', ikon: 'triangle-exclamation' },
  bilgi: { serit: 'border-l-sky-500', kutu: 'bg-sky-500/15 text-sky-400', cubuk: 'bg-sky-500', ikon: 'bell' },
};
const stil = (t) => TUR[t.tur] || TUR.bilgi;

// Her toast icin zamanlayici: sure dolunca kapanir; hover'da (CSS animasyonu durdugu icin) uzatilir
const zamanlayicilar = new Map();
function kur(t) {
  if (!t.sure || zamanlayicilar.has(t.id)) return;
  zamanlayicilar.set(t.id, { kalan: t.sure, bas: Date.now(), id: setTimeout(() => ui.toastKapat(t.id), t.sure) });
}
function durdur(t) {
  const z = zamanlayicilar.get(t.id); if (!z) return;
  clearTimeout(z.id); z.kalan = Math.max(600, z.kalan - (Date.now() - z.bas)); z.id = null;
}
function surdur(t) {
  const z = zamanlayicilar.get(t.id); if (!z || z.id) return;
  z.bas = Date.now(); z.id = setTimeout(() => ui.toastKapat(t.id), z.kalan);
}
watch(() => ui.toastlar.map((t) => t.id), (ids) => {
  ui.toastlar.forEach(kur);
  [...zamanlayicilar.keys()].forEach((id) => { if (!ids.includes(id)) { clearTimeout(zamanlayicilar.get(id).id); zamanlayicilar.delete(id); } });
}, { immediate: true });
onBeforeUnmount(() => zamanlayicilar.forEach((z) => clearTimeout(z.id)));
</script>

<template>
  <div class="fixed top-4 right-4 z-[85] flex flex-col gap-2 w-[min(380px,calc(100vw-2rem))] pointer-events-none" aria-live="polite">
    <transition-group enter-active-class="transition duration-200 ease-out" enter-from-class="opacity-0 translate-x-6" leave-active-class="transition duration-150 ease-in" leave-to-class="opacity-0 translate-x-6 scale-95" move-class="transition duration-200">
      <div v-for="t in ui.toastlar" :key="t.id" class="pointer-events-auto relative overflow-hidden rounded-xl border border-line border-l-4 bg-bg-1 shadow-2xl p-3.5" :class="stil(t).serit" role="status"
        @mouseenter="durdur(t)" @mouseleave="surdur(t)">
        <div class="flex items-start justify-between gap-3">
          <div class="flex items-start gap-3 min-w-0">
            <div class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg" :class="stil(t).kutu"><FaIcon :icon="stil(t).ikon" class="h-3.5 w-3.5" /></div>
            <div class="min-w-0">
              <h4 v-if="t.baslik" class="text-xs font-bold text-t-1">{{ t.baslik }}</h4>
              <p class="text-[11px] text-t-2 mt-0.5 leading-snug break-words">{{ t.metin }}</p>
            </div>
          </div>
          <button class="text-t-3 hover:text-t-1 shrink-0" aria-label="Kapat" @click="ui.toastKapat(t.id)"><FaIcon icon="xmark" class="h-3.5 w-3.5" /></button>
        </div>
        <div v-if="t.sure" class="absolute bottom-0 left-0 right-0 h-0.5 bg-bg-3">
          <div class="h-full toast-cubuk" :class="stil(t).cubuk" :style="{ animationDuration: t.sure + 'ms' }"></div>
        </div>
      </div>
    </transition-group>
  </div>
</template>
