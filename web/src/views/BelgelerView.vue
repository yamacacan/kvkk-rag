<script setup>
// Uyum belgeleri: kurum profili + envanterden docx/zip uretimi. Uretim arka planda
// (kuyruk) yapilir: istek 202 ile kuyruga alinir, belge hazir olunca bildirim gelir ve
// "Üretilen belgeler" tablosundan indirilir. Tablo, bekleyen is varken sik yoklanir.
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { belgeler as belgeApi, profil as profilApi } from '../api';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import { useBildirimStore } from '../stores/bildirim';
import { goreliZaman, kisalt, sayi, tarih } from '../utils/format';
import DataTable from '../components/DataTable.vue';
import Rozet from '../components/Rozet.vue';

const auth = useAuthStore();
const ui = useUiStore();
const router = useRouter();
const route = useRoute();
const bildirim = useBildirimStore();

const PROFIL_ALANLARI = [
  { k: 'kurum',            ad: 'Kurum / Veri Sorumlusu', zorunlu: true, ipucu: 'Örn: ÖRNEK TEKNOLOJİ A.Ş.' },
  { k: 'adres',            ad: 'Adres',                  ipucu: 'Başvuruların yapılacağı açık adres' },
  { k: 'web_adres',        ad: 'Web Adresi',             ipucu: 'www.ornek.com.tr' },
  { k: 'cagri_merkezi',    ad: 'Çağrı Merkezi',          ipucu: '0850 000 00 00' },
  { k: 'faaliyet',         ad: 'Belge Başlığı (Faaliyet)', ipucu: 'Aydınlatma metni başlığında geçer' },
  { k: 'veri_isleyen',     ad: 'Veri İşleyen',           grup: 'protokol', ipucu: 'Protokolün karşı tarafı' },
  { k: 'sozlesme_adi',     ad: 'Sözleşme Adı',           grup: 'protokol' },
  { k: 'sozlesme_tarihi',  ad: 'Sözleşme Tarihi',        grup: 'protokol', ipucu: 'GG.AA.YYYY' },
  { k: 'protokol_tarihi',  ad: 'Protokol Tarihi',        grup: 'protokol', ipucu: 'boş bırakılırsa bugün' },
];
const URETIM_ETIKET = {
  hukuki_sebepler: 'Hukuki sebepler (Bölüm 4)', kayit_ortamlari: 'Toplama ortamları (Bölüm 4)',
  saklama_ozeti: 'Saklama süreleri (Bölüm 11)', politika_kapsam: 'Amaç ve kapsam (Bölüm 2)',
  risk_analizi: 'Risk analizi (Bölüm 15)',
  ihlal_birimleri: 'Müdahale ekibi birimleri (Bölüm 3)', ihlal_veri_kategorileri: 'Etkilenebilecek veri kategorileri (Bölüm 4.4)',
  ihlal_senaryolari: 'Kuruma özgü ihlal senaryoları (Bölüm 2)', ihlal_risk_degerlendirmesi: 'İhlal risk değerlendirmesi (Bölüm 4.3)',
};

// Kurum profili Yonetim > Kurum Profili'nde duzenlenir; burada salt okunur kullanilir
const profil = reactive(Object.fromEntries(PROFIL_ALANLARI.map((a) => [a.k, ''])));
const profilGuncelleme = ref('');
const sablonlar = ref([]);
const faaliyetBazli = ref([]);
const faaliyetler = ref([]);
const faaliyetSecimi = reactive({});
const onizlemeler = ref({});
const hata = ref('');
const uretiliyor = reactive({});
// kapsam tum belgeler icin ortak; faaliyet secimi yalnizca kendi sablonunu daraltir
const kapsam = reactive({ birim: null, faaliyet_filtresi: null });

const profilDuzenlenebilir = computed(() => auth.can('profile.update'));
const uretebilir = computed(() => auth.can('documents.generate'));
const profilDolu = computed(() => PROFIL_ALANLARI.filter((a) => profil[a.k]));
const kapsamMetni = computed(() => (kapsam.birim ? `kapsam: ${kapsam.birim}` : 'kapsam: tüm envanter'));

function govde() { const out = {}; PROFIL_ALANLARI.forEach((a) => { out[a.k] = String(profil[a.k] || '').trim(); }); return { ...out, ...kapsam }; }

let sayac = 0;
async function onizlemeleriYukle() {
  // Es zamanli cagrilar birbirini ezmesin: yalnizca en son istek yazar
  const benim = ++sayac;
  const p = govde();
  if (!p.kurum) { onizlemeler.value = {}; return; }
  const sonuc = await Promise.all(sablonlar.value.filter((s) => s.mevcut).map((s) =>
    belgeApi.onizleme({ ...p, sablon: s.anahtar }).then((r) => [s.anahtar, r]).catch(() => [s.anahtar, null])));
  if (benim !== sayac) return;
  onizlemeler.value = Object.fromEntries(sonuc);
}
function eksikAlanlar(s) {
  const o = onizlemeler.value[s.anahtar];
  const faalBazli = faaliyetBazli.value.includes(s.anahtar);
  // Faaliyet bazli belgede baslik asagidaki listeden gelir, eksik sayilmaz
  return (o?.eksik_alanlar || []).filter((a) => !(faalBazli && a.toLocaleLowerCase('tr') === 'faaliyet'));
}
function durum(s) {
  const o = onizlemeler.value[s.anahtar];
  if (!s.mevcut) return { metin: 'ŞABLON YOK', sinif: 'bg-rose-500/15 text-rose-400 border-rose-500/30' };
  if (!o) return { metin: 'KURUM ADI BEKLENİYOR', sinif: 'bg-[var(--bg-3)] text-[var(--t2)] border-[var(--line)]' };
  const eksik = eksikAlanlar(s);
  return eksik.length
    ? { metin: `${eksik.length} ALAN EKSİK`, sinif: 'bg-amber-500/15 text-amber-400 border-amber-500/30' }
    : { metin: 'HAZIR', sinif: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' };
}
const hazir = (s) => s.mevcut && onizlemeler.value[s.anahtar] && eksikAlanlar(s).length === 0;
const uretilenler = (s) => onizlemeler.value[s.anahtar]?.uretilen_bolumler || [];
const butonEtiketi = (s) => {
  if (!faaliyetBazli.value.includes(s.anahtar)) return 'Üret (.docx)';
  return faaliyetSecimi[s.anahtar] ? 'Üret (.docx)' : `Tümünü üret (.zip · ${faaliyetler.value.length})`;
};

async function uret(s) {
  const veri = govde();
  if (!veri.kurum) { ui.bildir('Kurum adı zorunludur; Yönetim › Kurum Profili', 'uyari'); return; }
  const secim = faaliyetSecimi[s.anahtar];
  const faalBazli = faaliyetBazli.value.includes(s.anahtar);
  const zip = faalBazli && !secim; // faaliyet secilmemisse tum faaliyetler tek zip
  const b = { ...veri, sablon: s.anahtar };
  if (faalBazli) { b.faaliyet = secim || veri.faaliyet; b.faaliyet_filtresi = secim || null; }
  uretiliyor[s.anahtar] = 'Kuyruğa alınıyor…';
  try {
    const d = zip ? await belgeApi.uretHepsi(b) : await belgeApi.uret(b);
    ui.toast({ baslik: 'Kuyruğa alındı', tur: 'bilgi', metin: `${s.ad} arka planda üretiliyor; hazır olunca bildirim alacaksınız.` });
    uretilenBelgeler.value = [d.belge, ...uretilenBelgeler.value];
    bekleyen.value += 1;
    yoklamaAyarla();
  } catch (e) { ui.hata('Belge kuyruğa alınamadı', e.message); }
  finally { delete uretiliyor[s.anahtar]; }
}

// ---- uretilen belgeler (kuyruk ciktisi) ----
const uretilenBelgeler = ref([]);
const bekleyen = ref(0);
const uretilenYukleniyor = ref(false);
const indiriliyor = reactive({});
const vurguluBelge = ref(Number(route.query.belge) || null);
let yoklayici = null;
const DURUM = {
  kuyrukta: { ad: 'Kuyrukta', tur: 'notr', ikon: 'hourglass-half' },
  uretiliyor: { ad: 'Üretiliyor', tur: 'bilgi', ikon: 'spinner' },
  hazir: { ad: 'Hazır', tur: 'ok', ikon: 'check' },
  hata: { ad: 'Hata', tur: 'kritik', ikon: 'circle-xmark' },
};
const URETILEN_SUTUNLAR = [
  { key: 'sablon_adi', label: 'Belge' },
  { key: 'kapsam', label: 'Kapsam' },
  { key: 'durum', label: 'Durum', width: 'w-32' },
  { key: 'created_at', label: 'İstek', width: 'w-28' },
  { key: 'boyut', label: 'Boyut', width: 'w-20', align: 'right' },
  { key: 'islem', label: '', width: 'w-40', align: 'right' },
];
const kapsamOzeti = (b) => {
  const i = b.istek || {};
  const p = [];
  if (b.tur === 'zip') p.push('tüm faaliyetler');
  else if (i.faaliyet_filtresi) p.push(i.faaliyet_filtresi);
  if (i.birim) p.push(i.birim);
  return p.join(' · ') || 'tüm envanter';
};
const boyutMetni = (n) => (!n ? '—' : n < 1024 * 1024 ? `${Math.round(n / 1024)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);

async function uretilenleriYukle(sessiz = false) {
  if (!sessiz) uretilenYukleniyor.value = true;
  const onceBekleyen = bekleyen.value;
  try {
    const d = await belgeApi.uretilenler(30);
    uretilenBelgeler.value = d.belgeler; bekleyen.value = d.bekleyen;
  } catch {} finally { uretilenYukleniyor.value = false; }
  // bir is bittiyse bildirimi beklemeden zili tazele (toast + sayac)
  if (bekleyen.value < onceBekleyen) bildirim.yukle({ sessiz: true });
  yoklamaAyarla();
}
function yoklamaAyarla() {
  // bekleyen is varken 4 sn'de bir tazele; bitince dur (bildirim de ayrica tetikler)
  clearInterval(yoklayici); yoklayici = null;
  bildirim.hizliYokla(bekleyen.value > 0);
  if (bekleyen.value > 0) yoklayici = setInterval(() => uretilenleriYukle(true), 4000);
}
async function indir(b) {
  indiriliyor[b.id] = true;
  try { await belgeApi.indir(b.id, b.ad); }
  catch (e) { ui.hata('İndirilemedi', e.message); }
  finally { delete indiriliyor[b.id]; }
}
async function uretilenSil(b) {
  const ok = await ui.onay({ baslik: 'Belge silinsin mi?', metin: `${b.sablon_adi || b.sablon} (#${b.id}) ve dosyası silinecek.`, tur: 'uyari', onayMetni: 'Sil', tehlikeli: true });
  if (!ok) return;
  try { await belgeApi.uretilenSil(b.id); uretilenBelgeler.value = uretilenBelgeler.value.filter((x) => x.id !== b.id); ui.bildir('Belge silindi.'); }
  catch (e) { ui.hata('Silinemedi', e.message); }
}
// Belge bildirimi gelince listeyi tazele
const dinlemeyiBirak = bildirim.dinle((yeniler) => { if (yeniler.some((b) => b.type?.startsWith('documents.'))) uretilenleriYukle(true); });
watch(() => route.query.belge, (v) => { vurguluBelge.value = Number(v) || null; });
onBeforeUnmount(() => { clearInterval(yoklayici); bildirim.hizliYokla(false); dinlemeyiBirak(); });

onMounted(async () => {
  uretilenleriYukle();
  try {
    const d = await profilApi.getir();
    PROFIL_ALANLARI.forEach((a) => { profil[a.k] = d[a.k] || ''; });
    profilGuncelleme.value = d.guncelleme || '';
  } catch {}
  try {
    const d = await belgeApi.liste();
    // Faaliyet bazli sablonlar (aydinlatma, acik riza) Faaliyet Belgeleri sayfasinda otomatik uretilir
    faaliyetBazli.value = d.faaliyet_bazli || [];
    sablonlar.value = d.sablonlar.filter((s) => !faaliyetBazli.value.includes(s.anahtar));
    faaliyetler.value = (await belgeApi.faaliyetler(kapsam.birim)).faaliyetler || [];
    await onizlemeleriYukle();
  } catch (e) { hata.value = e.message; }
});
</script>

<template>
  <section>
    <h1 class="text-2xl font-extrabold text-white tracking-tight sm:text-3xl mb-1">Kurumsal Belgeler</h1>
    <p class="text-xs text-[var(--t1)] mb-5">Kurum geneli politika, prosedür ve formlar; kurum profili ve envanterden üretilir, arka planda hazırlanınca bildirim gelir.
      Faaliyet bazlı Aydınlatma Metni ve Açık Rıza Beyanı <router-link :to="{ name: 'faaliyet-belgeleri' }" class="text-indigo-400 hover:underline">Faaliyet Belgeleri</router-link> sayfasında envanterden otomatik üretilir.</p>

    <div class="rounded-2xl border border-[var(--line)] bg-[var(--bg-2)] p-5 mb-5">
      <div class="flex items-center gap-2 mb-3">
        <span class="w-2 h-2 rounded-full bg-indigo-500"></span>
        <h3 class="text-sm font-bold text-white">Kurum Profili</h3>
        <span class="text-[10.5px] text-[var(--t2)]">belgelerdeki kurum alanları buradan dolar<span v-if="profilGuncelleme"> · son kayıt {{ tarih(profilGuncelleme) }}</span></span>
        <button v-if="profilDuzenlenebilir" class="ml-auto px-3 py-1 rounded-lg bg-[var(--bg-3)] border border-[var(--line)] text-[var(--t1)] hover:text-white text-[11px] font-semibold" @click="router.push({ name: 'kurum-profili' })">Yönetim › Kurum Profili →</button>
      </div>
      <div v-if="!profil.kurum" class="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-300">
        Kurum adı tanımlı değil; belge üretilemez. <span v-if="profilDuzenlenebilir">Yönetim › Kurum Profili'nden doldurun.</span><span v-else>Yöneticinizden kurum profilini doldurmasını isteyin.</span>
      </div>
      <div v-else class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div v-for="a in profilDolu" :key="a.k">
          <p class="text-[10px] uppercase tracking-wider text-[var(--t2)]">{{ a.ad }}</p>
          <p class="text-xs text-white truncate" :title="profil[a.k]">{{ profil[a.k] }}</p>
        </div>
      </div>
    </div>

    <div class="rounded-2xl border border-[var(--line)] bg-[var(--bg-2)] overflow-hidden">
      <div class="px-5 py-3 border-b border-[var(--line)] bg-[var(--bg-1)]/70 flex items-center gap-2">
        <h3 class="text-sm font-bold text-white">Üretilebilir Belgeler</h3>
        <span class="text-[10.5px] text-[var(--t2)]">{{ kapsamMetni }}</span>
      </div>
      <div class="divide-y divide-[var(--line)]">
        <div v-if="hata" class="px-5 py-8 text-center text-xs text-rose-400">Yüklenemedi: {{ hata }}</div>
        <div v-else-if="!sablonlar.length" class="px-5 py-8 text-center text-xs text-[var(--t2)]">Yükleniyor…</div>
        <div v-for="s in sablonlar" :key="s.anahtar" class="px-5 py-4 hover:bg-[var(--bg-3)]/30">
          <div class="flex items-start justify-between gap-4">
            <div class="min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <h4 class="text-sm font-bold text-white">{{ s.ad }}</h4>
                <span class="text-[11px] font-bold px-2 py-0.5 rounded border" :class="durum(s).sinif">{{ durum(s).metin }}</span>
              </div>
              <p class="text-[11px] text-[var(--t2)] font-mono mb-1">{{ s.dosya }}</p>
              <p class="text-[11px] text-[var(--t1)]">Doldurulacak alanlar:
                <span class="text-slate-300">{{ (s.alanlar || []).join(', ') || '—' }}</span></p>
              <p v-if="eksikAlanlar(s).length" class="text-[11px] text-amber-400 mt-1">Eksik: {{ eksikAlanlar(s).join(', ') }} — bu alanlar boş kalacak.</p>
              <p v-if="uretilenler(s).length" class="text-[11px] text-[var(--t2)] mt-1.5">Otomatik yazılan bölümler:
                <span v-for="b in uretilenler(s)" :key="b.alan" class="inline-block mr-1 mt-1 px-1.5 py-0.5 rounded text-[10px] border"
                  :class="b.kaynak === 'yapay_zeka' ? 'bg-violet-500/10 text-violet-300 border-violet-500/30' : 'bg-sky-500/10 text-sky-300 border-sky-500/30'"
                  :title="b.kaynak === 'yapay_zeka' ? 'Yapay zeka ile yazılır — imzalamadan önce gözden geçirin' : 'Veri envanterinden doldurulur'">
                  {{ b.kaynak === 'yapay_zeka' ? '✨' : '🗄' }} {{ URETIM_ETIKET[b.alan] || b.alan }}</span>
              </p>
              <div v-if="faaliyetBazli.includes(s.anahtar)" class="mt-2 flex items-center gap-2">
                <select v-model="faaliyetSecimi[s.anahtar]" class="girdi flex-1 min-w-0 !py-1 !px-2 text-[11px]">
                  <option value="">Tüm faaliyetler ({{ faaliyetler.length }}) — ZIP</option>
                  <option v-for="f in faaliyetler" :key="f.ad" :value="f.ad">{{ f.ad }} · {{ f.satir }} kayıt</option>
                </select>
              </div>
            </div>
            <button v-if="uretebilir" :disabled="!s.mevcut || !!uretiliyor[s.anahtar]" @click="uret(s)"
              class="shrink-0 px-4 py-1.5 text-xs font-bold rounded-lg disabled:opacity-50 flex items-center gap-1.5"
              :class="hazir(s) ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30' : 'bg-[var(--bg-3)] border border-[var(--line)] text-[var(--t1)] hover:text-white'">
              <FaIcon :icon="uretiliyor[s.anahtar] ? 'spinner' : 'gears'" class="h-3 w-3" :class="uretiliyor[s.anahtar] ? 'animate-spin' : ''" />{{ uretiliyor[s.anahtar] || butonEtiketi(s) }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- uretilen belgeler: kuyruk ciktilari -->
    <div class="rounded-2xl border border-[var(--line)] bg-[var(--bg-2)] overflow-hidden mt-5">
      <div class="px-5 py-3 border-b border-[var(--line)] bg-[var(--bg-1)]/70 flex items-center gap-2">
        <FaIcon icon="inbox" class="h-3.5 w-3.5 text-indigo-400" />
        <h3 class="text-sm font-bold text-white">Üretilen Belgeler</h3>
        <Rozet v-if="bekleyen" tur="bilgi" boyut="xs" nokta nabiz>{{ bekleyen }} işlem sürüyor</Rozet>
        <span class="text-[10.5px] text-[var(--t2)] hidden sm:inline">arka planda üretilir; hazır olanları buradan indirin</span>
        <button class="ml-auto flex items-center gap-1 text-[11px] text-[var(--t1)] hover:text-white" @click="uretilenleriYukle()"><FaIcon icon="rotate" class="h-3 w-3" :class="uretilenYukleniyor ? 'animate-spin' : ''" />Yenile</button>
      </div>
      <DataTable :columns="URETILEN_SUTUNLAR" :rows="uretilenBelgeler" row-key="id" :loading="uretilenYukleniyor" dense :show-count="false"
        empty-text="Henüz belge üretilmedi. Yukarıdan bir şablon seçip üretin."
        :row-class="(r) => r.id === vurguluBelge ? 'bg-indigo-500/10' : ''">
        <template #cell-sablon_adi="{ row }">
          <span class="flex items-center gap-2 min-w-0">
            <FaIcon :icon="row.tur === 'zip' ? 'file-zipper' : 'file-word'" class="h-3.5 w-3.5 shrink-0" :class="row.tur === 'zip' ? 'text-amber-400' : 'text-sky-400'" />
            <span class="min-w-0">
              <span class="block text-xs font-semibold text-white truncate">{{ row.sablon_adi || row.sablon }} <span class="font-mono text-[10px] text-[var(--t2)]">#{{ row.id }}</span></span>
              <span v-if="row.durum === 'hata'" class="block text-[10.5px] text-rose-400 truncate" :title="row.hata">{{ kisalt(row.hata, 90) }}</span>
              <span v-else-if="row.durum === 'hazir' && (row.kalan?.length || row.yapay_zeka?.length || row.hatalar?.length)" class="block text-[10.5px] text-[var(--t2)] truncate">
                <span v-if="row.kalan?.length" class="text-amber-400">{{ row.kalan.length }} alan boş</span>
                <span v-if="row.yapay_zeka?.length"> · ✨ {{ row.yapay_zeka.length }} bölüm yapay zeka</span>
                <span v-if="row.hatalar?.length" class="text-amber-400"> · {{ row.hatalar.length }} faaliyet atlandı</span>
              </span>
            </span>
          </span>
        </template>
        <template #cell-kapsam="{ row }"><span class="text-[11px] text-[var(--t1)]">{{ kapsamOzeti(row) }}<span v-if="row.satir != null" class="text-[var(--t2)] font-mono"> · {{ sayi(row.satir) }} satır</span></span></template>
        <template #cell-durum="{ value }">
          <Rozet :tur="DURUM[value]?.tur || 'notr'" boyut="xs" sekil="rounded" :nokta="value === 'kuyrukta'" :nabiz="value === 'kuyrukta'">
            <FaIcon :icon="DURUM[value]?.ikon || 'circle-info'" class="h-2.5 w-2.5" :class="value === 'uretiliyor' ? 'animate-spin' : ''" />{{ DURUM[value]?.ad || value }}
          </Rozet>
        </template>
        <template #cell-created_at="{ value }"><span class="font-mono text-[10.5px] text-[var(--t2)]" :title="tarih(value)">{{ goreliZaman(value) }}</span></template>
        <template #cell-boyut="{ value }"><span class="font-mono text-[10.5px] text-[var(--t2)]">{{ boyutMetni(value) }}</span></template>
        <template #cell-islem="{ row }">
          <span class="flex items-center justify-end gap-1.5">
            <button v-if="row.durum === 'hazir' && uretebilir" class="flex items-center gap-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 px-2.5 py-1 text-[11px] font-semibold text-white disabled:opacity-50" :disabled="!!indiriliyor[row.id]" @click="indir(row)">
              <FaIcon :icon="indiriliyor[row.id] ? 'spinner' : 'download'" class="h-3 w-3" :class="indiriliyor[row.id] ? 'animate-spin' : ''" />İndir</button>
            <button v-if="row.durum === 'hazir' || row.durum === 'hata'" class="flex h-7 w-7 items-center justify-center rounded-lg border border-[var(--line)] text-[var(--t2)] hover:text-rose-400 hover:border-rose-500/40" title="Sil" @click="uretilenSil(row)"><FaIcon icon="trash" class="h-3 w-3" /></button>
          </span>
        </template>
      </DataTable>
    </div>
  </section>
</template>
