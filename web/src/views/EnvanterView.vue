<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { envanter as envApi } from '../api';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import { useTaksonomiStore } from '../stores/taksonomi';
import { kisalt, sayi, seviye, debounce } from '../utils/format';
import Rozet from '../components/Rozet.vue';
import FiltreCipi from '../components/FiltreCipi.vue';
import KpiCard from '../components/KpiCard.vue';
import Sayfalama from '../components/Sayfalama.vue';
import EnvanterForm from '../components/EnvanterForm.vue';
import DataTable from '../components/DataTable.vue';
import SearchableSelect from '../components/SearchableSelect.vue';
import Iskelet from '../components/Iskelet.vue';
import Modal from '../components/Modal.vue';
import EnvanterIslemleri from '../components/EnvanterIslemleri.vue';

// Tablo sutunlari: hucre icerikleri #cell-<key> slotlarinda, filtreler #filter-<key> slotlarinda
const SUTUNLAR = [
  { key: 'satir_no', label: 'Satır', width: 'w-14', sortable: true },
  { key: 'birim', label: 'Birim', width: 'w-44', sortable: true },
  { key: 'faaliyet', label: 'Faaliyet', width: 'w-48', sortable: true },
  { key: 'veri_kategorisi', label: 'Veri Kategorisi', width: 'w-36', sortable: true },
  { key: 'hukuki_sebep', label: 'Hukuki Sebep', width: 'min-w-[220px]' },
  { key: 'saklama_suresi', label: 'Saklama', width: 'w-32' },
  { key: 'risk_skoru', label: 'Risk', width: 'w-28', sortable: true },
  { key: 'bulgular', label: 'Uyum Bulguları', width: 'min-w-[260px]' },
  { key: 'islem', label: 'İşlem', width: 'w-16', align: 'right' },
];
const SEVIYE_SECENEK = [{ value: 'kritik', label: 'Kritik' }, { value: 'yuksek', label: 'Yüksek' }, { value: 'orta', label: 'Orta' }, { value: 'dusuk', label: 'Düşük' }];

const props = defineProps({ mod: { type: String, default: 'envanter' } }); // envanter | bulgular
const auth = useAuthStore();
const ui = useUiStore();
const route = useRoute();

const TABS = [
  { id: 'tum',    ad: 'Tüm Kayıtlar',        nokta: 'bg-indigo-400',  filtre: {} },
  { id: 'kritik', ad: 'Kritik',              nokta: 'bg-rose-500',    filtre: { seviye: 'kritik' } },
  { id: 'yuksek', ad: 'Yüksek',              nokta: 'bg-amber-400',   filtre: { seviye: 'yuksek' } },
  { id: 'ozel',   ad: 'Özel Nitelikli Risk', nokta: 'bg-fuchsia-400', filtre: { seviye: 'kritik', arama: 'Ceza Mahkumiyeti' } },
];
const BOS_FILTRE = { birim: '', faaliyet: '', veri_kategorisi: '', hukuki_sebep: '', seviye: '', arama: '' };
const ETIKET = { birim: 'Birim', faaliyet: 'Faaliyet', veri_kategorisi: 'Kategori', hukuki_sebep: 'Sebep', seviye: 'Risk', arama: 'Arama' };

const filtre = reactive({ ...BOS_FILTRE });
const tab = ref('tum');
const limit = ref(50);
const offset = ref(0);
const ozet = ref(null);
const liste = ref({ satirlar: [], toplam: 0, filtrelenmis: 0, kapsam: null });
const yukleniyor = ref(false);
const hata = ref('');
const secili = ref(new Set());
const form = ref(null); // {mevcut, onDoldur} -> modal acik

const bulgularModu = computed(() => props.mod === 'bulgular');
const baslik = computed(() => (bulgularModu.value ? 'Uyum Bulguları' : 'Kişisel Veri İşleme Envanteri'));
const aktifFiltreler = computed(() => Object.entries(filtre).filter(([, v]) => v));
const tabSayilari = computed(() => {
  const o = ozet.value;
  if (!o) return {};
  return { tum: o.satir, kritik: o.seviye.kritik || 0, yuksek: o.seviye.yuksek || 0, ozel: o.kod['ENV-004'] || 0 };
});
const uyumYuzde = computed(() => (ozet.value ? (ozet.value.uyum_orani * 100).toFixed(1) : '0.0'));
// Filtre secenekleri: ozetten (deger + adet) aranabilir listeye
const secenek = (liste) => (liste || []).map((x) => ({ value: x.deger, label: x.deger, count: x.adet }));
const birimSecenek = computed(() => secenek(ozet.value?.birim));
const faaliyetSecenek = computed(() => secenek(ozet.value?.faaliyet));
const kategoriSecenek = computed(() => secenek(ozet.value?.veri_kategorisi));
// hukuki sebep -> KVKK maddesi rozeti (m.5 genel / m.6 ozel nitelikli / m.28 istisna); ayni ad iki maddede olabilir
const tax = useTaksonomiStore();
const MADDE_ROZET = { 5: 'bg-sky-500/15 text-sky-300', 6: 'bg-fuchsia-500/20 text-fuchsia-300', 28: 'bg-amber-500/15 text-amber-300' };
const sebepMaddeleri = computed(() => {
  const m = new Map();
  (tax.veri?.hukuki_sebep_detay || []).forEach((d) => { if (d.madde) m.set(d.ad, [...(m.get(d.ad) || []), d.madde]); });
  return m;
});
const sebepMadde = (ad) => sebepMaddeleri.value.get(String(ad || '').trim()) || [];
const sayfaBilgi = computed(() => {
  const l = liste.value;
  const son = Math.min(offset.value + limit.value, l.filtrelenmis);
  return { toplam: sayi(l.toplam), bas: sayi(l.filtrelenmis ? offset.value + 1 : 0), son: sayi(son), filtrelenmis: sayi(l.filtrelenmis) };
});

function seviyeSayilari(r) {
  const s = {};
  (r.bulgular || []).forEach((b) => { s[b.seviye] = (s[b.seviye] || 0) + 1; });
  return s;
}

async function ozetYukle() {
  try { ozet.value = await envApi.ozet(); } catch (e) { hata.value = e.message; }
}

async function tabloYukle() {
  yukleniyor.value = true; hata.value = '';
  try {
    liste.value = await envApi.liste({ ...filtre, limit: limit.value, offset: offset.value });
  } catch (e) { hata.value = e.message; liste.value = { satirlar: [], toplam: 0, filtrelenmis: 0 }; }
  finally { yukleniyor.value = false; }
}

const tabloYukleGecikmeli = debounce(tabloYukle, 320);

function filtreAta(k, v, gecikme = false) {
  filtre[k] = v; offset.value = 0;
  gecikme ? tabloYukleGecikmeli() : tabloYukle();
}

function tabSec(t) {
  tab.value = t.id;
  Object.assign(filtre, BOS_FILTRE, t.filtre);
  offset.value = 0; tabloYukle();
}

function sifirla() {
  Object.assign(filtre, BOS_FILTRE); tab.value = 'tum'; offset.value = 0; tabloYukle();
}

function yenile() { ozetYukle(); tabloYukle(); }

function sayfayaGit(o) { offset.value = o; tabloYukle(); }

function limitDegis(e) { limit.value = +e.target.value; offset.value = 0; tabloYukle(); }

// ---- secim / toplu islem ----
async function tumunuSec() {
  // Filtreye uyan tum satirlari secer (sayfadakiler degil)
  try {
    const d = await envApi.liste({ ...filtre, limit: 10000, offset: 0 });
    secili.value = new Set([...secili.value, ...d.satirlar.map((r) => r.satir_no)]);
  } catch (e) { ui.bildir('Seçilemedi: ' + e.message, 'hata'); }
}
async function topluSil() {
  const n = secili.value.size;
  if (!n) return;
  const onay = await ui.onay({
    baslik: `${sayi(n)} kayıt silinsin mi?`, tur: 'hata', onayMetni: 'Evet, sil',
    metin: 'Seçili envanter satırları kalıcı olarak silinir; değişiklik geçmişi korunur.',
    detay: 'Yetki kapsamınız dışındaki satırlar atlanır ve silinmez.',
  });
  if (!onay) return;
  try {
    const d = await envApi.topluSil([...secili.value]);
    secili.value = new Set();
    await ozetYukle(); await tabloYukle();
    ui.toast({ baslik: 'Silindi', tur: d.yetkisiz?.length ? 'uyari' : 'ok',
      metin: `${d.adet} kayıt silindi.` + (d.yetkisiz?.length ? ` ${d.yetkisiz.length} kayıt yetki kapsamı dışında, atlandı.` : '') });
  } catch (e) { ui.bildir('Silinemedi: ' + e.message, 'hata'); }
}
// ---- kuyruklu isler: Excel disa/ice aktarim, yeniden indeksleme (EnvanterIslemleri paneli izler) ----
const islemlerRef = ref(null);
const iceAktarModal = ref(false);
const iceAktar = reactive({ dosya: null, mod: 'ekle', gonderiliyor: false });
const tamKapsamSilme = computed(() => auth.can('inventory.delete') && auth.scope('inventory', 'delete') === 'all');

async function excelIndir(seciliSatirlar = false) {
  // Dosya arka planda uretilir; hazir olunca bildirim gelir, Arka Plan İşlemleri'nden indirilir
  const veri = { ...filtre, sadece_bulgulu: undefined, kurum: 'ÖRNEK TEKNOLOJİ A.Ş.' };
  if (seciliSatirlar) veri.satir_no = [...secili.value];
  try {
    const d = await envApi.disaAktar(veri);
    islemlerRef.value?.ekle(d.islem);
    ui.toast({ baslik: 'Kuyruğa alındı', tur: 'bilgi', metin: seciliSatirlar ? `${sayi(secili.value.size)} seçili kayıt Excel'e aktarılıyor; hazır olunca bildirim alacaksınız.` : `${sayi(liste.value.filtrelenmis)} kayıt Excel'e aktarılıyor; hazır olunca bildirim alacaksınız.` });
  } catch (e) { ui.hata('Dışa aktarım kuyruğa alınamadı', e.message); }
}
function dosyaSec(e) { iceAktar.dosya = e.target.files?.[0] || null; }
async function iceAktarGonder() {
  if (!iceAktar.dosya) { ui.bildir('Önce bir .xlsx dosyası seçin.', 'uyari'); return; }
  if (iceAktar.mod === 'degistir') {
    const ok = await ui.onay({ baslik: 'Tüm envanter değiştirilsin mi?', tur: 'hata', onayMetni: 'Evet, değiştir',
      metin: 'Mevcut tüm envanter satırları silinir ve dosyadaki satırlar yüklenir. Değişiklik geçmişi korunur.',
      detay: 'Bu işlem geri alınamaz; emin değilseniz "Mevcut envantere ekle" seçin.' });
    if (!ok) return;
  }
  iceAktar.gonderiliyor = true;
  try {
    const d = await envApi.iceAktar(iceAktar.dosya, iceAktar.mod);
    islemlerRef.value?.ekle(d.islem);
    iceAktarModal.value = false; iceAktar.dosya = null; iceAktar.mod = 'ekle';
    ui.toast({ baslik: 'Kuyruğa alındı', tur: 'bilgi', metin: `${d.islem.ad} arka planda işleniyor; bitince bildirim alacaksınız.` });
  } catch (e) { ui.hata('İçe aktarım başlatılamadı', e.message); }
  finally { iceAktar.gonderiliyor = false; }
}
async function yenidenIndeksle() {
  const ok = await ui.onay({ baslik: 'Vektör indeksi yeniden kurulsun mu?', metin: 'Anlamsal arama indeksi sıfırdan oluşturulur; envanter büyüklüğüne göre birkaç dakika sürebilir.', tur: 'bilgi', onayMetni: 'Başlat' });
  if (!ok) return;
  try { const d = await envApi.yenidenIndeksle(); islemlerRef.value?.ekle(d.islem); ui.bildir('İndeksleme kuyruğa alındı.', 'bilgi'); }
  catch (e) { ui.hata('Başlatılamadı', e.message); }
}
function islemTamamlandi(i) {
  // ice aktarim bitti -> tablo ve ozet tazelenir
  if (i.tur === 'ice_aktar') { ozetYukle(); tabloYukle(); }
}

// ---- form ----
function formAc(mevcut = null, onDoldur = null) { form.value = { mevcut, onDoldur }; }
function formKaydedildi() { ozetYukle(); tabloYukle(); }

watch(() => props.mod, () => baslat());

function baslat() {
  secili.value = new Set();
  if (bulgularModu.value) { tab.value = 'kritik'; Object.assign(filtre, BOS_FILTRE, { seviye: 'kritik' }); }
  else { tab.value = 'tum'; Object.assign(filtre, BOS_FILTRE, route.query.arama ? { arama: String(route.query.arama) } : {}); }
  offset.value = 0;
  ozetYukle(); tabloYukle();
}

onMounted(() => { baslat(); tax.yukle().catch(() => {}); });
</script>

<template>
  <section>
    <div class="mb-5">
      <div class="flex items-center gap-2 text-xs text-[var(--t1)] mb-1">
        <span>Denetim</span><span class="text-[var(--t2)]">/</span>
        <span class="text-white font-semibold">{{ bulgularModu ? 'Uyum Bulguları' : 'Veri Envanteri' }}</span>
      </div>
      <h1 class="text-2xl font-extrabold text-white tracking-tight sm:text-3xl flex items-center gap-3">
        <span>{{ baslik }}</span>
        <span class="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono">{{ ozet ? sayi(ozet.satir) + ' kayıt' : '—' }}</span>
        <Rozet v-if="liste.kapsam && liste.kapsam !== 'all'" tur="uyari" mono nokta title="Yetki kapsamınız">kapsam: {{ liste.kapsam }}</Rozet>
      </h1>
      <p class="text-xs text-[var(--t1)] mt-1">Her sütunda bağımsız filtre, mevzuat dayanaklı uyum bulguları ve risk skorlaması.</p>
    </div>

    <div v-if="!ozet && !hata" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6" aria-busy="true">
      <div v-for="i in 4" :key="i" class="p-4 rounded-xl border border-[var(--line)] bg-[var(--bg-2)]">
        <div class="flex items-center justify-between mb-3"><Iskelet class="h-3 w-24" /><Iskelet class="h-4 w-12" /></div>
        <Iskelet class="h-7 w-20 mb-3" /><Iskelet class="h-2.5 w-28" />
      </div>
    </div>
    <div v-else-if="ozet" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <KpiCard baslik="Envanter Kaydı" :deger="sayi(ozet.satir)" :alt="`${ozet.birim.length}+ birim, ${ozet.faaliyet.length}+ faaliyet`" renk="indigo" rozet="VERBİS" />
      <KpiCard baslik="Kritik Bulgu" :deger="sayi(ozet.seviye.kritik || 0)" alt="mevzuata aykırılık riski" renk="rose" rozet="acil" />
      <KpiCard baslik="Yüksek Bulgu" :deger="sayi(ozet.seviye.yuksek || 0)" alt="tamamlanması gereken alanlar" renk="amber" />
      <KpiCard baslik="Uyum Oranı" :deger="`%${uyumYuzde}`" :alt="`${sayi(ozet.temiz_satir)} kayıt bulgusuz`" :renk="+uyumYuzde > 50 ? 'emerald' : 'rose'" />
    </div>

    <div class="rounded-2xl border border-[var(--line)] bg-[var(--bg-2)] shadow-2xl overflow-hidden mb-8">
      <div class="border-b border-[var(--line)] bg-[var(--bg-1)]/70 px-5 pt-3.5">
        <div class="flex items-center gap-2 mb-3">
          <span class="w-2.5 h-2.5 rounded-full bg-indigo-500"></span>
          <h2 class="text-sm font-bold text-white tracking-wide">Envanter Kayıtları</h2>
          <div class="ml-auto flex items-center gap-2">
            <button v-if="auth.can('inventory.create')" class="h-8 px-3 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 border border-sky-500/30 text-[11px] font-semibold flex items-center gap-1.5" @click="iceAktarModal = true"><FaIcon icon="file-arrow-up" class="h-3 w-3" />İçe Aktar</button>
            <button v-if="auth.can('inventory.export')" class="h-8 px-3 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-[11px] font-semibold flex items-center gap-1.5" title="Filtreye uyan kayıtlar arka planda Excel'e aktarılır" @click="excelIndir(false)"><FaIcon icon="file-excel" class="h-3 w-3" />Excel'e Aktar</button>
            <button v-if="auth.can('inventory.create')" class="h-8 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-bold shadow-lg shadow-indigo-600/30 flex items-center gap-1.5" @click="formAc()"><FaIcon icon="plus" class="h-3 w-3" />Yeni Kayıt</button>
            <button class="h-8 px-2.5 rounded-lg bg-[var(--bg-3)] hover:bg-[var(--line-2)] border border-[var(--line)] text-[11px] font-semibold text-[var(--t1)] hover:text-white" @click="yenile">Yenile</button>
          </div>
        </div>
        <div class="flex items-center gap-2 overflow-x-auto border-t border-[var(--line)] pt-2">
          <button v-for="t in TABS" :key="t.id" @click="tabSec(t)"
            class="flex items-center gap-2 px-3 py-2 text-xs whitespace-nowrap border-b-2"
            :class="tab === t.id ? 'border-indigo-500 text-white font-bold' : 'border-transparent text-[var(--t1)] hover:text-white font-semibold'">
            <span class="w-1.5 h-1.5 rounded-full" :class="t.nokta"></span>{{ t.ad }}
            <span class="rounded-full bg-[var(--bg-3)] px-1.5 text-[10.5px] font-mono">{{ sayi(tabSayilari[t.id] || 0) }}</span>
          </button>
        </div>
      </div>

      <div class="p-3.5 border-b border-[var(--line)] bg-[var(--bg-inset)]/60 flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div class="flex items-center gap-3 flex-1 max-w-md">
          <input :value="filtre.arama" @input="filtreAta('arama', $event.target.value, true)" type="text" placeholder="Genel arama: birim, faaliyet, veri, sebep…"
                 class="girdi !bg-[var(--bg-2)] !px-3">
          <span class="text-xs text-[var(--t2)] whitespace-nowrap font-mono"><strong class="text-white">{{ sayi(liste.filtrelenmis) }}</strong> sonuç</span>
        </div>
        <div v-if="aktifFiltreler.length" class="flex flex-wrap items-center gap-1.5">
          <span class="text-[11px] font-bold uppercase tracking-wider text-[var(--t2)] mr-1">Filtreler:</span>
          <FiltreCipi v-for="[k, v] in aktifFiltreler" :key="k" :etiket="ETIKET[k]" :deger="kisalt(v, 26)" :tur="k === 'seviye' ? 'kritik' : 'mor'" @kaldir="filtreAta(k, '')" />
          <button class="text-[11px] font-semibold text-rose-400 hover:text-rose-300 hover:underline px-1.5" @click="sifirla">Tümünü temizle</button>
        </div>
      </div>

      <div v-if="secili.size" class="px-3.5 py-2 border-b border-[var(--line)] bg-indigo-500/10 flex items-center gap-3">
        <span class="text-xs font-bold text-white">{{ sayi(secili.size) }} kayıt seçildi</span>
        <button class="text-[11px] font-semibold text-indigo-300 hover:text-white underline" @click="tumunuSec">Filtredeki tümünü seç</button>
        <button class="text-[11px] font-semibold text-[var(--t1)] hover:text-white" @click="secili = new Set()">Seçimi temizle</button>
        <div class="ml-auto flex items-center gap-2">
          <button v-if="auth.can('inventory.export')" class="px-2.5 py-1 rounded-md text-[11px] font-semibold bg-[var(--bg-3)] border border-[var(--line)] text-[var(--t1)] hover:text-white" @click="excelIndir(true)">Seçilenleri dışa aktar</button>
          <button v-if="auth.can('inventory.delete')" class="px-3 py-1 rounded-md text-[11px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30" @click="topluSil"><FaIcon icon="trash" class="h-3 w-3 mr-1" />Seçilenleri Sil</button>
        </div>
      </div>

      <DataTable :columns="SUTUNLAR" :rows="liste.satirlar" row-key="satir_no" selectable v-model:selected="secili"
        :loading="yukleniyor" :error="hata" empty-text="Filtreye uyan kayıt yok." min-width="min-w-[1360px]"
        :row-class="(r) => seviyeSayilari(r).kritik > 0 ? 'bg-rose-500/5 border-l-2 border-l-rose-500' : 'bg-[var(--bg-2)]/30'">
        <!-- filtre satiri: aranabilir secimler -->
        <template #filter-satir_no><span class="block text-center text-[var(--t2)] font-mono text-[11px]">#</span></template>
        <template #filter-birim>
          <SearchableSelect :model-value="filtre.birim" :options="birimSecenek" size="sm" placeholder="Tüm birimler" @update:model-value="filtreAta('birim', $event || '')" />
        </template>
        <template #filter-faaliyet>
          <SearchableSelect :model-value="filtre.faaliyet" :options="faaliyetSecenek" size="sm" placeholder="Tüm faaliyetler" @update:model-value="filtreAta('faaliyet', $event || '')" />
        </template>
        <template #filter-veri_kategorisi>
          <SearchableSelect :model-value="filtre.veri_kategorisi" :options="kategoriSecenek" size="sm" placeholder="Tüm kategoriler" @update:model-value="filtreAta('veri_kategorisi', $event || '')" />
        </template>
        <template #filter-hukuki_sebep>
          <input :value="filtre.hukuki_sebep" @input="filtreAta('hukuki_sebep', $event.target.value, true)" type="text" placeholder="Sebepte filtrele…" class="girdi !rounded-lg !px-2 !py-1 text-[11px] !bg-[var(--bg-2)]">
        </template>
        <template #filter-saklama_suresi><span class="text-[10px] text-[var(--t2)] font-mono">saklama süresi</span></template>
        <template #filter-risk_skoru>
          <SearchableSelect :model-value="filtre.seviye" :options="SEVIYE_SECENEK" size="sm" placeholder="Tüm riskler" input-class="!border-rose-500/40" @update:model-value="filtreAta('seviye', $event || '')" />
        </template>
        <template #filter-bulgular><span class="text-[10px] text-[var(--t2)]">dayanak KVKK maddesi</span></template>
        <template #filter-islem>
          <button class="px-2 py-1 text-[10.5px] font-semibold text-indigo-400 hover:text-white rounded bg-[var(--bg-3)] border border-[var(--line)]" @click="sifirla">Sıfırla</button>
        </template>

        <!-- hucreler -->
        <template #cell-satir_no="{ value }"><span class="font-mono text-[11px] text-indigo-400 font-bold">{{ value }}</span></template>
        <template #cell-birim="{ value }"><span class="text-[11px] font-semibold text-white block leading-tight">{{ kisalt(value, 34) }}</span></template>
        <template #cell-faaliyet="{ value }"><span class="text-[11px] text-slate-300 block leading-tight">{{ kisalt(value, 38) }}</span></template>
        <template #cell-veri_kategorisi="{ value }"><span class="inline-block px-1.5 py-0.5 rounded text-[10.5px] font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">{{ kisalt(value, 22) }}</span></template>
        <template #cell-hukuki_sebep="{ value }">
          <span class="text-[10.5px] text-[var(--t1)] leading-snug block">{{ kisalt(value, 76) }}</span>
          <span v-for="m in sebepMadde(value)" :key="m" class="inline-block mt-0.5 mr-1 px-1 rounded text-[9.5px] font-semibold" :class="MADDE_ROZET[m]">m.{{ m }}</span>
        </template>
        <template #cell-saklama_suresi="{ value }">
          <span v-if="value" class="text-[10.5px] font-mono text-slate-300">{{ kisalt(value, 18) }}</span>
          <span v-else class="text-[10.5px] text-rose-400 font-semibold">— yok —</span>
        </template>
        <template #cell-risk_skoru="{ row, value }"><span class="font-mono text-xs font-extrabold" :class="seviyeSayilari(row).kritik > 0 ? 'text-rose-400' : 'text-amber-400'">{{ value }}</span></template>
        <template #cell-bulgular="{ row }">
          <div class="flex flex-wrap gap-1 mb-1">
            <Rozet v-for="(adet, k) in seviyeSayilari(row)" :key="k" :tur="k" boyut="xs" sekil="rounded" :nokta="k === 'kritik'" :nabiz="k === 'kritik'">{{ seviye(k).etiket }} {{ adet }}</Rozet>
          </div>
          <div v-for="(b, i) in (row.bulgular || []).slice(0, 3)" :key="i" class="text-[10.5px] leading-snug">
            <span class="text-slate-300">{{ b.baslik }}</span>
            <span class="text-[var(--t2)] font-mono"> · {{ kisalt(b.dayanak, 42) }}</span>
          </div>
          <div v-if="(row.bulgular || []).length > 3" class="text-[10px] text-[var(--t2)] mt-0.5">+{{ row.bulgular.length - 3 }} bulgu daha</div>
        </template>
        <template #cell-islem="{ row }">
          <button class="p-1 rounded text-[var(--t2)] hover:text-white hover:bg-[var(--bg-3)]" title="Detay / Düzenle" @click="formAc(row)">
            <FaIcon icon="pen-to-square" class="h-3.5 w-3.5" />
          </button>
        </template>
        <template #footer></template>
      </DataTable>

      <div class="p-4 bg-[var(--bg-1)]/80 border-t border-[var(--line)] flex flex-col sm:flex-row items-center justify-between gap-4">
        <div class="flex items-center gap-4 text-xs text-[var(--t1)]">
          <div class="flex items-center gap-2"><span>Sayfa boyutu:</span>
            <select :value="limit" @change="limitDegis" class="bg-[var(--bg-inset)] border border-[var(--line)] rounded-md px-2 py-1 text-xs text-white focus:outline-none">
              <option>25</option><option>50</option><option>100</option></select></div>
          <div class="hidden md:block text-[var(--t2)]">
            Toplam <span class="font-mono font-bold text-white">{{ sayfaBilgi.toplam }}</span> kayıttan
            <span class="font-mono text-white">{{ sayfaBilgi.bas }} - {{ sayfaBilgi.son }}</span> arası
            (<span class="text-indigo-400 font-semibold font-mono">{{ sayfaBilgi.filtrelenmis }} filtrelenmiş</span>)
          </div>
        </div>
        <Sayfalama :toplam="liste.filtrelenmis" :limit="limit" :offset="offset" @git="sayfayaGit" />
      </div>
    </div>

    <!-- arka plan islemleri (kuyruk): disa/ice aktarim, indeksleme -->
    <EnvanterIslemleri v-if="!bulgularModu" ref="islemlerRef" class="mb-8" @tamamlandi="islemTamamlandi" @yeniden-indeksle="yenidenIndeksle" />

    <EnvanterForm v-if="form" :mevcut="form.mevcut" :on-doldur="form.onDoldur"
      @kapat="form = null" @kaydedildi="formKaydedildi" @silindi="formKaydedildi" />

    <!-- Excel'den ice aktarim -->
    <Modal v-if="iceAktarModal" baslik="Excel'den İçe Aktar" alt-baslik="Sütun adları dışa aktarılan dosyayla aynı olmalı (Birim, Faaliyet, Veri Kategorisi, Kişisel Veri…)" genislik="max-w-lg" @kapat="iceAktarModal = false">
      <div class="space-y-4">
        <label class="block rounded-xl border-2 border-dashed border-line hover:border-indigo-500/60 bg-bg-2 px-4 py-6 text-center cursor-pointer">
          <FaIcon icon="file-excel" class="h-6 w-6 mx-auto mb-2 text-emerald-400" />
          <span class="block text-xs font-semibold text-t-1">{{ iceAktar.dosya ? iceAktar.dosya.name : '.xlsx dosyası seçin' }}</span>
          <span class="block text-[10.5px] text-t-3 mt-1">{{ iceAktar.dosya ? `${Math.round(iceAktar.dosya.size / 1024)} KB` : 'en fazla 20 MB · ilk sayfa okunur' }}</span>
          <input type="file" accept=".xlsx" class="hidden" @change="dosyaSec">
        </label>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <label class="flex items-start gap-2 rounded-lg border p-3 cursor-pointer" :class="iceAktar.mod === 'ekle' ? 'border-indigo-500 bg-indigo-500/10' : 'border-line bg-bg-2'">
            <input v-model="iceAktar.mod" type="radio" value="ekle" class="mt-0.5 accent-indigo-500">
            <span><span class="block text-xs font-semibold text-t-1">Mevcut envantere ekle</span><span class="block text-[10.5px] text-t-3">Satırlar yeni kayıt olarak eklenir.</span></span>
          </label>
          <label class="flex items-start gap-2 rounded-lg border p-3" :class="[iceAktar.mod === 'degistir' ? 'border-rose-500 bg-rose-500/10' : 'border-line bg-bg-2', tamKapsamSilme ? 'cursor-pointer' : 'opacity-50 cursor-not-allowed']">
            <input v-model="iceAktar.mod" type="radio" value="degistir" class="mt-0.5 accent-rose-500" :disabled="!tamKapsamSilme">
            <span><span class="block text-xs font-semibold text-t-1">Tümünü değiştir</span><span class="block text-[10.5px] text-t-3">{{ tamKapsamSilme ? 'Önce tüm envanter silinir, sonra dosya yüklenir.' : 'Tam kapsamlı silme yetkisi gerekir.' }}</span></span>
          </label>
        </div>
        <p v-if="auth.scope('inventory', 'create') === 'department'" class="text-[10.5px] text-amber-400 flex items-center gap-1"><FaIcon icon="triangle-exclamation" class="h-3 w-3" />Yalnızca kendi biriminizin satırları eklenir; diğerleri atlanır ve sonuçta raporlanır.</p>
      </div>
      <template #alt>
        <span class="text-[10.5px] text-t-3">Satırlar arka planda eklenir; her satır için uyum denetimi çalışır.</span>
        <span class="flex items-center gap-2">
          <button class="px-3 py-1.5 rounded-lg border border-line bg-bg-2 text-xs text-t-2 hover:text-t-1" @click="iceAktarModal = false"><FaIcon icon="xmark" class="h-3 w-3 mr-1" />Vazgeç</button>
          <button class="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-bold text-white disabled:opacity-50 flex items-center gap-1.5" :disabled="!iceAktar.dosya || iceAktar.gonderiliyor" @click="iceAktarGonder">
            <FaIcon :icon="iceAktar.gonderiliyor ? 'spinner' : 'file-arrow-up'" class="h-3 w-3" :class="iceAktar.gonderiliyor ? 'animate-spin' : ''" />Kuyruğa al</button>
        </span>
      </template>
    </Modal>
  </section>
</template>
