<script setup>
import { computed } from 'vue';
const props = defineProps({ toplam: { type: Number, default: 0 }, limit: { type: Number, default: 50 }, offset: { type: Number, default: 0 } });
const emit = defineEmits(['git']);

const sayfa = computed(() => Math.floor(props.offset / props.limit) + 1);
const son = computed(() => Math.max(1, Math.ceil(props.toplam / props.limit)));
const numaralar = computed(() => {
  const bas = Math.max(1, Math.min(sayfa.value - 1, son.value - 2));
  const out = [];
  for (let i = bas; i <= Math.min(bas + 2, son.value); i++) out.push(i);
  return { bas, out };
});
const git = (s) => emit('git', Math.max(0, (s - 1) * props.limit));
const btn = 'h-8 rounded-md text-xs font-semibold';
const pasifSinif = 'border border-[var(--line)] bg-[var(--bg-3)] text-[var(--t1)] hover:text-white';
</script>

<template>
  <div class="flex items-center gap-1.5">
    <button :class="[btn, 'px-2.5', pasifSinif, sayfa === 1 ? 'opacity-40 cursor-not-allowed' : '']" :disabled="sayfa === 1" @click="git(sayfa - 1)">Önceki</button>
    <button v-for="i in numaralar.out" :key="i" :class="[btn, 'w-8', i === sayfa ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30' : pasifSinif]" @click="git(i)">{{ i }}</button>
    <template v-if="son > numaralar.bas + 2">
      <span class="px-1 text-[var(--t2)] text-xs font-mono">…</span>
      <button :class="[btn, 'px-2.5', pasifSinif]" @click="git(son)">{{ son }}</button>
    </template>
    <button :class="[btn, 'px-2.5', pasifSinif, sayfa >= son ? 'opacity-40 cursor-not-allowed' : '']" :disabled="sayfa >= son" @click="git(sayfa + 1)">Sonraki</button>
  </div>
</template>
