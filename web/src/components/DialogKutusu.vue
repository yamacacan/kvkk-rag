<script setup>
// SweetAlert2 tarzi dialog: buyuk yuvarlak ikon, baslik, aciklama, istege bagli detay kutusu,
// onay/iptal (ui.onay) ya da tek dugme (ui.uyar). Esc = vazgec, Enter = onayla.
import { computed, onBeforeUnmount, onMounted } from 'vue';
import { useUiStore } from '../stores/ui';

const ui = useUiStore();
const TUR = {
  ok: { halka: 'bg-emerald-500/10 border-emerald-500/40 text-emerald-400', ikon: 'circle-check', dugme: 'bg-emerald-600 hover:bg-emerald-500', kenar: 'border-emerald-500/30', detay: 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300' },
  uyari: { halka: 'bg-amber-500/10 border-amber-500/40 text-amber-400', ikon: 'triangle-exclamation', dugme: 'bg-amber-500 hover:bg-amber-400 !text-black', kenar: 'border-amber-500/30', detay: 'bg-amber-500/10 border-amber-500/25 text-amber-300' },
  hata: { halka: 'bg-rose-500/10 border-rose-500/40 text-rose-400', ikon: 'circle-xmark', dugme: 'bg-rose-600 hover:bg-rose-500', kenar: 'border-rose-500/30', detay: 'bg-rose-500/10 border-rose-500/25 text-rose-300' },
  bilgi: { halka: 'bg-indigo-500/10 border-indigo-500/40 text-indigo-400', ikon: 'bell', dugme: 'bg-indigo-600 hover:bg-indigo-500', kenar: 'border-indigo-500/30', detay: 'bg-indigo-500/10 border-indigo-500/25 text-indigo-300' },
};
const d = computed(() => ui.dialog);
const stil = computed(() => TUR[d.value?.tur] || TUR.bilgi);

function tus(e) {
  if (!ui.dialog) return;
  if (e.key === 'Escape') { e.preventDefault(); ui.dialogKapat(false); }
  else if (e.key === 'Enter') { e.preventDefault(); ui.dialogKapat(true); }
}
onMounted(() => document.addEventListener('keydown', tus));
onBeforeUnmount(() => document.removeEventListener('keydown', tus));
</script>

<template>
  <Teleport to="body">
    <transition enter-active-class="transition duration-150" enter-from-class="opacity-0" leave-active-class="transition duration-100" leave-to-class="opacity-0">
      <div v-if="d" class="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" @click.self="ui.dialogKapat(false)">
        <transition appear enter-active-class="transition duration-200 ease-out" enter-from-class="opacity-0 scale-95 translate-y-2">
          <div class="w-full max-w-md rounded-2xl border bg-bg-card shadow-2xl p-6 relative overflow-hidden text-center" :class="stil.kenar" role="alertdialog" aria-modal="true">
            <div class="absolute -top-12 -left-12 w-32 h-32 rounded-full blur-2xl pointer-events-none opacity-60" :class="stil.halka.split(' ')[0]"></div>
            <div class="relative">
              <div class="mx-auto w-16 h-16 rounded-full border-2 flex items-center justify-center shadow-sm" :class="stil.halka">
                <FaIcon :icon="stil.ikon" class="h-7 w-7" />
              </div>
              <h3 class="mt-4 text-base font-bold text-t-1">{{ d.baslik }}</h3>
              <p v-if="d.metin" class="mt-2 text-xs text-t-2 leading-relaxed whitespace-pre-line">{{ d.metin }}</p>
              <div v-if="d.detay" class="mt-4 p-3 rounded-xl border text-left text-[11px] leading-relaxed" :class="stil.detay">{{ d.detay }}</div>
              <div class="mt-6 grid gap-3" :class="d.mod === 'onay' ? 'grid-cols-2' : 'grid-cols-1'">
                <button v-if="d.mod === 'onay'" class="py-2.5 rounded-xl text-xs font-semibold bg-bg-3 hover:bg-bg-hover border border-line text-t-2 hover:text-t-1 transition" @click="ui.dialogKapat(false)">{{ d.iptalMetni }}</button>
                <button class="py-2.5 rounded-xl text-xs font-bold text-white shadow-sm transition" :class="stil.dugme" autofocus @click="ui.dialogKapat(true)">{{ d.onayMetni }}</button>
              </div>
            </div>
          </div>
        </transition>
      </div>
    </transition>
  </Teleport>
</template>
