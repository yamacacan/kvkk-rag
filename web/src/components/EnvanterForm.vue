<script setup>
// Envanter kayit formu: elle giris + asistan onerisi. Seceneklerin kaynagi seeder
// taksonomisi; listede yoksa kullanici "Diğer(...)" yazar.
import { computed, onMounted, reactive, ref } from 'vue';
import { envanter as envApi } from '../api';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import { useTaksonomiStore } from '../stores/taksonomi';
import BulguListesi from './BulguListesi.vue';
import SearchableSelect from './SearchableSelect.vue';

const props = defineProps({
  mevcut: { type: Object, default: null },      // duzenleme modunda satir
  onDoldur: { type: Object, default: null },    // sohbetten: {veri, birim, faaliyet}
});
const emit = defineEmits(['kapat', 'kaydedildi', 'silindi']);

const auth = useAuthStore();
const ui = useUiStore();
const tax = useTaksonomiStore();

const ALANLAR = [
  // birim/faaliyet kurumsal alanlar: kanonik taksonomi yok, Diğer() kalıbı geçerli değil
  { k: 'birim',               ad: 'Birim / Başkanlık', tip: 'liste-serbest', kaynak: ['envanterden', 'birim'], serbest: true },
  { k: 'faaliyet',            ad: 'Faaliyet',          tip: 'liste-serbest', kaynak: ['envanterden', 'faaliyet'], serbest: true },
  { k: 'kisisel_veri',        ad: 'Kişisel Veri',      tip: 'metin' },
  { k: 'veri_kategorisi',     ad: 'Veri Kategorisi',   tip: 'liste-serbest', kaynak: ['kanonik', 'veri_kategorisi'], ozelIsaret: true },
  { k: 'ozel_nitelikli_veri', ad: 'Özel Nitelikli Veri', tip: 'metin' },
  { k: 'kisi_grubu',          ad: 'İlgili Kişi Grubu', tip: 'liste-serbest', kaynak: ['envanterden', 'kisi_grubu'] },
  { k: 'isleme_amaci',        ad: 'İşleme Amacı',      tip: 'liste-serbest', kaynak: ['kanonik', 'isleme_amaci'] },
  { k: 'hukuki_sebep',        ad: 'Hukuki Sebep',      tip: 'liste-serbest', kaynak: ['kanonik', 'hukuki_sebep'] },
  { k: 'alici_grubu',         ad: 'Alıcı Grubu',       tip: 'liste-serbest', kaynak: ['kanonik', 'alici_grubu'] },
  { k: 'yurt_disi_aktarim',   ad: 'Yurt Dışı Aktarım', tip: 'secim', secenek: ['Hayır', 'Evet'] },
  { k: 'saklama_suresi',      ad: 'Saklama Süresi',    tip: 'metin' },
  { k: 'imha_yontemi',        ad: 'İmha Yöntemi',      tip: 'metin' },
  { k: 'teknik_tedbir',       ad: 'Teknik Tedbirler',  tip: 'coklu', kaynak: ['kanonik', 'teknik_tedbir'] },
  { k: 'idari_tedbir',        ad: 'İdari Tedbirler',   tip: 'coklu', kaynak: ['kanonik', 'idari_tedbir'] },
];
const SUTUNLAR = [ALANLAR.slice(0, 5), ALANLAR.slice(5, 10), ALANLAR.slice(10)];

const duzenle = computed(() => !!props.mevcut);
const form = reactive({});
ALANLAR.forEach((a) => {
  const v = props.mevcut?.[a.k] ?? '';
  form[a.k] = a.tip === 'coklu'
    ? String(v).split('\n').map((s) => s.replace(/^•\s*/, '').trim()).filter(Boolean)
    : (a.tip === 'secim' ? (v || a.secenek[0]) : v);
});

const oneriVeri = ref(props.onDoldur?.veri || '');
const oneri = ref(null);       // {gerekce, uyarilar, kaynaklar}
const oneriHata = ref('');
const oneriBekliyor = ref(false);
const durum = ref({ metin: '', renk: 'var(--t2)' });
const bulgular = ref(props.mevcut?.bulgular || []);
const bulgularGoster = ref(duzenle.value);
const kaydediyor = ref(false);

const secenekler = (a) => (a.kaynak ? tax.secenekler(a.kaynak[0], a.kaynak[1]) : a.secenek || []);
const ozelKategori = computed(() => tax.ozelKategoriler.has(String(form.veri_kategorisi || '').trim()));
const ipucu = (a) => (a.serbest ? 'Seçin veya yeni bir değer yazın' : 'Seçin veya yazın — listede yoksa Diğer(açıklama)');
// Hukuki sebepler madde grubuna gore listelenir: m.5 genel sartlar, m.6 ozel nitelikli, m.28 istisna.
// Ayni ad iki grupta olabilir ("Kanunlarda Açıkça Öngörülmesi"); ozel nitelikli kategoride m.6 basa alinir.
const MADDE = {
  5: { grup: 'KVKK m.5 · Kişisel veri işleme şartları', rozet: 'm.5', sinif: 'bg-sky-500/15 text-sky-300' },
  6: { grup: 'KVKK m.6 · Özel nitelikli kişisel veri işleme şartları', rozet: 'm.6 · özel nitelikli', sinif: 'bg-fuchsia-500/20 text-fuchsia-300' },
  28: { grup: 'KVKK m.28 · İstisna sebepler', rozet: 'm.28 · istisna', sinif: 'bg-amber-500/15 text-amber-300' },
};
const hukukiSecenekleri = computed(() => {
  const detay = tax.veri?.hukuki_sebep_detay || [];
  if (!detay.length) return tax.secenekler('kanonik', 'hukuki_sebep').map((x) => ({ value: x, label: x }));
  const sira = ozelKategori.value ? ['6', '5', '28'] : ['5', '6', '28'];
  return sira.flatMap((m) => detay.filter((d) => d.madde === m)
    .map((d) => ({ value: d.ad, label: d.ad, group: MADDE[m].grup, badge: MADDE[m].rozet, badgeClass: MADDE[m].sinif })));
});
// secili sebep m.6 sartlarindan mi (ozel nitelikli veri icin zorunlu; ENV-004)
const sebepM6 = computed(() => (tax.veri?.hukuki_sebep_detay || []).some((d) => d.madde === '6' && d.ad === String(form.hukuki_sebep || '').trim()));
// Aranabilir secim kutusu secenekleri: kanonik/envanter listesi (+ veri kategorisi icin Diğer kalibi)
const secimSecenekleri = (a) => {
  if (a.k === 'hukuki_sebep') return hukukiSecenekleri.value;
  const liste = secenekler(a).map((x) => ({ value: x, label: x }));
  if (a.k === 'veri_kategorisi') liste.push({ value: 'Diğer(açıklama)', label: 'Diğer(açıklama)', badge: 'listede yoksa' });
  return liste;
};
// ozel nitelikli kategoriler rozetle isaretlenir
const ozelRozet = computed(() => new Map([...tax.ozelKategoriler].map((k) => [k, 'özel nitelikli'])));

const silebilir = computed(() => duzenle.value && auth.can('inventory.delete'));
const oneriAlabilir = computed(() => auth.can('inventory.suggest'));

function setDurum(metin, renk = 'var(--t2)') { durum.value = { metin, renk }; }

function formOku() {
  const out = {};
  ALANLAR.forEach((a) => {
    out[a.k] = a.tip === 'coklu' ? form[a.k].join('\n') : String(form[a.k] ?? '').trim();
  });
  // Diğer(Biyometrik Veri) gibi kanonik bir kategori Diğer() kalıbına sokulmuşsa düzelt
  const m = out.veri_kategorisi.match(/^diğer\((.+)\)$/i);
  if (m) {
    const icerik = m[1].trim();
    const es = tax.secenekler('kanonik', 'veri_kategorisi').find((c) => c.toLowerCase() === icerik.toLowerCase());
    if (es) out.veri_kategorisi = es;
  }
  return out;
}

function oneriUygula(o) {
  const ata = (k, v) => { if (v) form[k] = v; };
  // Kullanici tek cumle yazmis olabilir; asistan birim/faaliyet/veriyi ayristirir
  ata('kisisel_veri', o.kisisel_veri); ata('birim', o.birim); ata('faaliyet', o.faaliyet);
  ['veri_kategorisi', 'kisi_grubu', 'isleme_amaci', 'hukuki_sebep', 'alici_grubu', 'saklama_suresi', 'imha_yontemi']
    .forEach((k) => ata(k, o[k]));
  if (o.ozel_nitelikli && o.veri_kategorisi) ata('ozel_nitelikli_veri', o.kisisel_veri);
  ['teknik_tedbir', 'idari_tedbir'].forEach((k) => {
    const sec = new Set(o[k] || []);
    const mevcutListe = tax.secenekler('kanonik', k);
    form[k] = Array.from(new Set([...form[k], ...mevcutListe.filter((x) => sec.has(x))]));
  });
}

async function oneriAl() {
  const veri = oneriVeri.value.trim() || String(form.kisisel_veri || '').trim();
  if (!veri) { ui.bildir('Önce eklenen kişisel veriyi yazın.', 'uyari'); return; }
  oneriBekliyor.value = true; oneriHata.value = ''; oneri.value = null;
  try {
    const o = await envApi.oneri({ veri, birim: form.birim, faaliyet: form.faaliyet });
    oneriUygula(o);
    oneri.value = {
      gerekce: o.gerekce || '', uyarilar: o.uyarilar || [],
      kaynak: (o.kaynaklar || []).map((k) => (k.madde_no ? `m.${k.madde_no}` : k.karar_no)).filter(Boolean).slice(0, 8),
    };
    setDurum('');
    ui.toast({ baslik: 'Öneri uygulandı', tur: 'bilgi', metin: 'Alanlar mevzuat dayanağıyla dolduruldu; kaydetmeden önce gözden geçirin.' });
  } catch (e) {
    oneriHata.value = 'Öneri alınamadı: ' + e.message;
    ui.bildir('Öneri alınamadı: ' + e.message, 'hata');
  } finally { oneriBekliyor.value = false; }
}

async function kaydet() {
  kaydediyor.value = true; setDurum('Kaydediliyor…');
  try {
    const veri = formOku();
    const d = duzenle.value ? await envApi.guncelle(props.mevcut.satir_no, veri) : await envApi.olustur(veri);
    bulgular.value = d.bulgular || []; bulgularGoster.value = true;
    const n = bulgular.value.length;
    setDurum('');
    ui.toast({
      baslik: duzenle.value ? 'Kayıt güncellendi' : 'Kayıt oluşturuldu', tur: n ? 'uyari' : 'ok',
      metin: n ? `${n} uyum bulgusu oluştu; formun altında listeleniyor.` : 'Uyum bulgusu yok.',
    });
    emit('kaydedildi', d);
  } catch (e) { setDurum(''); ui.bildir('Kaydedilemedi: ' + e.message, 'hata'); }
  finally { kaydediyor.value = false; }
}

async function sil() {
  const onay = await ui.onay({ baslik: `Satır #${props.mevcut.satir_no} silinsin mi?`, tur: 'hata', onayMetni: 'Evet, sil',
    metin: 'Envanter kaydı kalıcı olarak silinir; işlem satır geçmişine yazılır.' });
  if (!onay) return;
  try { await envApi.sil(props.mevcut.satir_no); ui.bildir(`Satır #${props.mevcut.satir_no} silindi.`); emit('silindi', props.mevcut.satir_no); emit('kapat'); }
  catch (e) { ui.bildir('Silinemedi: ' + e.message, 'hata'); }
}

onMounted(async () => {
  await tax.yukle();
  if (props.onDoldur && !duzenle.value) {
    if (props.onDoldur.veri) form.kisisel_veri = props.onDoldur.veri;
    if (props.onDoldur.birim) form.birim = props.onDoldur.birim;
    if (props.onDoldur.faaliyet) form.faaliyet = props.onDoldur.faaliyet;
    setDurum('Sohbetten geldi — öneri alınıyor…');
    if (oneriAlabilir.value) oneriAl();
  }
});
</script>

<template>
  <div class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start justify-center p-6 overflow-y-auto" @click.self="emit('kapat')">
    <div class="bg-[var(--bg-2)] border border-[var(--line)] rounded-2xl max-w-5xl w-full my-4 shadow-2xl">
      <div class="sticky top-0 z-10 bg-[var(--bg-1)] border-b border-[var(--line)] px-5 py-3 flex items-center justify-between rounded-t-2xl">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/25">
            <FaIcon :icon="duzenle ? 'pen-to-square' : 'plus'" class="h-4 w-4" />
          </div>
          <div>
            <h3 class="text-sm font-bold text-white">{{ duzenle ? `Kaydı Düzenle · Satır ${mevcut.satir_no}` : 'Yeni Envanter Kaydı' }}</h3>
            <p class="text-[11px] text-[var(--t2)]">{{ duzenle ? 'Kişisel veri işleme envanteri satırı' : 'Alanlar taksonomiden aranarak seçilir; listede yoksa yazılır' }}</p>
          </div>
        </div>
        <button class="w-8 h-8 rounded-lg bg-[var(--bg-2)] hover:bg-[var(--bg-3)] text-[var(--t2)] hover:text-white flex items-center justify-center border border-[var(--line)]" aria-label="Kapat" @click="emit('kapat')"><FaIcon icon="xmark" class="h-3.5 w-3.5" /></button>
      </div>

      <div v-if="oneriAlabilir" class="p-5 border-b border-[var(--line)] bg-[var(--bg-inset)]/40">
        <div class="flex items-center gap-2 mb-2">
          <span class="w-2 h-2 rounded-full bg-indigo-500"></span>
          <h4 class="text-xs font-bold text-white">Asistan Önerisi</h4>
          <span class="text-[10.5px] text-[var(--t2)]">veriyi ve faaliyeti yazıp öneri isteyin; alanlar mevzuat dayanağıyla doldurulur</span>
        </div>
        <div class="flex gap-2">
          <input v-model="oneriVeri" placeholder="Eklenen kişisel veri — örn: Çocuk sayısı"
            class="girdi flex-1 !bg-[var(--bg-2)]" @keydown.enter.prevent="oneriAl">
          <button :disabled="oneriBekliyor" class="px-4 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white whitespace-nowrap" @click="oneriAl">
            <FaIcon :icon="oneriBekliyor ? 'spinner' : 'wand-magic-sparkles'" class="h-3 w-3 mr-1.5" :class="oneriBekliyor ? 'animate-spin' : ''" />{{ oneriBekliyor ? 'Üretiliyor…' : 'Öneri Al' }}
          </button>
        </div>
        <div v-if="oneriBekliyor" class="mt-3 text-xs text-[var(--t2)]">Mevzuat kaynakları taranıyor ve öneri üretiliyor…</div>
        <div v-else-if="oneriHata" class="mt-3 text-xs text-rose-400">{{ oneriHata }}</div>
        <div v-else-if="oneri" class="mt-3 p-3 rounded-lg bg-[var(--bg-2)] border border-indigo-500/25 text-xs">
          <p class="text-[11px] text-slate-200 leading-snug mb-2">{{ oneri.gerekce }}</p>
          <p v-for="(u, i) in oneri.uyarilar" :key="i" class="text-[11px] text-amber-400 leading-snug mb-1">⚠ {{ u }}</p>
          <p class="text-[10.5px] text-[var(--t2)] mt-1">Dayanak: <span class="font-mono text-indigo-400">{{ oneri.kaynak.join(' · ') }}</span></p>
        </div>
      </div>

      <div class="p-5 grid grid-cols-1 lg:grid-cols-3 gap-x-5">
        <div v-for="(sutun, si) in SUTUNLAR" :key="si">
          <div v-for="a in sutun" :key="a.k" class="mb-3">
            <label class="text-[10px] uppercase tracking-wider text-[var(--t2)] block mb-1" :for="'form-' + a.k">{{ a.ad }}</label>

            <SearchableSelect v-if="a.tip === 'coklu'" v-model="form[a.k]" :options="secenekler(a)" multiple allow-custom
              placeholder="Arayıp seçin; birden fazla olabilir" custom-text="olarak ekle" :max-height="220" />

            <select v-else-if="a.tip === 'secim'" :id="'form-' + a.k" v-model="form[a.k]" class="girdi">
              <option v-for="x in a.secenek" :key="x">{{ x }}</option>
            </select>

            <template v-else-if="a.tip === 'liste-serbest'">
              <SearchableSelect v-model="form[a.k]" :options="secimSecenekleri(a)" allow-custom :placeholder="ipucu(a)"
                :highlight="a.ozelIsaret ? ozelRozet : null" :input-class="a.ozelIsaret && ozelKategori ? '!border-fuchsia-500/60' : ''" />
              <p v-if="a.ozelIsaret && ozelKategori" class="text-[10px] text-fuchsia-400 mt-1">
                Özel nitelikli kişisel veri — hukuki sebep KVKK m.6'dan seçilmeli.</p>
              <p v-if="a.k === 'hukuki_sebep' && ozelKategori && form.hukuki_sebep && !sebepM6" class="text-[10px] text-amber-400 mt-1">
                <FaIcon icon="triangle-exclamation" class="h-2.5 w-2.5 mr-0.5" />Seçilen sebep m.6 kapsamında değil; kaydedilirse ENV-004 (kritik) bulgusu oluşur.</p>
            </template>

            <input v-else :id="'form-' + a.k" v-model="form[a.k]" class="girdi">
          </div>
        </div>
      </div>

      <div v-if="bulgularGoster" class="px-5 pb-3">
        <h4 class="text-xs font-bold text-white mb-2">Uyum Bulguları</h4>
        <BulguListesi :bulgular="bulgular" />
      </div>

      <div class="sticky bottom-0 bg-[var(--bg-1)] border-t border-[var(--line)] px-5 py-3 flex items-center justify-between rounded-b-2xl">
        <span class="text-[11px]" :style="{ color: durum.renk }">{{ durum.metin }}</span>
        <div class="flex gap-2">
          <button v-if="silebilir" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-500/15 text-rose-400 border border-rose-500/30 hover:bg-rose-500/25" @click="sil"><FaIcon icon="trash" class="h-3 w-3 mr-1.5" />Sil</button>
          <button class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-[var(--bg-3)] border border-[var(--line)] text-[var(--t1)] hover:text-white" @click="emit('kapat')"><FaIcon icon="xmark" class="h-3 w-3 mr-1.5" />Vazgeç</button>
          <button :disabled="kaydediyor" class="px-5 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white shadow-lg shadow-indigo-600/30" @click="kaydet">
            <FaIcon :icon="kaydediyor ? 'spinner' : 'floppy-disk'" class="h-3 w-3 mr-1.5" :class="kaydediyor ? 'animate-spin' : ''" />{{ kaydediyor ? 'Kaydediliyor…' : duzenle ? 'Güncelle' : 'Kaydet' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
