<script setup>
// Yatay cubuk grafik: tek seri, tek vurgu tonu, <=24px kalinlik, 4px yuvarlak uc
// (taban duz), dogrudan deger etiketi, hover balonu. Genislikler 0'dan animasyonla acilir.
import { computed, onMounted, ref } from 'vue';
import { sayi } from '../utils/format';

const props = defineProps({
  veriler: { type: Array, required: true },   // [{ etiket, deger }]
  maks: { type: Number, default: 0 },
  enFazla: { type: Number, default: 8 },      // fazlasi "Diğer" olarak katlanir
  renk: { type: String, default: '#6366F1' },
  birim: { type: String, default: 'kayıt' },
});
const hazir = ref(false);
const vurgu = ref(-1);
const satirlar = computed(() => {
  const s = [...props.veriler].sort((a, b) => b.deger - a.deger);
  if (s.length <= props.enFazla) return s;
  const bas = s.slice(0, props.enFazla - 1);
  const kalan = s.slice(props.enFazla - 1).reduce((a, x) => a + x.deger, 0);
  return [...bas, { etiket: `Diğer (${s.length - bas.length})`, deger: kalan, diger: true }];
});
const tavan = computed(() => Math.max(props.maks || 0, ...satirlar.value.map((x) => x.deger), 1));
const toplam = computed(() => satirlar.value.reduce((a, x) => a + x.deger, 0) || 1);
const genislik = (x) => (hazir.value ? Math.max(1.5, (x.deger / tavan.value) * 100) : 0);
onMounted(() => { requestAnimationFrame(() => { hazir.value = true; }); setTimeout(() => { hazir.value = true; }, 400); });
</script>

<template>
  <div class="h-full flex flex-col justify-center gap-2" role="img" aria-label="Veri kategorisi dağılımı">
    <div v-for="(x, i) in satirlar" :key="x.etiket" class="grid grid-cols-[minmax(0,118px)_1fr_auto] items-center gap-2.5 text-[11px]"
      @mouseenter="vurgu = i" @mouseleave="vurgu = -1">
      <span class="truncate" :class="x.diger ? 'text-t-3 italic' : vurgu === i ? 'text-t-1' : 'text-t-2'" :title="x.etiket">{{ x.etiket }}</span>
      <div class="h-2.5 rounded-r-md bg-bg-3 overflow-hidden">
        <div class="h-full rounded-r-md cubuk-dolum" :style="{ width: genislik(x) + '%', background: x.diger ? 'var(--t-muted)' : renk, opacity: vurgu === -1 || vurgu === i ? 1 : 0.45, transitionDelay: (i * 60) + 'ms' }"></div>
      </div>
      <span class="font-mono shrink-0 text-right tabular-nums" :class="vurgu === i ? 'text-t-1' : 'text-t-3'">{{ sayi(x.deger) }}<span v-if="vurgu === i" class="text-t-3"> · %{{ Math.round((x.deger / toplam) * 100) }}</span></span>
    </div>
    <p v-if="!satirlar.length" class="text-[11px] text-t-3">Veri yok.</p>
  </div>
</template>
