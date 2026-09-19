<script setup>
// Kaldirilabilir filtre cipi: "Etiket: Deger  x". tur: notr|kritik|mor|ok
defineProps({ etiket: String, deger: [String, Number], tur: { type: String, default: 'notr' }, ikon: String });
const emit = defineEmits(['kaldir']);
const TUR = {
  notr: 'bg-bg-2 text-t-2 border-line hover:bg-bg-3',
  kritik: 'bg-rose-500/10 text-rose-300 border-rose-500/25 hover:bg-rose-500/15',
  mor: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/25 hover:bg-indigo-500/15',
  ok: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/25 hover:bg-emerald-500/15',
};
</script>

<template>
  <span class="inline-flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 rounded-lg text-[11px] font-medium border transition" :class="TUR[tur] || TUR.notr">
    <FaIcon v-if="ikon" :icon="ikon" class="h-3 w-3 opacity-80" />
    <span><span v-if="etiket">{{ etiket }}: </span><strong class="text-t-1">{{ deger }}</strong></span>
    <button type="button" class="p-0.5 rounded opacity-70 hover:opacity-100 focus:outline-none" title="Kaldır" aria-label="Filtreyi kaldır" @click="emit('kaldir')">
      <FaIcon icon="xmark" class="h-3 w-3" />
    </button>
  </span>
</template>
