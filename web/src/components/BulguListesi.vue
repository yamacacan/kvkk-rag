<script setup>
import { seviye } from '../utils/format';
defineProps({ bulgular: { type: Array, default: () => [] }, detayli: { type: Boolean, default: false } });
</script>

<template>
  <p v-if="!bulgular.length" class="text-xs text-emerald-400">{{ detayli ? 'Bulgu yok.' : 'Bu kayıtta uyum bulgusu yok.' }}</p>
  <div v-else>
    <div v-for="(b, i) in bulgular" :key="i" class="p-2.5 rounded-lg bg-[var(--bg-inset)] border mb-1.5" :class="seviye(b.seviye).kutu">
      <div class="flex items-center gap-2 mb-0.5">
        <span class="text-[9.5px] font-bold px-1.5 py-0.5 rounded border" :class="seviye(b.seviye).rozet">{{ seviye(b.seviye).etiket }}</span>
        <span class="font-mono text-[9.5px] text-[var(--t2)]">{{ b.kod }}</span>
        <span class="text-[11px] font-semibold text-white">{{ b.baslik }}</span>
      </div>
      <p v-if="detayli" class="text-[11px] text-[var(--t1)] leading-snug mb-1">{{ b.aciklama }}</p>
      <p class="text-[10.5px] font-mono text-indigo-400">{{ detayli ? 'Dayanak: ' : '' }}{{ b.dayanak }}</p>
    </div>
  </div>
</template>
