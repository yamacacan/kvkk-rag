<script setup>
// Header zili: okunmamis sayaci (nabizli rozet), acilir bildirim listesi, tumunu oku,
// tiklayinca bagli sayfaya git. Veri: bildirim store'u (periyodik yoklama).
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useBildirimStore } from '../stores/bildirim';
import { goreliZaman } from '../utils/format';

const router = useRouter();
const store = useBildirimStore();
const kutu = ref(null);

const TUR = {
  'documents.ready': { ikon: 'file-word', sinif: 'bg-emerald-500/15 text-emerald-400' },
  'documents.failed': { ikon: 'circle-xmark', sinif: 'bg-rose-500/15 text-rose-400' },
  'queue.failed': { ikon: 'gears', sinif: 'bg-rose-500/15 text-rose-400' },
  'inventory.export_ready': { ikon: 'file-excel', sinif: 'bg-emerald-500/15 text-emerald-400' },
  'inventory.import_done': { ikon: 'file-arrow-up', sinif: 'bg-emerald-500/15 text-emerald-400' },
  'inventory.reindex_done': { ikon: 'arrows-rotate', sinif: 'bg-sky-500/15 text-sky-400' },
  'inventory.failed': { ikon: 'circle-xmark', sinif: 'bg-rose-500/15 text-rose-400' },
};
const SEVIYE = { ok: 'bg-emerald-500/15 text-emerald-400', hata: 'bg-rose-500/15 text-rose-400', uyari: 'bg-amber-500/15 text-amber-400', bilgi: 'bg-sky-500/15 text-sky-400' };
const stil = (b) => TUR[b.type] || { ikon: 'bell', sinif: SEVIYE[b.level] || SEVIYE.bilgi };
const sayac = computed(() => (store.okunmamis > 99 ? '99+' : store.okunmamis));

function ac() { store.acik = !store.acik; if (store.acik) store.yukle({ sessiz: true }); }
function disTiklama(e) { if (kutu.value && !kutu.value.contains(e.target)) store.acik = false; }
async function tikla(b) {
  await store.oku(b.id);
  store.acik = false;
  if (b.link) {
    const url = new URL(b.link, window.location.origin);
    router.push({ path: url.pathname, query: Object.fromEntries(url.searchParams) });
  }
}
onMounted(() => document.addEventListener('click', disTiklama));
onBeforeUnmount(() => document.removeEventListener('click', disTiklama));
</script>

<template>
  <div ref="kutu" class="relative">
    <button class="relative flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-bg-2 text-t-2 hover:text-t-1 hover:bg-bg-3"
      :class="store.acik ? 'border-indigo-500 text-t-1' : ''" title="Bildirimler" aria-haspopup="menu" :aria-expanded="store.acik" @click="ac">
      <FaIcon icon="bell" class="h-3.5 w-3.5" :class="store.okunmamis ? 'zil-salla' : ''" />
      <span v-if="store.okunmamis" class="absolute -top-1.5 -right-1.5 flex h-4 min-w-[16px] px-1 items-center justify-center rounded-full bg-rose-500 text-[9.5px] font-bold text-white ring-2 ring-bg-1">{{ sayac }}</span>
    </button>

    <transition enter-active-class="transition duration-150 ease-out" enter-from-class="opacity-0 -translate-y-1 scale-95" leave-active-class="transition duration-100" leave-to-class="opacity-0 scale-95">
      <div v-if="store.acik" class="absolute right-0 mt-2 w-[min(380px,calc(100vw-2rem))] rounded-xl border border-line bg-bg-1 shadow-2xl overflow-hidden z-50" role="menu">
        <div class="px-4 py-2.5 border-b border-line flex items-center justify-between">
          <p class="text-xs font-bold text-t-1 flex items-center gap-2"><FaIcon icon="bell" class="h-3 w-3 text-indigo-400" />Bildirimler
            <span v-if="store.okunmamis" class="rounded-full bg-rose-500/15 px-1.5 text-[10px] font-semibold text-rose-400">{{ store.okunmamis }} yeni</span></p>
          <button v-if="store.okunmamis" class="text-[11px] text-indigo-400 hover:underline flex items-center gap-1" @click="store.hepsiniOku()"><FaIcon icon="check-double" class="h-2.5 w-2.5" />Tümünü okundu say</button>
        </div>
        <div class="max-h-[420px] overflow-y-auto custom-scroll divide-y divide-line-60">
          <div v-if="!store.liste.length" class="px-4 py-8 text-center text-xs text-t-3">
            <FaIcon icon="inbox" class="h-6 w-6 mx-auto mb-2 text-t-muted" />Henüz bildirim yok.
          </div>
          <button v-for="b in store.liste" :key="b.id" class="w-full text-left px-4 py-2.5 flex items-start gap-3 hover:bg-bg-2 group" :class="b.okundu ? '' : 'bg-indigo-500/[0.06]'" role="menuitem" @click="tikla(b)">
            <span class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg" :class="stil(b).sinif"><FaIcon :icon="stil(b).ikon" class="h-3.5 w-3.5" /></span>
            <span class="min-w-0 flex-1">
              <span class="flex items-center gap-2">
                <span class="text-xs font-semibold truncate" :class="b.okundu ? 'text-t-2' : 'text-t-1'">{{ b.title }}</span>
                <span v-if="!b.okundu" class="h-1.5 w-1.5 rounded-full bg-indigo-500 shrink-0"></span>
              </span>
              <span v-if="b.body" class="block text-[11px] text-t-3 leading-snug line-clamp-2">{{ b.body }}</span>
              <span class="block text-[10px] font-mono text-t-muted mt-0.5" :title="b.created_at">{{ goreliZaman(b.created_at) }}</span>
            </span>
            <span class="opacity-0 group-hover:opacity-100 text-t-3 hover:text-rose-400 shrink-0 p-1" title="Sil" @click.stop="store.sil(b.id)"><FaIcon icon="xmark" class="h-3 w-3" /></span>
          </button>
        </div>
        <button class="w-full border-t border-line px-4 py-2.5 text-[11px] font-semibold text-indigo-400 hover:bg-bg-2 flex items-center justify-center gap-1.5" @click="store.acik = false; router.push({ name: 'bildirimler' })">
          <FaIcon icon="list-check" class="h-3 w-3" />Tüm bildirimleri gör</button>
      </div>
    </transition>
  </div>
</template>
