<script setup>
// Genel amacli modal: baslik, govde (slot), alt aksiyonlar (slot#alt). Esc / arka plan kapatir.
import { onBeforeUnmount, onMounted } from 'vue';
defineProps({ baslik: String, altBaslik: String, genislik: { type: String, default: 'max-w-2xl' } });
const emit = defineEmits(['kapat']);
function esc(e) { if (e.key === 'Escape') emit('kapat'); }
onMounted(() => document.addEventListener('keydown', esc));
onBeforeUnmount(() => document.removeEventListener('keydown', esc));
</script>

<template>
  <div class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start justify-center p-4 sm:p-6 overflow-y-auto" @click.self="emit('kapat')">
    <div class="w-full my-4 bg-bg-card border border-line rounded-2xl shadow-2xl" :class="genislik" role="dialog" aria-modal="true">
      <div class="sticky top-0 bg-bg-1 border-b border-line px-5 py-3 flex items-center justify-between rounded-t-2xl">
        <div>
          <h3 class="text-sm font-bold text-t-1">{{ baslik }}</h3>
          <p v-if="altBaslik" class="text-[11px] text-t-3">{{ altBaslik }}</p>
        </div>
        <button class="text-t-3 hover:text-t-1 text-lg leading-none" aria-label="Kapat" @click="emit('kapat')">✕</button>
      </div>
      <div class="p-5"><slot /></div>
      <div v-if="$slots.alt" class="sticky bottom-0 bg-bg-1 border-t border-line px-5 py-3 flex items-center justify-between gap-3 rounded-b-2xl">
        <slot name="alt" />
      </div>
    </div>
  </div>
</template>
