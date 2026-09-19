<script setup>
// Kurum profili (veri sorumlusu bilgileri): bir kez kaydedilir, tum uyum belgelerinde kullanilir.
// Uyum Belgeleri ekranindan buraya tasindi; belgeler sayfasi bu profili okur.
import { onMounted, reactive, ref } from 'vue';
import { profil as profilApi } from '../../api';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { tarih } from '../../utils/format';

const auth = useAuthStore();
const ui = useUiStore();

const PROFIL_ALANLARI = [
  { k: 'kurum', ad: 'Kurum / Veri Sorumlusu', zorunlu: true, ipucu: 'Örn: ÖRNEK TEKNOLOJİ A.Ş.', grup: 'kurum' },
  { k: 'adres', ad: 'Adres', ipucu: 'Başvuruların yapılacağı açık adres', grup: 'kurum' },
  { k: 'web_adres', ad: 'Web Adresi', ipucu: 'https://www.ornek.com.tr — Genel Aydınlatma Metni QR kodu bu adrese gider', grup: 'kurum' },
  { k: 'cagri_merkezi', ad: 'Çağrı Merkezi', ipucu: '0850 000 00 00', grup: 'kurum' },
  { k: 'faaliyet', ad: 'Belge Başlığı (Faaliyet)', ipucu: 'Aydınlatma metni başlığında geçer', grup: 'kurum' },
  { k: 'veri_isleyen', ad: 'Veri İşleyen', ipucu: 'Protokolün karşı tarafı', grup: 'protokol' },
  { k: 'sozlesme_adi', ad: 'Sözleşme Adı', grup: 'protokol' },
  { k: 'sozlesme_tarihi', ad: 'Sözleşme Tarihi', ipucu: 'GG.AA.YYYY', grup: 'protokol' },
  { k: 'protokol_tarihi', ad: 'Protokol Tarihi', ipucu: 'boş bırakılırsa bugün', grup: 'protokol' },
];

const profil = reactive(Object.fromEntries(PROFIL_ALANLARI.map((a) => [a.k, ''])));
const guncelleme = ref('');
const kaydediyor = ref(false);
const hata = ref('');
const kirli = ref(false);

async function yukle() {
  try {
    const d = await profilApi.getir();
    PROFIL_ALANLARI.forEach((a) => { profil[a.k] = d[a.k] || ''; });
    guncelleme.value = d.guncelleme || '';
    kirli.value = false;
  } catch (e) { hata.value = e.message; }
}
async function kaydet() {
  hata.value = '';
  if (!profil.kurum.trim()) { hata.value = 'Kurum adı zorunludur.'; return; }
  kaydediyor.value = true;
  try {
    const d = await profilApi.kaydet({ ...profil });
    guncelleme.value = d.guncelleme; kirli.value = false;
    ui.bildir('Kurum profili kaydedildi.');
  } catch (e) { hata.value = e.message; }
  finally { kaydediyor.value = false; }
}
onMounted(yukle);
</script>

<template>
  <section class="space-y-5 max-w-5xl mx-auto">
    <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
      <div>
        <h1 class="text-2xl font-extrabold text-t-1 tracking-tight">Kurum Profili</h1>
        <p class="text-xs text-t-2 mt-1">Veri sorumlusu bilgileri; aydınlatma metni, politika ve protokol şablonlarındaki alanlar buradan doldurulur.<span v-if="guncelleme" class="text-t-3"> Son kayıt: {{ tarih(guncelleme) }}</span></p>
      </div>
      <button v-if="auth.can('profile.update')" :disabled="kaydediyor || !kirli" class="rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/20" @click="kaydet"><FaIcon :icon="kaydediyor ? 'spinner' : 'floppy-disk'" class="h-3 w-3 mr-1.5" :class="kaydediyor ? 'animate-spin' : ''" />{{ kaydediyor ? 'Kaydediliyor…' : 'Profili Kaydet' }}</button>
    </div>

    <form @submit.prevent="kaydet" @input="kirli = true" novalidate class="space-y-5">
      <div v-for="grup in [['kurum', 'Veri Sorumlusu', 'Tüm belgelerde kullanılır'], ['protokol', 'Veri İşleyen Protokolü', 'Yalnızca protokol şablonunda kullanılır']]" :key="grup[0]" class="rounded-xl border border-line bg-bg-card p-5">
        <div class="flex items-center gap-2 mb-3">
          <span class="w-2 h-2 rounded-full" :class="grup[0] === 'kurum' ? 'bg-indigo-500' : 'bg-emerald-500'"></span>
          <h3 class="text-sm font-bold text-t-1">{{ grup[1] }}</h3><span class="text-[10.5px] text-t-3">{{ grup[2] }}</span>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div v-for="a in PROFIL_ALANLARI.filter((x) => x.grup === grup[0])" :key="a.k">
            <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1" :for="'kp-' + a.k">{{ a.ad }}<span v-if="a.zorunlu" class="text-rose-400"> *</span></label>
            <input :id="'kp-' + a.k" v-model="profil[a.k]" :placeholder="a.ipucu || ''" :disabled="!auth.can('profile.update')" class="girdi disabled:opacity-60">
          </div>
        </div>
      </div>
      <p v-if="hata" class="text-[11px] text-rose-400">{{ hata }}</p>
    </form>
  </section>
</template>
