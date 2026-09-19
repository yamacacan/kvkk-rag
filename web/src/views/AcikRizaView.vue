<script setup>
// Acik riza kayitlari (consents): ilgili kisilerin faaliyet bazinda verdigi / vermedigi /
// geri cektigi rizalar. Liste DataTable (sunucu tarafi sayfalama, kapsam filtreli);
// kayit formu modal: Acik Riza (faaliyet) *, TC Kimlik No *, Ad *, Soyad *, Onay Durumu *,
// Geri Cekme Tarihi (geri cekildiyse zorunlu), Onay Yontemi, Not.
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { acikRiza as api } from '../api';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import { debounce, goreliZaman, kisalt, sayi, tarih } from '../utils/format';
import DataTable from '../components/DataTable.vue';
import SearchableSelect from '../components/SearchableSelect.vue';
import Sayfalama from '../components/Sayfalama.vue';
import Rozet from '../components/Rozet.vue';
import KpiCard from '../components/KpiCard.vue';
import FiltreCipi from '../components/FiltreCipi.vue';
import Modal from '../components/Modal.vue';

const auth = useAuthStore();
const ui = useUiStore();
const router = useRouter();

const DURUM = {
  onaylandi: { ad: 'Onaylandı', tur: 'ok', ikon: 'user-check' },
  onaylanmadi: { ad: 'Onaylanmadı', tur: 'kritik', ikon: 'user-xmark' },
  geri_cekildi: { ad: 'Geri Çekildi', tur: 'uyari', ikon: 'user-slash' },
};
const YONTEM = {
  islak_imza: 'Islak imzalı form', elektronik: 'Elektronik onay (web / uygulama)', eposta: 'E-posta', sms: 'SMS',
  sozlu: 'Sözlü / telefon', diger: 'Diğer',
};
const SUTUNLAR = [
  { key: 'ad_soyad', label: 'Kişi', sortable: true },
  { key: 'faaliyet', label: 'Açık Rıza (Faaliyet)', sortable: true },
  { key: 'durum', label: 'Onay Durumu', width: 'w-36' },
  { key: 'onay_yontemi', label: 'Yöntem', width: 'w-40' },
  { key: 'onay_tarihi', label: 'Onay', width: 'w-32' },
  { key: 'geri_cekme_tarihi', label: 'Geri Çekme', width: 'w-32' },
  { key: 'notlar', label: 'Not' },
  { key: 'islem', label: '', width: 'w-24', align: 'right' },
];
const BOS = { faaliyet: '', tc_kimlik: '', ad: '', soyad: '', durum: 'onaylandi', onay_tarihi: '', geri_cekme_tarihi: '', onay_yontemi: '', notlar: '' };

const kayitlar = ref([]);
const toplam = ref(0);
const ozet = ref({ toplam: 0, onaylandi: 0, onaylanmadi: 0, geri_cekildi: 0 });
const kapsam = ref('');
const limit = ref(25);
const offset = ref(0);
const filtre = reactive({ faaliyet: '', durum: '', onay_yontemi: '', arama: '' });
const faaliyetSecenekleri = ref([]); // listede gecen faaliyetler (filtre)
const rizaFaaliyetleri = ref([]);    // envanterden secilebilir faaliyetler (form)
const yukleniyor = ref(false);
const form = ref(null);              // {id?, ...alanlar}
const hatalar = ref({});
const kaydediyor = ref(false);

const durumSecenek = Object.entries(DURUM).map(([k, v]) => ({ value: k, label: v.ad }));
const yontemSecenek = Object.entries(YONTEM).map(([k, v]) => ({ value: k, label: v }));
const aktifFiltreler = computed(() => Object.entries(filtre).filter(([, v]) => v));
const ETIKET = { faaliyet: 'Faaliyet', durum: 'Durum', onay_yontemi: 'Yöntem', arama: 'Arama' };
const filtreDeger = (k, v) => (k === 'durum' ? DURUM[v]?.ad : k === 'onay_yontemi' ? YONTEM[v] : v);
const rizaSecenek = computed(() => rizaFaaliyetleri.value.map((f) => ({
  value: f.faaliyet, label: f.faaliyet, alt: `${f.birim || '—'} · ${f.satir} kayıt`,
  badge: f.beyan?.durum === 'guncel' ? 'beyan güncel' : f.beyan ? 'beyan ' + f.beyan.durum : undefined,
  badgeClass: f.beyan?.durum === 'guncel' ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300',
})));
const seciliBeyan = computed(() => rizaFaaliyetleri.value.find((f) => f.faaliyet === form.value?.faaliyet)?.beyan || null);
const tcGecerli = (tc) => {
  if (!/^[1-9]\d{10}$/.test(tc)) return false;
  const h = [...tc].map(Number);
  const tek = h[0] + h[2] + h[4] + h[6] + h[8], cift = h[1] + h[3] + h[5] + h[7];
  return ((tek * 7 - cift) % 10 + 10) % 10 === h[9] && h.slice(0, 10).reduce((a, b) => a + b, 0) % 10 === h[10];
};

async function yukle() {
  yukleniyor.value = true;
  try {
    const d = await api.liste({ ...filtre, limit: limit.value, offset: offset.value });
    kayitlar.value = d.kayitlar; toplam.value = d.toplam; ozet.value = d.ozet; kapsam.value = d.kapsam;
    faaliyetSecenekleri.value = d.faaliyetler.map((f) => ({ value: f, label: f }));
  } catch (e) { ui.hata('Kayıtlar yüklenemedi', e.message); }
  finally { yukleniyor.value = false; }
}
const yukleGecikmeli = debounce(yukle, 320);
watch(() => [filtre.faaliyet, filtre.durum, filtre.onay_yontemi], () => { offset.value = 0; yukle(); });
watch(() => filtre.arama, () => { offset.value = 0; yukleGecikmeli(); });
function sifirla() { Object.assign(filtre, { faaliyet: '', durum: '', onay_yontemi: '', arama: '' }); }

async function faaliyetleriYukle() {
  try { rizaFaaliyetleri.value = (await api.faaliyetler()).faaliyetler; } catch {}
}
const simdi = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);
function yeni() { hatalar.value = {}; form.value = { ...BOS, onay_tarihi: simdi() }; faaliyetleriYukle(); }
async function duzenle(k) {
  hatalar.value = {};
  try {
    const d = (await api.getir(k.id)).kayit;
    form.value = { ...BOS, ...d, onay_tarihi: (d.onay_tarihi || '').slice(0, 16), geri_cekme_tarihi: (d.geri_cekme_tarihi || '').slice(0, 16), onay_yontemi: d.onay_yontemi || '', notlar: d.notlar || '' };
    faaliyetleriYukle();
  } catch (e) { ui.hata('Kayıt açılamadı', e.message); }
}
function dogrula() {
  const f = form.value, h = {};
  if (!f.faaliyet) h.faaliyet = 'Açık rıza (faaliyet) seçiniz.';
  if (!tcGecerli(String(f.tc_kimlik || '').trim())) h.tc_kimlik = 'Geçerli bir 11 haneli T.C. Kimlik Numarası giriniz.';
  if (!String(f.ad || '').trim()) h.ad = 'Ad zorunludur.';
  if (!String(f.soyad || '').trim()) h.soyad = 'Soyad zorunludur.';
  if (!f.durum) h.durum = 'Onay durumu seçiniz.';
  if (f.durum === 'geri_cekildi' && !f.geri_cekme_tarihi) h.geri_cekme_tarihi = 'Geri çekme tarihi zorunludur.';
  hatalar.value = h;
  return !Object.keys(h).length;
}
async function kaydet() {
  if (!dogrula()) return;
  kaydediyor.value = true;
  const f = form.value;
  const veri = { faaliyet: f.faaliyet, tc_kimlik: String(f.tc_kimlik).trim(), ad: f.ad.trim(), soyad: f.soyad.trim(), durum: f.durum,
    onay_tarihi: f.onay_tarihi || null, geri_cekme_tarihi: f.durum === 'geri_cekildi' ? f.geri_cekme_tarihi : null,
    onay_yontemi: f.onay_yontemi || null, notlar: f.notlar || null };
  try {
    if (f.id) { await api.guncelle(f.id, veri); ui.bildir('Açık rıza kaydı güncellendi.'); }
    else { await api.olustur(veri); ui.toast({ baslik: 'Kaydedildi', tur: 'ok', metin: `${veri.ad} ${veri.soyad} · ${DURUM[veri.durum].ad}` }); }
    form.value = null;
    await yukle();
  } catch (e) {
    if (e.errors) hatalar.value = Object.fromEntries(Object.entries(e.errors).map(([k, v]) => [k, v[0]]));
    ui.hata('Kaydedilemedi', e.message);
  } finally { kaydediyor.value = false; }
}
async function sil(k) {
  const ok = await ui.onay({ baslik: 'Açık rıza kaydı silinsin mi?', metin: `${k.ad_soyad} · ${k.faaliyet}`, tur: 'hata', onayMetni: 'Sil', tehlikeli: true, detay: 'Kayıt kalıcı olarak silinir; işlem denetim günlüğüne yazılır.' });
  if (!ok) return;
  try { await api.sil(k.id); ui.bildir('Kayıt silindi.'); yukle(); } catch (e) { ui.hata('Silinemedi', e.message); }
}
async function geriCek(k) {
  const ok = await ui.onay({ baslik: 'Rıza geri çekilsin mi?', metin: `${k.ad_soyad} kişisinin "${kisalt(k.faaliyet, 50)}" için verdiği açık rıza geri çekildi olarak işaretlenecek.`, tur: 'uyari', onayMetni: 'Geri çek' });
  if (!ok) return;
  try {
    const d = (await api.getir(k.id)).kayit;
    await api.guncelle(k.id, { faaliyet: d.faaliyet, tc_kimlik: d.tc_kimlik, ad: d.ad, soyad: d.soyad, durum: 'geri_cekildi',
      onay_tarihi: d.onay_tarihi, geri_cekme_tarihi: simdi(), onay_yontemi: d.onay_yontemi, notlar: d.notlar });
    ui.bildir('Rıza geri çekildi olarak işaretlendi.', 'uyari'); yukle();
  } catch (e) { ui.hata('Güncellenemedi', e.message); }
}
onMounted(yukle);
</script>

<template>
  <section class="space-y-5 max-w-[1780px] mx-auto">
    <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
      <div>
        <h1 class="text-2xl font-extrabold text-t-1 tracking-tight sm:text-3xl flex items-center gap-2.5"><FaIcon icon="clipboard-check" class="h-5 w-5 text-teal-400" />Açık Rıza Kayıtları
          <Rozet v-if="kapsam && kapsam !== 'all'" tur="uyari" mono nokta>kapsam: {{ kapsam }}</Rozet></h1>
        <p class="text-xs text-t-2 mt-1">İlgili kişilerin faaliyet bazında verdiği, vermediği ve geri çektiği açık rızalar (KVKK m.5/1). Beyan metinleri <router-link :to="{ name: 'faaliyet-belgeleri' }" class="text-indigo-400 hover:underline">Faaliyet Belgeleri</router-link>'nden envanterle otomatik güncellenir.</p>
      </div>
      <button v-if="auth.can('consents.create')" class="flex items-center gap-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/20" @click="yeni"><FaIcon icon="plus" class="h-3 w-3" />Yeni Açık Rıza Kaydı</button>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard baslik="Toplam Kayıt" :deger="sayi(ozet.toplam)" alt="kapsamınızdaki açık rıza kaydı" renk="indigo" />
      <KpiCard baslik="Onaylandı" :deger="sayi(ozet.onaylandi)" alt="geçerli açık rıza" renk="emerald" />
      <KpiCard baslik="Onaylanmadı" :deger="sayi(ozet.onaylanmadi)" alt="rıza verilmedi" renk="rose" />
      <KpiCard baslik="Geri Çekildi" :deger="sayi(ozet.geri_cekildi)" alt="ilgili kişi rızasını geri çekti" renk="amber" />
    </div>

    <div class="rounded-xl border border-line bg-bg-card overflow-hidden">
      <div class="border-b border-line bg-bg-1/80 px-4 py-3 flex flex-col md:flex-row md:items-center gap-2">
        <input v-model="filtre.arama" placeholder="Ad, soyad, TC veya faaliyet ara…" class="girdi md:max-w-xs">
        <div class="md:w-64"><SearchableSelect v-model="filtre.faaliyet" :options="faaliyetSecenekleri" placeholder="Tüm faaliyetler" size="sm" /></div>
        <div class="md:w-40"><SearchableSelect v-model="filtre.durum" :options="durumSecenek" placeholder="Tüm durumlar" size="sm" /></div>
        <div class="md:w-48"><SearchableSelect v-model="filtre.onay_yontemi" :options="yontemSecenek" placeholder="Tüm yöntemler" size="sm" /></div>
        <div v-if="aktifFiltreler.length" class="flex flex-wrap items-center gap-1.5">
          <FiltreCipi v-for="[k, v] in aktifFiltreler" :key="k" :etiket="ETIKET[k]" :deger="kisalt(filtreDeger(k, v), 26)" @kaldir="filtre[k] = ''" />
          <button class="text-[11px] text-indigo-400 hover:underline" @click="sifirla">Temizle</button>
        </div>
        <span class="text-[11px] text-t-3 md:ml-auto font-mono">{{ sayi(toplam) }} kayıt</span>
      </div>

      <DataTable :columns="SUTUNLAR" :rows="kayitlar" row-key="id" :loading="yukleniyor" dense :show-count="false" min-width="min-w-[1180px]"
        empty-text="Açık rıza kaydı yok. Sağ üstten yeni kayıt oluşturun.">
        <template #cell-ad_soyad="{ row }">
          <span class="flex items-center gap-2.5">
            <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg" :class="DURUM[row.durum]?.tur === 'ok' ? 'bg-emerald-500/15 text-emerald-400' : DURUM[row.durum]?.tur === 'kritik' ? 'bg-rose-500/15 text-rose-400' : 'bg-amber-500/15 text-amber-400'"><FaIcon :icon="DURUM[row.durum]?.ikon || 'user'" class="h-3.5 w-3.5" /></span>
            <span class="min-w-0"><span class="block text-xs font-semibold text-t-1 truncate">{{ row.ad_soyad }}</span><span class="block text-[10.5px] font-mono text-t-3">{{ row.tc_kimlik_maske }}</span></span>
          </span>
        </template>
        <template #cell-faaliyet="{ row }">
          <span class="block text-[11px] text-t-1 leading-snug">{{ row.faaliyet }}</span>
          <span v-if="row.birim" class="block text-[10px] text-t-3">{{ row.birim }}</span>
        </template>
        <template #cell-durum="{ value }"><Rozet :tur="DURUM[value]?.tur || 'notr'" boyut="xs" sekil="rounded" :nokta="value === 'onaylandi'">{{ DURUM[value]?.ad || value }}</Rozet></template>
        <template #cell-onay_yontemi="{ value }"><span class="text-[11px] text-t-2">{{ YONTEM[value] || '—' }}</span></template>
        <template #cell-onay_tarihi="{ value }"><span v-if="value" class="font-mono text-[10.5px] text-t-2" :title="tarih(value)">{{ tarih(value) }}</span><span v-else class="text-t-muted">—</span></template>
        <template #cell-geri_cekme_tarihi="{ value }"><span v-if="value" class="font-mono text-[10.5px] text-amber-400" :title="tarih(value)">{{ tarih(value) }}</span><span v-else class="text-t-muted">—</span></template>
        <template #cell-notlar="{ value }"><span class="text-[11px] text-t-3" :title="value">{{ kisalt(value || '—', 48) }}</span></template>
        <template #cell-islem="{ row }">
          <span class="flex items-center justify-end gap-1">
            <button v-if="auth.can('consents.update') && row.durum === 'onaylandi'" class="flex h-7 w-7 items-center justify-center rounded-md border border-line text-t-2 hover:text-amber-400 hover:border-amber-500/40" title="Rızayı geri çek" @click="geriCek(row)"><FaIcon icon="user-slash" class="h-3 w-3" /></button>
            <button v-if="auth.can('consents.update')" class="flex h-7 w-7 items-center justify-center rounded-md border border-line text-t-2 hover:text-indigo-400 hover:border-indigo-500/40" title="Düzenle" @click="duzenle(row)"><FaIcon icon="pen-to-square" class="h-3 w-3" /></button>
            <button v-if="auth.can('consents.delete')" class="flex h-7 w-7 items-center justify-center rounded-md border border-line text-t-2 hover:text-rose-400 hover:border-rose-500/40" title="Sil" @click="sil(row)"><FaIcon icon="trash" class="h-3 w-3" /></button>
          </span>
        </template>
      </DataTable>
      <div v-if="toplam > limit" class="px-4 py-3 border-t border-line flex items-center justify-between gap-3">
        <span class="text-[11px] text-t-3 font-mono">{{ offset + 1 }}–{{ Math.min(offset + limit, toplam) }} / {{ sayi(toplam) }}</span>
        <Sayfalama :toplam="toplam" :limit="limit" :offset="offset" @git="(o) => { offset = o; yukle(); }" />
      </div>
    </div>

    <!-- kayit formu -->
    <Modal v-if="form" :baslik="form.id ? 'Açık Rıza Kaydını Düzenle' : 'Yeni Açık Rıza Kaydı Oluştur'" alt-baslik="* zorunlu alanlar · TC kimlik numarası listede maskelenir, denetim günlüğüne maskeli yazılır" genislik="max-w-2xl" @kapat="form = null">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="md:col-span-2">
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Açık Rıza <span class="text-rose-400">*</span></label>
          <SearchableSelect v-model="form.faaliyet" :options="rizaSecenek" placeholder="Seçiniz — rıza verilen işleme faaliyeti" :input-class="hatalar.faaliyet ? '!border-rose-500/60' : ''" />
          <p v-if="hatalar.faaliyet" class="text-[10px] text-rose-400 mt-1">{{ hatalar.faaliyet }}</p>
          <p v-else-if="form.faaliyet" class="text-[10px] mt-1 flex items-center gap-1" :class="seciliBeyan?.durum === 'guncel' ? 'text-emerald-400' : 'text-t-3'">
            <FaIcon :icon="seciliBeyan?.durum === 'guncel' ? 'file-circle-check' : 'file-circle-exclamation'" class="h-3 w-3" />
            {{ seciliBeyan?.durum === 'guncel' ? 'Bu faaliyetin Açık Rıza Beyanı güncel' : seciliBeyan ? 'Beyan belgesi yenileniyor' : 'Beyan belgesi henüz üretilmedi' }}
            <button type="button" class="text-indigo-400 hover:underline" @click="router.push({ name: 'faaliyet-belgeleri', query: { faaliyet: form.faaliyet } })">Faaliyet Belgeleri →</button>
          </p>
        </div>
        <div>
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">TC Kimlik No <span class="text-rose-400">*</span></label>
          <input v-model="form.tc_kimlik" class="girdi font-mono" :class="hatalar.tc_kimlik ? '!border-rose-500/60' : ''" placeholder="11 haneli TC Kimlik No" inputmode="numeric" maxlength="11" @input="form.tc_kimlik = form.tc_kimlik.replace(/\D/g, '').slice(0, 11)">
          <p v-if="hatalar.tc_kimlik" class="text-[10px] text-rose-400 mt-1">{{ hatalar.tc_kimlik }}</p>
        </div>
        <div>
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Onay Durumu <span class="text-rose-400">*</span></label>
          <div class="flex rounded-lg border border-line bg-bg-2 p-0.5 text-[11px]">
            <button v-for="(d, k) in DURUM" :key="k" type="button" class="flex-1 flex items-center justify-center gap-1 rounded-md py-1.5"
              :class="form.durum === k ? (d.tur === 'ok' ? 'bg-emerald-500/20 text-emerald-300' : d.tur === 'kritik' ? 'bg-rose-500/20 text-rose-300' : 'bg-amber-500/20 text-amber-300') + ' font-semibold' : 'text-t-3 hover:text-t-1'"
              @click="form.durum = k; if (k === 'geri_cekildi' && !form.geri_cekme_tarihi) form.geri_cekme_tarihi = simdi();"><FaIcon :icon="d.ikon" class="h-3 w-3" />{{ d.ad }}</button>
          </div>
          <p v-if="hatalar.durum" class="text-[10px] text-rose-400 mt-1">{{ hatalar.durum }}</p>
        </div>
        <div>
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Ad <span class="text-rose-400">*</span></label>
          <input v-model="form.ad" class="girdi" :class="hatalar.ad ? '!border-rose-500/60' : ''" placeholder="Ad">
          <p v-if="hatalar.ad" class="text-[10px] text-rose-400 mt-1">{{ hatalar.ad }}</p>
        </div>
        <div>
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Soyad <span class="text-rose-400">*</span></label>
          <input v-model="form.soyad" class="girdi" :class="hatalar.soyad ? '!border-rose-500/60' : ''" placeholder="Soyad">
          <p v-if="hatalar.soyad" class="text-[10px] text-rose-400 mt-1">{{ hatalar.soyad }}</p>
        </div>
        <div>
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Onay Tarihi</label>
          <input v-model="form.onay_tarihi" type="datetime-local" class="girdi font-mono">
        </div>
        <div>
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Geri Çekme Tarihi <span v-if="form.durum === 'geri_cekildi'" class="text-rose-400">*</span></label>
          <input v-model="form.geri_cekme_tarihi" type="datetime-local" class="girdi font-mono" :class="hatalar.geri_cekme_tarihi ? '!border-rose-500/60' : ''" :disabled="form.durum !== 'geri_cekildi'" placeholder="gg.aa.yyyy --:--">
          <p v-if="hatalar.geri_cekme_tarihi" class="text-[10px] text-rose-400 mt-1">{{ hatalar.geri_cekme_tarihi }}</p>
          <p v-else-if="form.durum !== 'geri_cekildi'" class="text-[10px] text-t-muted mt-1">Yalnızca "Geri Çekildi" durumunda girilir.</p>
        </div>
        <div>
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Onay Yöntemi</label>
          <SearchableSelect v-model="form.onay_yontemi" :options="yontemSecenek" placeholder="Seçiniz" />
        </div>
        <div class="md:col-span-2">
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Not</label>
          <textarea v-model="form.notlar" class="girdi min-h-[72px]" placeholder="Form numarası, kanal, ek açıklama…" maxlength="2000"></textarea>
        </div>
      </div>
      <template #alt>
        <span class="text-[10.5px] text-t-3">Kayıt denetim günlüğüne yazılır.</span>
        <span class="flex items-center gap-2">
          <button class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-bg-3 border border-line text-t-2 hover:text-t-1" @click="form = null"><FaIcon icon="xmark" class="h-3 w-3" />Vazgeç</button>
          <button class="flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-60" :disabled="kaydediyor" @click="kaydet">
            <FaIcon :icon="kaydediyor ? 'spinner' : 'floppy-disk'" class="h-3 w-3" :class="kaydediyor ? 'animate-spin' : ''" />{{ kaydediyor ? 'Kaydediliyor…' : form.id ? 'Güncelle' : 'Kaydet' }}</button>
        </span>
      </template>
    </Modal>
  </section>
</template>
