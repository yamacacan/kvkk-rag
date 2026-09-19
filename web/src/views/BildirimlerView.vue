<script setup>
// Tum bildirimler: kullanicinin kendi bildirimleri, sunucu tarafi sayfalama;
// durum/tur/arama filtreleri; oku / okunmadi yap / sil; tumunu oku, okunmuslari temizle.
// Zil (header) ile ayni store'u paylasir: burada yapilan degisiklik sayaci da gunceller.
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { bildirimler as api } from '../api';
import { useBildirimStore } from '../stores/bildirim';
import { useUiStore } from '../stores/ui';
import { debounce, goreliZaman, sayi, tarih } from '../utils/format';
import DataTable from '../components/DataTable.vue';
import SearchableSelect from '../components/SearchableSelect.vue';
import Sayfalama from '../components/Sayfalama.vue';
import Rozet from '../components/Rozet.vue';
import FiltreCipi from '../components/FiltreCipi.vue';

const router = useRouter();
const store = useBildirimStore();
const ui = useUiStore();

const TUR = {
  'documents.ready': { ad: 'Belge hazır', ikon: 'file-word', sinif: 'bg-emerald-500/15 text-emerald-400', rozet: 'ok' },
  'documents.failed': { ad: 'Belge hatası', ikon: 'circle-xmark', sinif: 'bg-rose-500/15 text-rose-400', rozet: 'kritik' },
  'queue.failed': { ad: 'Kuyruk hatası', ikon: 'gears', sinif: 'bg-rose-500/15 text-rose-400', rozet: 'kritik' },
  'inventory.export_ready': { ad: 'Excel hazır', ikon: 'file-excel', sinif: 'bg-emerald-500/15 text-emerald-400', rozet: 'ok' },
  'inventory.import_done': { ad: 'İçe aktarım', ikon: 'file-arrow-up', sinif: 'bg-emerald-500/15 text-emerald-400', rozet: 'ok' },
  'inventory.reindex_done': { ad: 'İndeks yenilendi', ikon: 'arrows-rotate', sinif: 'bg-sky-500/15 text-sky-400', rozet: 'bilgi' },
  'inventory.failed': { ad: 'Envanter işi hatası', ikon: 'circle-xmark', sinif: 'bg-rose-500/15 text-rose-400', rozet: 'kritik' },
};
const SEVIYE = { ok: 'bg-emerald-500/15 text-emerald-400', hata: 'bg-rose-500/15 text-rose-400', uyari: 'bg-amber-500/15 text-amber-400', bilgi: 'bg-sky-500/15 text-sky-400' };
const stil = (b) => TUR[b.type] || { ad: b.type, ikon: 'bell', sinif: SEVIYE[b.level] || SEVIYE.bilgi, rozet: 'bilgi' };
const DURUMLAR = [{ value: 'okunmamis', label: 'Okunmamış' }, { value: 'okunmus', label: 'Okunmuş' }];

const SUTUNLAR = [
  { key: 'title', label: 'Bildirim' },
  { key: 'type', label: 'Tür', width: 'w-40' },
  { key: 'created_at', label: 'Zaman', width: 'w-36' },
  { key: 'okundu', label: 'Durum', width: 'w-28' },
  { key: 'islem', label: '', width: 'w-40', align: 'right' },
];

const kayitlar = ref([]);
const toplam = ref(0);
const limit = ref(25);
const offset = ref(0);
const turler = ref([]);
const durum = ref('');
const tur = ref('');
const arama = ref('');
const yukleniyor = ref(false);
const secili = ref(new Set());

const turSecenekleri = computed(() => turler.value.map((t) => ({ value: t, label: TUR[t]?.ad || t, alt: t })));
const aktifFiltreler = computed(() => [
  durum.value && { k: 'durum', etiket: 'Durum', deger: DURUMLAR.find((d) => d.value === durum.value)?.label },
  tur.value && { k: 'tur', etiket: 'Tür', deger: TUR[tur.value]?.ad || tur.value },
  arama.value && { k: 'arama', etiket: 'Arama', deger: arama.value },
].filter(Boolean));
const seciliOkunmamis = computed(() => kayitlar.value.filter((b) => secili.value.has(b.id) && !b.okundu).length);

async function yukle() {
  yukleniyor.value = true;
  try {
    const d = await api.liste({ durum: durum.value, tur: tur.value, arama: arama.value, limit: limit.value, offset: offset.value });
    kayitlar.value = d.bildirimler; toplam.value = d.toplam; turler.value = d.turler;
    store.okunmamis = d.okunmamis;
  } catch (e) { ui.hata('Bildirimler yüklenemedi', e.message); }
  finally { yukleniyor.value = false; }
}
const yukleGecikmeli = debounce(yukle, 320);
watch([durum, tur], () => { offset.value = 0; yukle(); });
watch(arama, () => { offset.value = 0; yukleGecikmeli(); });
function filtreKaldir(k) { if (k === 'durum') durum.value = ''; else if (k === 'tur') tur.value = ''; else arama.value = ''; }
function sifirla() { durum.value = ''; tur.value = ''; arama.value = ''; }

// Durum filtresi acikken satir artik filtreye uymuyorsa listeden duser
function filtredenDusur(b, filtre) {
  if (durum.value !== filtre) return;
  kayitlar.value = kayitlar.value.filter((x) => x.id !== b.id); toplam.value = Math.max(0, toplam.value - 1);
}
async function oku(b) {
  if (b.okundu) return;
  b.okundu = true; store.okunmamis = Math.max(0, store.okunmamis - 1);
  try { await api.oku(b.id); } catch {}
  filtredenDusur(b, 'okunmamis');
  store.yukle({ sessiz: true });
}
async function okunmadiYap(b) {
  b.okundu = false; store.okunmamis += 1;
  try { await api.okunmadiYap(b.id); } catch {}
  filtredenDusur(b, 'okunmus');
  store.yukle({ sessiz: true });
}
async function git(b) {
  await oku(b);
  if (!b.link) return;
  const url = new URL(b.link, window.location.origin);
  router.push({ path: url.pathname, query: Object.fromEntries(url.searchParams) });
}
async function sil(b) {
  try { await api.sil(b.id); kayitlar.value = kayitlar.value.filter((x) => x.id !== b.id); toplam.value -= 1; if (!b.okundu) store.okunmamis = Math.max(0, store.okunmamis - 1); }
  catch (e) { ui.hata('Silinemedi', e.message); }
  store.yukle({ sessiz: true });
}
async function hepsiniOku() {
  await store.hepsiniOku();
  kayitlar.value.forEach((b) => { b.okundu = true; });
  ui.bildir('Tüm bildirimler okundu sayıldı.');
}
async function okunmuslariTemizle() {
  const ok = await ui.onay({ baslik: 'Okunmuş bildirimler silinsin mi?', metin: 'Okunmamış bildirimler kalır; bu işlem geri alınamaz.', tur: 'uyari', onayMetni: 'Temizle', tehlikeli: true });
  if (!ok) return;
  try { const d = await api.okunmuslariTemizle(); ui.bildir(`${d.silindi} bildirim silindi.`); offset.value = 0; await yukle(); store.yukle({ sessiz: true }); }
  catch (e) { ui.hata('Temizlenemedi', e.message); }
}
async function seciliOku() {
  const hedef = kayitlar.value.filter((b) => secili.value.has(b.id) && !b.okundu);
  await Promise.all(hedef.map((b) => oku(b)));
  secili.value = new Set();
}
async function seciliSil() {
  const ok = await ui.onay({ baslik: `${secili.value.size} bildirim silinsin mi?`, tur: 'uyari', onayMetni: 'Sil', tehlikeli: true });
  if (!ok) return;
  const hedef = kayitlar.value.filter((b) => secili.value.has(b.id));
  await Promise.all(hedef.map((b) => sil(b)));
  secili.value = new Set();
  if (!kayitlar.value.length && offset.value > 0) { offset.value = Math.max(0, offset.value - limit.value); }
  yukle();
}
onMounted(yukle);
</script>

<template>
  <section class="space-y-5 max-w-[1780px] mx-auto">
    <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
      <div>
        <h1 class="text-2xl font-extrabold text-t-1 tracking-tight flex items-center gap-2.5"><FaIcon icon="bell" class="h-5 w-5 text-indigo-400" />Bildirimler
          <Rozet v-if="store.okunmamis" tur="kritik" boyut="xs" nokta nabiz>{{ store.okunmamis }} okunmamış</Rozet></h1>
        <p class="text-xs text-t-2 mt-1">Belge üretimi ve arka plan işleri gibi size özel bildirimler. Bildirime tıklayınca ilgili sayfaya gidersiniz.</p>
      </div>
      <div class="flex items-center gap-2">
        <button class="flex items-center gap-1.5 rounded-lg border border-line bg-bg-2 px-3 py-1.5 text-xs font-medium text-t-2 hover:text-t-1 hover:bg-bg-3 disabled:opacity-50" :disabled="!store.okunmamis" @click="hepsiniOku"><FaIcon icon="check-double" class="h-3 w-3" />Tümünü okundu say</button>
        <button class="flex items-center gap-1.5 rounded-lg border border-line bg-bg-2 px-3 py-1.5 text-xs font-medium text-t-2 hover:text-rose-400 hover:border-rose-500/40" @click="okunmuslariTemizle"><FaIcon icon="trash" class="h-3 w-3" />Okunmuşları temizle</button>
      </div>
    </div>

    <div class="rounded-xl border border-line bg-bg-card overflow-hidden">
      <div class="border-b border-line bg-bg-1/80 px-4 py-3 flex flex-col md:flex-row md:items-center gap-2">
        <input v-model="arama" placeholder="Başlık veya içerikte ara…" class="girdi md:max-w-xs">
        <div class="md:w-44"><SearchableSelect v-model="durum" :options="DURUMLAR" placeholder="Tüm durumlar" size="sm" /></div>
        <div class="md:w-56"><SearchableSelect v-model="tur" :options="turSecenekleri" placeholder="Tüm türler" size="sm" /></div>
        <div v-if="aktifFiltreler.length" class="flex flex-wrap items-center gap-1.5">
          <FiltreCipi v-for="f in aktifFiltreler" :key="f.k" :etiket="f.etiket" :deger="f.deger" @kaldir="filtreKaldir(f.k)" />
          <button class="text-[11px] text-indigo-400 hover:underline" @click="sifirla">Temizle</button>
        </div>
        <span class="text-[11px] text-t-3 md:ml-auto font-mono">{{ sayi(toplam) }} bildirim</span>
      </div>

      <div v-if="secili.size" class="border-b border-line bg-indigo-500/[0.06] px-4 py-2 flex items-center gap-3 text-xs">
        <span class="font-semibold text-t-1">{{ secili.size }} seçili</span>
        <button v-if="seciliOkunmamis" class="flex items-center gap-1 text-indigo-400 hover:underline" @click="seciliOku"><FaIcon icon="envelope-open" class="h-3 w-3" />Okundu say ({{ seciliOkunmamis }})</button>
        <button class="flex items-center gap-1 text-rose-400 hover:underline" @click="seciliSil"><FaIcon icon="trash" class="h-3 w-3" />Sil</button>
        <button class="ml-auto text-t-3 hover:text-t-1" @click="secili = new Set()">Seçimi bırak</button>
      </div>

      <DataTable :columns="SUTUNLAR" :rows="kayitlar" row-key="id" :loading="yukleniyor" selectable v-model:selected="secili" dense :show-count="false"
        empty-text="Bildirim yok." min-width="min-w-[860px]" :row-class="(b) => b.okundu ? '' : 'bg-indigo-500/[0.05]'">
        <template #cell-title="{ row: b }">
          <button class="flex items-start gap-3 text-left min-w-0 w-full group" @click="git(b)">
            <span class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg" :class="stil(b).sinif"><FaIcon :icon="stil(b).ikon" class="h-3.5 w-3.5" /></span>
            <span class="min-w-0">
              <span class="flex items-center gap-2"><span class="text-xs truncate group-hover:text-indigo-300" :class="b.okundu ? 'font-medium text-t-2' : 'font-bold text-t-1'">{{ b.title }}</span><span v-if="!b.okundu" class="h-1.5 w-1.5 rounded-full bg-indigo-500 shrink-0"></span></span>
              <span v-if="b.body" class="block text-[11px] text-t-3 leading-snug line-clamp-2">{{ b.body }}</span>
              <span v-if="b.link" class="block text-[10px] font-mono text-t-muted mt-0.5">{{ b.link }}</span>
            </span>
          </button>
        </template>
        <template #cell-type="{ row: b }"><Rozet :tur="stil(b).rozet" boyut="xs" sekil="rounded">{{ stil(b).ad }}</Rozet></template>
        <template #cell-created_at="{ value }"><span class="font-mono text-[10.5px] text-t-2" :title="tarih(value)">{{ goreliZaman(value) }}</span><span class="block font-mono text-[9.5px] text-t-muted">{{ tarih(value) }}</span></template>
        <template #cell-okundu="{ row: b }">
          <Rozet v-if="b.okundu" tur="notr" boyut="xs" sekil="rounded" ikon="envelope-open">Okundu</Rozet>
          <Rozet v-else tur="mor" boyut="xs" sekil="rounded" nokta>Yeni</Rozet>
        </template>
        <template #cell-islem="{ row: b }">
          <span class="flex items-center justify-end gap-1.5">
            <button v-if="b.link" class="flex h-7 w-7 items-center justify-center rounded-lg border border-line text-t-2 hover:text-indigo-400 hover:border-indigo-500/40" title="Sayfaya git" @click="git(b)"><FaIcon icon="arrow-up-right-from-square" class="h-3 w-3" /></button>
            <button class="flex h-7 w-7 items-center justify-center rounded-lg border border-line text-t-2 hover:text-t-1" :title="b.okundu ? 'Okunmadı yap' : 'Okundu say'" @click="b.okundu ? okunmadiYap(b) : oku(b)"><FaIcon :icon="b.okundu ? 'envelope-open' : 'check'" class="h-3 w-3" /></button>
            <button class="flex h-7 w-7 items-center justify-center rounded-lg border border-line text-t-2 hover:text-rose-400 hover:border-rose-500/40" title="Sil" @click="sil(b)"><FaIcon icon="trash" class="h-3 w-3" /></button>
          </span>
        </template>
      </DataTable>

      <div v-if="toplam > limit" class="px-4 py-3 border-t border-line flex items-center justify-between gap-3">
        <span class="text-[11px] text-t-3 font-mono">{{ offset + 1 }}–{{ Math.min(offset + limit, toplam) }} / {{ sayi(toplam) }}</span>
        <Sayfalama :toplam="toplam" :limit="limit" :offset="offset" @git="(o) => { offset = o; yukle(); }" />
      </div>
    </div>
  </section>
</template>
