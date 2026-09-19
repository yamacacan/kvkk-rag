<script setup>
// Panel KPI karti: ikon kutusu, sayac animasyonlu deger, kisa alt bilgi, filigran ikon.
import { computed, toRef } from 'vue';
import { useSayac } from '../composables/useSayac';
import { sayi } from '../utils/format';

const props = defineProps({
  baslik: String, deger: { type: Number, default: 0 }, sonek: { type: String, default: '' }, onek: { type: String, default: '' },
  alt: String, ikon: { type: String, default: 'database' }, renk: { type: String, default: 'indigo' }, rozet: String, gecikme: { type: Number, default: 0 },
});
const RENK = {
  indigo: { kutu: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/20', deger: 'text-t-1', rozet: 'bg-indigo-500/10 text-indigo-400', filigran: 'text-indigo-400' },
  rose: { kutu: 'bg-rose-500/15 text-rose-400 border-rose-500/20', deger: 'text-rose-400', rozet: 'bg-rose-500/10 text-rose-400', filigran: 'text-rose-400' },
  amber: { kutu: 'bg-amber-500/15 text-amber-400 border-amber-500/20', deger: 'text-t-1', rozet: 'bg-amber-500/10 text-amber-400', filigran: 'text-amber-400' },
  emerald: { kutu: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20', deger: 'text-emerald-400', rozet: 'bg-emerald-500/10 text-emerald-400', filigran: 'text-emerald-400' },
};
const r = computed(() => RENK[props.renk] || RENK.indigo);
const canli = useSayac(toRef(props, 'deger'));
</script>

<template>
  <div class="kart-giris kart-kalk relative overflow-hidden rounded-xl border border-line bg-bg-card p-4" :style="{ animationDelay: gecikme + 'ms' }">
    <FaIcon :icon="ikon" class="absolute -right-3 -bottom-3 h-20 w-20 opacity-[0.06] pointer-events-none" :class="r.filigran" />
    <div class="flex items-start justify-between mb-3">
      <div class="flex items-center gap-2.5">
        <span class="flex h-9 w-9 items-center justify-center rounded-lg border" :class="r.kutu"><FaIcon :icon="ikon" class="h-4 w-4" /></span>
        <span class="text-xs font-semibold uppercase tracking-wider text-t-3">{{ baslik }}</span>
      </div>
      <span v-if="rozet" class="rounded px-2 py-0.5 text-[11px] font-medium" :class="r.rozet">{{ rozet }}</span>
    </div>
    <div class="text-3xl font-extrabold tracking-tight font-mono" :class="r.deger">{{ onek }}{{ sayi(canli) }}{{ sonek }}</div>
    <div v-if="alt" class="mt-1.5 text-[11px] text-t-3">{{ alt }}</div>
    <slot />
  </div>
</template>
