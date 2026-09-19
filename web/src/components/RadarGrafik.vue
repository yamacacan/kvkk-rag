<script setup>
// Altigen (radar) grafik: tek seri, N eksen (varsayilan 6 denetim kurali). Poligon
// merkezden hedef degerlere animasyonla acilir; her kose hover'da deger balonu.
// Tablo gorunumu (eksen + deger listesi) grafigin yaninda; renk tek vurgu tonu.
import { computed, onMounted, ref } from 'vue';

const props = defineProps({
  eksenler: { type: Array, required: true },   // [{ etiket, deger, ipucu?, kisa? }]
  maks: { type: Number, default: 0 },          // 0 -> en buyuk degerden
  boyut: { type: Number, default: 260 },
  halka: { type: Number, default: 4 },
});
const R = computed(() => props.boyut / 2 - 30);
const merkez = computed(() => props.boyut / 2);
const tavan = computed(() => Math.max(props.maks || 0, ...props.eksenler.map((e) => e.deger || 0), 1));
const ilerleme = ref(0);
const vurgu = ref(-1);

const aci = (i) => -Math.PI / 2 + (2 * Math.PI * i) / props.eksenler.length;
const nokta = (i, r) => ({ x: merkez.value + r * Math.cos(aci(i)), y: merkez.value + r * Math.sin(aci(i)) });
const halkaYolu = (oran) => props.eksenler.map((_, i) => { const p = nokta(i, R.value * oran); return `${p.x},${p.y}`; }).join(' ');
const veriNoktalari = computed(() => props.eksenler.map((e, i) => nokta(i, R.value * ((e.deger || 0) / tavan.value) * ilerleme.value)));
const veriYolu = computed(() => veriNoktalari.value.map((p) => `${p.x},${p.y}`).join(' '));
const etiketKonum = (i) => { const p = nokta(i, R.value + 15); return { x: p.x, y: p.y, anchor: Math.abs(p.x - merkez.value) < 6 ? 'middle' : p.x < merkez.value ? 'end' : 'start' }; };

onMounted(() => {
  const azaltilmis = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  if (azaltilmis) { ilerleme.value = 1; return; }
  const t0 = performance.now(), sure = 900;
  const adim = (t) => { const x = Math.min(1, (t - t0) / sure); ilerleme.value = 1 - Math.pow(1 - x, 3); if (x < 1) requestAnimationFrame(adim); };
  requestAnimationFrame(adim);
  setTimeout(() => { ilerleme.value = 1; }, sure + 200);
});
</script>

<template>
  <div class="h-full flex flex-col sm:flex-row items-center justify-center gap-5">
    <svg :viewBox="`0 0 ${boyut} ${boyut}`" :width="boyut" :height="boyut" class="shrink-0 max-w-full overflow-visible" role="img" aria-label="Kural bazlı bulgu radarı">
      <!-- halkalar ve eksen cizgileri (geri planda, sonuk) -->
      <polygon v-for="h in halka" :key="h" :points="halkaYolu(h / halka)" fill="none" stroke="var(--line)" stroke-width="1" />
      <line v-for="(e, i) in eksenler" :key="'ax' + i" :x1="merkez" :y1="merkez" :x2="nokta(i, R).x" :y2="nokta(i, R).y" stroke="var(--line)" stroke-width="1" />
      <!-- veri -->
      <polygon :points="veriYolu" fill="rgba(99,102,241,.22)" stroke="#6366F1" stroke-width="2" stroke-linejoin="round" />
      <g v-for="(p, i) in veriNoktalari" :key="'pt' + i" @mouseenter="vurgu = i" @mouseleave="vurgu = -1" class="cursor-default">
        <circle :cx="p.x" :cy="p.y" r="11" fill="transparent" />
        <circle :cx="p.x" :cy="p.y" :r="vurgu === i ? 6 : 4" fill="#6366F1" stroke="var(--bg-card)" stroke-width="2" />
      </g>
      <!-- eksen etiketleri -->
      <text v-for="(e, i) in eksenler" :key="'lb' + i" :x="etiketKonum(i).x" :y="etiketKonum(i).y" :text-anchor="etiketKonum(i).anchor" dominant-baseline="middle"
        font-size="10" font-family="JetBrains Mono, monospace" font-weight="600" :fill="vurgu === i ? 'var(--t0)' : 'var(--t1)'">{{ e.kisa || e.etiket }}</text>
      <!-- balon -->
      <g v-if="vurgu >= 0">
        <rect :x="Math.min(Math.max(veriNoktalari[vurgu].x - 44, 4), boyut - 92)" :y="veriNoktalari[vurgu].y - 36" width="88" height="24" rx="6" fill="var(--bg-1)" stroke="var(--line-2)" />
        <text :x="Math.min(Math.max(veriNoktalari[vurgu].x - 44, 4), boyut - 92) + 44" :y="veriNoktalari[vurgu].y - 24" text-anchor="middle" dominant-baseline="middle" font-size="10.5" font-family="JetBrains Mono, monospace" fill="var(--t0)">{{ eksenler[vurgu].etiket }}: {{ eksenler[vurgu].deger }}</text>
      </g>
    </svg>
    <!-- tablo gorunumu: eksen, deger, aciklama -->
    <ul class="flex-1 min-w-0 w-full space-y-1">
      <li v-for="(e, i) in eksenler" :key="e.etiket" class="rounded-md px-2 py-1 text-[11px] transition-colors cursor-default" :class="vurgu === i ? 'bg-indigo-500/10' : ''" @mouseenter="vurgu = i" @mouseleave="vurgu = -1">
        <div class="flex items-center justify-between gap-2">
          <span class="font-mono text-indigo-300">{{ e.etiket }}</span>
          <span class="font-mono font-semibold text-t-1">{{ e.deger }}</span>
        </div>
        <p v-if="e.ipucu" class="text-[10.5px] text-t-3 leading-tight truncate" :title="e.ipucu">{{ e.ipucu }}</p>
      </li>
    </ul>
  </div>
</template>
