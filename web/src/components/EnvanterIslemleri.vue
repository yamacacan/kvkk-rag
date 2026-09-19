<script setup>
// Envanter arka plan islemleri (kuyruk): Excel disa aktarim, Excel'den ice aktarim,
// vektor indeksi. Kullanicinin kendi islemleri; bekleyen is varken 4 sn'de bir yoklanir,
// belge bildirimi gelince tazelenir. Bitince 'tamamlandi' yayar (ice aktarim -> tablo yenilenir).
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { envanter as envApi } from '../api';
import { useAuthStore } from '../stores/auth';
import { useBildirimStore } from '../stores/bildirim';
import { useUiStore } from '../stores/ui';
import { goreliZaman, kisalt, sayi, tarih } from '../utils/format';
import DataTable from './DataTable.vue';
import Rozet from './Rozet.vue';

const emit = defineEmits(['tamamlandi', 'yeniden-indeksle']);
const auth = useAuthStore();
const ui = useUiStore();
const route = useRoute();
const bildirim = useBildirimStore();

const islemler = ref([]);
const bekleyen = ref(0);
const yukleniyor = ref(false);
const indiriliyor = reactive({});
const vurgulu = ref(Number(route.query.islem) || null);
const acik = ref(!!route.query.islem);
let yoklayici = null;
let bilinen = new Set(); // tamamlanmis olarak gorulen islem id'leri (tamamlandi olayi bir kez yayilsin)

const TUR = {
  disa_aktar: { ikon: 'file-arrow-down', sinif: 'text-emerald-400' },
  ice_aktar: { ikon: 'file-arrow-up', sinif: 'text-sky-400' },
  yeniden_indeksle: { ikon: 'arrows-rotate', sinif: 'text-violet-400' },
};
const DURUM = {
  kuyrukta: { ad: 'Kuyrukta', tur: 'notr', ikon: 'hourglass-half' },
  calisiyor: { ad: 'Çalışıyor', tur: 'bilgi', ikon: 'spinner' },
  tamamlandi: { ad: 'Tamamlandı', tur: 'ok', ikon: 'check' },
  hata: { ad: 'Hata', tur: 'kritik', ikon: 'circle-xmark' },
};
const SUTUNLAR = [
  { key: 'tur_adi', label: 'İşlem' },
  { key: 'sonuc', label: 'Sonuç' },
  { key: 'durum', label: 'Durum', width: 'w-32' },
  { key: 'created_at', label: 'Zaman', width: 'w-28' },
  { key: 'islem', label: '', width: 'w-36', align: 'right' },
];
const boyutMetni = (n) => (!n ? '' : n < 1024 * 1024 ? `${Math.round(n / 1024)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);
function sonucMetni(i) {
  const s = i.sonuc || {}; const f = i.istek || {};
  if (i.durum === 'hata') return i.hata;
  if (i.tur === 'disa_aktar') {
    const filtre = ['birim', 'faaliyet', 'veri_kategorisi', 'seviye', 'arama'].filter((k) => f[k]).map((k) => `${k}: ${f[k]}`);
    if (f.satir_no?.length) filtre.push(`${f.satir_no.length} seçili satır`);
    return (i.durum === 'tamamlandi' ? `${sayi(s.satir)} satır · ${boyutMetni(i.boyut)}` : 'hazırlanıyor') + (filtre.length ? ` · ${filtre.join(', ')}` : '');
  }
  if (i.tur === 'ice_aktar') {
    if (i.durum !== 'tamamlandi') return `${i.ad || 'xlsx'} · ${boyutMetni(i.boyut)} · ${f.mod === 'degistir' ? 'tümünü değiştir' : 'ekle'}`;
    return `${sayi(s.eklenen)} satır eklendi` + (s.atlanan ? ` · ${s.atlanan} satır kapsam dışı` : '') + (s.eksik_sutunlar?.length ? ` · eksik sütun: ${s.eksik_sutunlar.join(', ')}` : '');
  }
  return i.durum === 'tamamlandi' ? `${sayi(s.satir)} satır indekslendi` : 'indeks kuruluyor';
}

async function yukle(sessiz = false) {
  if (!sessiz) yukleniyor.value = true;
  const onceBekleyen = bekleyen.value;
  try {
    const d = await envApi.islemler(30);
    islemler.value = d.islemler; bekleyen.value = d.bekleyen;
    // yeni tamamlanan isler -> olay (ice aktarim tabloyu tazeler)
    d.islemler.filter((i) => i.durum === 'tamamlandi' && !bilinen.has(i.id)).forEach((i) => { if (bilinen.size || onceBekleyen) emit('tamamlandi', i); });
    bilinen = new Set(d.islemler.filter((i) => i.durum !== 'kuyrukta' && i.durum !== 'calisiyor').map((i) => i.id));
  } catch {} finally { yukleniyor.value = false; }
  if (bekleyen.value < onceBekleyen) bildirim.yukle({ sessiz: true });
  yoklamaAyarla();
}
function yoklamaAyarla() {
  clearInterval(yoklayici); yoklayici = null;
  bildirim.hizliYokla(bekleyen.value > 0);
  if (bekleyen.value > 0) yoklayici = setInterval(() => yukle(true), 4000);
}
function ekle(islem) { islemler.value = [islem, ...islemler.value]; bekleyen.value += 1; acik.value = true; yoklamaAyarla(); }
async function indir(i) {
  indiriliyor[i.id] = true;
  try { await envApi.islemIndir(i.id, i.ad); } catch (e) { ui.hata('İndirilemedi', e.message); }
  finally { delete indiriliyor[i.id]; }
}
async function sil(i) {
  const ok = await ui.onay({ baslik: 'İşlem kaydı silinsin mi?', metin: `${i.tur_adi} (#${i.id})${i.ad ? ' · ' + i.ad : ''} ve dosyası silinecek.`, tur: 'uyari', onayMetni: 'Sil', tehlikeli: true });
  if (!ok) return;
  try { await envApi.islemSil(i.id); islemler.value = islemler.value.filter((x) => x.id !== i.id); ui.bildir('İşlem silindi.'); }
  catch (e) { ui.hata('Silinemedi', e.message); }
}
const dinlemeyiBirak = bildirim.dinle((yeniler) => { if (yeniler.some((b) => b.type?.startsWith('inventory.'))) yukle(true); });
watch(() => route.query.islem, (v) => { vurgulu.value = Number(v) || null; if (v) acik.value = true; });
onMounted(() => yukle());
onBeforeUnmount(() => { clearInterval(yoklayici); bildirim.hizliYokla(false); dinlemeyiBirak(); });
defineExpose({ yukle, ekle });
</script>

<template>
  <div class="rounded-2xl border border-[var(--line)] bg-[var(--bg-2)] overflow-hidden">
    <button class="w-full px-5 py-3 flex items-center gap-2 text-left" :class="acik ? 'border-b border-[var(--line)] bg-[var(--bg-1)]/70' : ''" @click="acik = !acik">
      <FaIcon icon="gears" class="h-3.5 w-3.5 text-indigo-400" />
      <h3 class="text-sm font-bold text-white">Arka Plan İşlemleri</h3>
      <Rozet v-if="bekleyen" tur="bilgi" boyut="xs" nokta nabiz>{{ bekleyen }} işlem sürüyor</Rozet>
      <span v-else-if="islemler.length" class="text-[10.5px] text-[var(--t2)] font-mono">{{ islemler.length }} kayıt</span>
      <span class="text-[10.5px] text-[var(--t2)] hidden sm:inline">Excel dışa/içe aktarım ve indeksleme kuyrukta çalışır; bitince bildirim gelir</span>
      <span class="ml-auto flex items-center gap-2">
        <span v-if="auth.can('inventory.reindex')" class="text-[11px] text-[var(--t1)] hover:text-white flex items-center gap-1" title="Vektör indeksini yeniden kur" @click.stop="$emit('yeniden-indeksle')"><FaIcon icon="arrows-rotate" class="h-3 w-3" />İndeksi yenile</span>
        <span class="text-[11px] text-[var(--t1)] hover:text-white flex items-center gap-1" @click.stop="yukle()"><FaIcon icon="rotate" class="h-3 w-3" :class="yukleniyor ? 'animate-spin' : ''" />Yenile</span>
        <FaIcon icon="chevron-down" class="h-3 w-3 text-[var(--t2)] transition-transform" :class="acik ? 'rotate-180' : ''" />
      </span>
    </button>
    <DataTable v-if="acik" :columns="SUTUNLAR" :rows="islemler" row-key="id" :loading="yukleniyor" dense :show-count="false"
      empty-text="Henüz arka plan işlemi yok. Excel'e aktar / içe aktar ile başlatın."
      :row-class="(r) => r.id === vurgulu ? 'bg-indigo-500/10' : ''">
      <template #cell-tur_adi="{ row }">
        <span class="flex items-center gap-2"><FaIcon :icon="TUR[row.tur]?.ikon || 'gears'" class="h-3.5 w-3.5 shrink-0" :class="TUR[row.tur]?.sinif" />
          <span><span class="block text-xs font-semibold text-white">{{ row.tur_adi }} <span class="font-mono text-[10px] text-[var(--t2)]">#{{ row.id }}</span></span>
            <span v-if="row.ad" class="block text-[10.5px] text-[var(--t2)] font-mono truncate max-w-[220px]" :title="row.ad">{{ row.ad }}</span></span></span>
      </template>
      <template #cell-sonuc="{ row }"><span class="text-[11px] leading-snug" :class="row.durum === 'hata' ? 'text-rose-400' : 'text-[var(--t1)]'" :title="sonucMetni(row)">{{ kisalt(sonucMetni(row), 110) }}</span></template>
      <template #cell-durum="{ value }">
        <Rozet :tur="DURUM[value]?.tur || 'notr'" boyut="xs" sekil="rounded" :nokta="value === 'kuyrukta'" :nabiz="value === 'kuyrukta'">
          <FaIcon :icon="DURUM[value]?.ikon || 'circle-info'" class="h-2.5 w-2.5" :class="value === 'calisiyor' ? 'animate-spin' : ''" />{{ DURUM[value]?.ad || value }}</Rozet>
      </template>
      <template #cell-created_at="{ value }"><span class="font-mono text-[10.5px] text-[var(--t2)]" :title="tarih(value)">{{ goreliZaman(value) }}</span></template>
      <template #cell-islem="{ row }">
        <span class="flex items-center justify-end gap-1.5">
          <button v-if="row.indirilebilir && auth.can('inventory.export')" class="flex items-center gap-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-2.5 py-1 text-[11px] font-semibold text-white disabled:opacity-50" :disabled="!!indiriliyor[row.id]" @click="indir(row)">
            <FaIcon :icon="indiriliyor[row.id] ? 'spinner' : 'download'" class="h-3 w-3" :class="indiriliyor[row.id] ? 'animate-spin' : ''" />İndir</button>
          <button v-if="row.durum === 'tamamlandi' || row.durum === 'hata'" class="flex h-7 w-7 items-center justify-center rounded-lg border border-[var(--line)] text-[var(--t2)] hover:text-rose-400 hover:border-rose-500/40" title="Sil" @click="sil(row)"><FaIcon icon="trash" class="h-3 w-3" /></button>
        </span>
      </template>
    </DataTable>
  </div>
</template>
