<script setup>
import { useRoute } from 'vue-router';
const route = useRoute();
</script>

<template>
  <div class="max-w-lg mx-auto mt-16 p-6 rounded-2xl border border-[var(--line)] bg-[var(--bg-2)] text-center">
    <p class="text-[10.5px] font-bold uppercase tracking-wider text-rose-400 mb-2">403 · Yetki yok</p>
    <h1 class="text-lg font-extrabold text-white mb-2">Bu sayfa için izniniz yok</h1>
    <p class="text-xs text-[var(--t1)] mb-1">Rolünüz bu modüle erişim vermiyor.</p>
    <p v-if="route.query.izin" class="text-[11px] font-mono text-[var(--t2)]">gereken izin: {{ route.query.izin }}</p>
  </div>
</template>
