<script setup>
defineProps({ baslik: String, deger: [String, Number], alt: String, renk: { type: String, default: 'indigo' }, rozet: String });
const RENK = {
  indigo: { deger: 'text-indigo-400', rozet: 'bg-indigo-500/20 text-indigo-300' },
  rose: { deger: 'text-rose-400', rozet: 'bg-rose-500/20 text-rose-300' },
  amber: { deger: 'text-amber-400', rozet: 'bg-amber-500/20 text-amber-300' },
  emerald: { deger: 'text-emerald-400', rozet: 'bg-emerald-500/20 text-emerald-300' },
};
</script>

<template>
  <div class="p-4 rounded-xl border border-[var(--line)] bg-[var(--bg-2)]">
    <div class="flex items-center justify-between mb-2">
      <span class="text-xs font-semibold uppercase tracking-wider text-[var(--t2)]">{{ baslik }}</span>
      <span v-if="rozet" class="text-xs font-bold px-2 py-0.5 rounded" :class="(RENK[renk] || RENK.indigo).rozet">{{ rozet }}</span>
    </div>
    <p class="text-2xl font-mono font-extrabold" :class="(RENK[renk] || RENK.indigo).deger">{{ deger }}</p>
    <p class="text-[11px] text-[var(--t2)] mt-0.5">{{ alt }}</p>
  </div>
</template>
