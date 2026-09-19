<script setup>
// Panel: animasyonlu KPI kartlari, (yonetici) sistem seridi, 6 kural radari + kategori
// cubuklari + seviye dagilimi, ve uc esit liste (riskli faaliyet / son hareket / gunluk).
// Satirlar her kartta 12 kolonluk gride oturur; kartlar satir icinde esit yuksekliktedir.
// Veri tek istekten (/api/dashboard); yalnizca izinli bloklar gelir.
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { panel as panelApi } from '../api';
import { useAuthStore } from '../stores/auth';
import { goreliZaman, kisalt, sayi, seviye } from '../utils/format';
import Iskelet from '../components/Iskelet.vue';
import KpiKarti from '../components/KpiKarti.vue';
import RadarGrafik from '../components/RadarGrafik.vue';
import CubukGrafik from '../components/CubukGrafik.vue';
import Rozet from '../components/Rozet.vue';

const auth = useAuthStore();
const router = useRouter();
const veri = ref(null);
const hata = ref('');
const yukleniyor = ref(true);
const yenileniyor = ref(false);
const SATIR = 6; // liste kartlarinda gosterilen satir sayisi (esit yukseklik icin sabit)

const env = computed(() => veri.value?.envanter || null);
const uyum = computed(() => (env.value ? Math.round(env.value.uyum_orani * 1000) / 10 : 0));
const seviyeler = computed(() => {
  const s = env.value?.seviye || {};
  const toplam = Object.values(s).reduce((a, b) => a + b, 0) || 1;
  return ['kritik', 'yuksek', 'orta', 'dusuk'].map((k) => ({ k, adet: s[k] || 0, yuzde: Math.round(((s[k] || 0) / toplam) * 100) }));
});
// 6 denetim kurali -> altigen radar eksenleri
const KURAL = {
  'ENV-001': 'Saklama süresi yok', 'ENV-002': 'İmha yöntemi yok', 'ENV-003': 'Tedbir eksik',
  'ENV-004': 'Özel nitelikli / sebep', 'ENV-005': 'Yurt dışı dayanaksız', 'ENV-006': 'Açık rıza tek dayanak',
};
const radar = computed(() => Object.keys(KURAL).map((kod) => ({ etiket: kod, kisa: kod.replace('ENV-', 'E'), deger: env.value?.kod?.[kod] || 0, ipucu: KURAL[kod] })));
const kategoriler = computed(() => (env.value?.veri_kategorisi || []).map((x) => ({ etiket: x.deger, deger: x.adet })));
const riskli = computed(() => (veri.value?.riskli_faaliyetler || []).slice(0, SATIR));
const hareketler = computed(() => (veri.value?.son_hareketler || []).slice(0, SATIR));
const gunluk = computed(() => (veri.value?.denetim_gunlugu || []).slice(0, SATIR));

const ISLEM = { olustur: { ad: 'oluşturuldu', ikon: 'plus', sinif: 'text-emerald-400 bg-emerald-500/10' }, guncelle: { ad: 'güncellendi', ikon: 'pen-to-square', sinif: 'text-amber-400 bg-amber-500/10' }, sil: { ad: 'silindi', ikon: 'trash', sinif: 'text-rose-400 bg-rose-500/10' } };
const islem = (k) => ISLEM[k] || { ad: k, ikon: 'circle-info', sinif: 'text-t-3 bg-bg-3' };
const EYLEM = {
  'auth.login': ['giriş yaptı', 'right-from-bracket', 'text-emerald-400 bg-emerald-500/10'], 'auth.login_failed': ['başarısız giriş', 'circle-xmark', 'text-rose-400 bg-rose-500/10'], 'auth.logout': ['çıkış yaptı', 'right-from-bracket', 'text-t-3 bg-bg-3'],
  'auth.profile_update': ['profilini güncelledi', 'id-badge', 'text-sky-400 bg-sky-500/10'], 'auth.password_change': ['şifresini değiştirdi', 'key', 'text-amber-400 bg-amber-500/10'], 'auth.password_reset': ['şifresini sıfırladı', 'key', 'text-amber-400 bg-amber-500/10'],
  'users.create': ['kullanıcı oluşturdu', 'users', 'text-indigo-400 bg-indigo-500/10'], 'users.update': ['kullanıcı güncelledi', 'users', 'text-indigo-400 bg-indigo-500/10'], 'users.delete': ['kullanıcı sildi', 'users', 'text-rose-400 bg-rose-500/10'],
  'roles.create': ['rol oluşturdu', 'user-shield', 'text-fuchsia-400 bg-fuchsia-500/10'], 'roles.update': ['rol güncelledi', 'user-shield', 'text-fuchsia-400 bg-fuchsia-500/10'], 'roles.delete': ['rol sildi', 'user-shield', 'text-rose-400 bg-rose-500/10'], 'roles.clone': ['rol klonladı', 'user-shield', 'text-fuchsia-400 bg-fuchsia-500/10'],
  'departments.create': ['birim oluşturdu', 'sitemap', 'text-sky-400 bg-sky-500/10'], 'departments.update': ['birim güncelledi', 'sitemap', 'text-sky-400 bg-sky-500/10'], 'departments.delete': ['birim sildi', 'sitemap', 'text-rose-400 bg-rose-500/10'],
  'profile.update': ['kurum profilini güncelledi', 'building-user', 'text-teal-400 bg-teal-500/10'],
};
const eylem = (k) => EYLEM[k] || [k, 'circle-info', 'text-t-3 bg-bg-3'];
const YONETIM = [
  ['users', 'Kullanıcı', 'kullanici', 'kullanicilar', 'text-violet-400 bg-violet-500/10'],
  ['user-shield', 'Rol', 'rol', 'roller', 'text-fuchsia-400 bg-fuchsia-500/10'],
  ['sitemap', 'Birim', 'departman', 'birimler', 'text-sky-400 bg-sky-500/10'],
  ['key', 'Aktif oturum', 'aktif_oturum', 'profil', 'text-emerald-400 bg-emerald-500/10'],
  ['gears', 'Kuyruk', 'kuyruk', 'gunluk', 'text-amber-400 bg-amber-500/10'],
];
const kuyrukDeger = (k) => (k ? (k.queued || 0) + (k.running || 0) : 0);
const selam = computed(() => { const s = new Date().getHours(); return s < 12 ? 'Günaydın' : s < 18 ? 'İyi günler' : 'İyi akşamlar'; });
const bugun = new Date().toLocaleDateString('tr-TR', { weekday: 'long', day: 'numeric', month: 'long' });

async function yukle(sessiz = false) {
  if (sessiz) yenileniyor.value = true; else yukleniyor.value = true;
  try { veri.value = await panelApi.getir(); hata.value = ''; } catch (e) { hata.value = e.message; }
  finally { yukleniyor.value = false; yenileniyor.value = false; }
}
onMounted(() => yukle());
</script>

<template>
  <section class="space-y-5 max-w-[1780px] mx-auto">
    <!-- baslik -->
    <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
      <div>
        <p class="text-xs text-t-3 mb-1 flex items-center gap-2"><FaIcon icon="clock" class="h-3 w-3" />{{ bugun }}</p>
        <h1 class="text-2xl font-extrabold text-t-1 tracking-tight sm:text-3xl">{{ selam }}, {{ (auth.user?.name || '').split(' ')[0] }}</h1>
        <div class="mt-2 flex flex-wrap items-center gap-2">
          <Rozet v-if="veri?.kapsam?.envanter && veri.kapsam.envanter !== 'all'" tur="uyari" mono nokta>kapsam: {{ veri.kapsam.envanter }}</Rozet>
          <Rozet v-if="env" tur="ok" ikon="check-double">{{ sayi(env.temiz_satir) }} bulgusuz kayıt</Rozet>
          <Rozet v-if="env && env.seviye.kritik" tur="kritik" nokta nabiz>{{ sayi(env.seviye.kritik) }} kritik bulgu</Rozet>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button class="flex items-center gap-1.5 rounded-lg border border-line bg-bg-2 px-3 py-1.5 text-xs font-medium text-t-2 hover:text-t-1 hover:bg-bg-3 disabled:opacity-60" :disabled="yenileniyor" @click="yukle(true)">
          <FaIcon icon="rotate" class="h-3 w-3" :class="yenileniyor ? 'animate-spin' : ''" />Yenile</button>
        <button v-if="auth.can('inventory.create')" class="flex items-center gap-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/20" @click="router.push({ name: 'envanter' })"><FaIcon icon="plus" class="h-3 w-3" />Envanter kaydı</button>
        <button v-if="auth.can('chat.use')" class="flex items-center gap-1.5 rounded-lg border border-line bg-bg-2 px-3.5 py-1.5 text-xs font-medium text-t-2 hover:text-t-1 hover:bg-bg-3" @click="router.push({ name: 'asistan' })"><FaIcon icon="comments" class="h-3 w-3" />Asistana sor</button>
      </div>
    </div>

    <div v-if="hata" class="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2"><FaIcon icon="circle-xmark" class="h-4 w-4" />Panel yüklenemedi: {{ hata }}</div>

    <template v-else-if="yukleniyor">
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4" aria-busy="true">
        <div v-for="i in 4" :key="i" class="rounded-xl border border-line bg-bg-card p-4">
          <div class="flex items-center gap-2.5 mb-3"><Iskelet class="h-9 w-9" /><Iskelet class="h-3 w-24" /></div>
          <Iskelet class="h-8 w-24 mb-2" /><Iskelet class="h-2.5 w-32" />
        </div>
      </div>
      <div class="grid grid-cols-12 gap-4">
        <div v-for="i in 3" :key="i" class="col-span-12 lg:col-span-4 rounded-xl border border-line bg-bg-card p-4 space-y-3"><Iskelet class="h-3 w-32 mb-4" /><Iskelet v-for="j in 6" :key="j" class="h-2.5 w-full" /></div>
      </div>
    </template>

    <template v-else>
      <!-- KPI -->
      <div v-if="env" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <KpiKarti baslik="Envanter kaydı" :deger="env.satir" :alt="`${env.birim.length} birim · ${env.faaliyet.length} faaliyet`" ikon="database" renk="indigo" rozet="VERBİS" :gecikme="0" />
        <KpiKarti baslik="Kritik bulgu" :deger="env.seviye.kritik || 0" alt="acil müdahale gerektirir" ikon="triangle-exclamation" renk="rose" :rozet="env.seviye.kritik ? 'acil' : ''" :gecikme="60" />
        <KpiKarti baslik="Toplam bulgu" :deger="env.bulgu" :alt="`${sayi(env.seviye.yuksek || 0)} yüksek · ${sayi(env.seviye.orta || 0)} orta`" ikon="list-check" renk="amber" :gecikme="120" />
        <KpiKarti baslik="Uyum oranı" :deger="Math.round(uyum)" sonek="%" alt="bulgusuz kayıt oranı" ikon="shield-halved" :renk="uyum >= 50 ? 'emerald' : 'rose'" :gecikme="180">
          <div class="mt-3 h-1.5 rounded-full bg-bg-3 overflow-hidden"><div class="h-full rounded-full cubuk-dolum" :class="uyum >= 50 ? 'bg-emerald-500' : 'bg-rose-500'" :style="{ width: uyum + '%' }"></div></div>
        </KpiKarti>
      </div>

      <!-- yonetim seridi: tek satir, dort esit hucre -->
      <div v-if="veri.yonetim" class="kart-giris grid grid-cols-2 md:grid-cols-5 rounded-xl border border-line bg-bg-card divide-x divide-line-60" style="animation-delay:220ms">
        <button v-for="t in YONETIM" :key="t[1]" class="flex items-center gap-3 px-4 py-3 text-left hover:bg-bg-hover/60 first:rounded-l-xl last:rounded-r-xl" @click="router.push({ name: t[3] })">
          <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg" :class="t[4]"><FaIcon :icon="t[0]" class="h-3.5 w-3.5" /></span>
          <span class="min-w-0">
            <span class="block font-mono text-lg font-bold text-t-1 leading-none">{{ t[2] === 'kuyruk' ? kuyrukDeger(veri.yonetim.kuyruk) : veri.yonetim[t[2]] }}</span>
            <span class="block text-[10px] uppercase tracking-wider text-t-3 mt-1 truncate">{{ t[1] }}<span v-if="t[2] === 'kullanici'" class="normal-case text-emerald-400"> · {{ veri.yonetim.aktif_kullanici }} aktif</span><span v-else-if="t[2] === 'kuyruk' && veri.yonetim.kuyruk?.failed" class="normal-case text-rose-400"> · {{ veri.yonetim.kuyruk.failed }} hatalı</span><span v-else-if="t[2] === 'kuyruk'" class="normal-case"> · bekleyen iş</span></span>
          </span>
        </button>
      </div>

      <!-- grafikler: 5 / 4 / 3, esit yukseklik -->
      <div v-if="env" class="grid grid-cols-12 gap-4">
        <div class="kart-giris col-span-12 lg:col-span-6 xl:col-span-5 rounded-xl border border-line bg-bg-card p-4 flex flex-col" style="animation-delay:260ms">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-xs font-bold uppercase tracking-wider text-t-1 flex items-center gap-2 min-w-0 truncate"><FaIcon icon="diagram-project" class="h-3.5 w-3.5 text-indigo-400" />Kural radarı</h3>
            <span class="text-[10.5px] font-mono text-t-3 shrink-0 hidden 2xl:inline">bulgu adedi</span>
          </div>
          <div class="flex-1 min-h-0"><RadarGrafik :eksenler="radar" :boyut="230" /></div>
        </div>
        <div class="kart-giris col-span-12 lg:col-span-6 xl:col-span-4 rounded-xl border border-line bg-bg-card p-4 flex flex-col" style="animation-delay:320ms">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-xs font-bold uppercase tracking-wider text-t-1 flex items-center gap-2 min-w-0 truncate"><FaIcon icon="layer-group" class="h-3.5 w-3.5 text-indigo-400" />Veri kategorileri</h3>
            <span class="text-[10.5px] font-mono text-t-3 shrink-0 hidden 2xl:inline">{{ env.veri_kategorisi.length }} kategori</span>
          </div>
          <div class="flex-1 min-h-0"><CubukGrafik :veriler="kategoriler" :en-fazla="7" /></div>
        </div>
        <div class="kart-giris col-span-12 xl:col-span-3 rounded-xl border border-line bg-bg-card p-4 flex flex-col" style="animation-delay:380ms">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-xs font-bold uppercase tracking-wider text-t-1 flex items-center gap-2 min-w-0 truncate"><FaIcon icon="fire" class="h-3.5 w-3.5 text-rose-400" />Bulgu seviyeleri</h3>
            <span class="text-[10.5px] font-mono text-t-3 shrink-0 hidden 2xl:inline">{{ sayi(env.bulgu) }} bulgu</span>
          </div>
          <!-- yigin cubuk: dagilimin tek bakista gorunumu -->
          <div class="flex h-2.5 rounded-md overflow-hidden bg-bg-3 gap-px mb-4">
            <div v-for="s in seviyeler" :key="s.k" class="h-full cubuk-dolum" :class="'bg-' + seviye(s.k).renk + '-500'" :style="{ width: s.yuzde + '%' }" :title="`${seviye(s.k).etiket}: ${s.adet}`"></div>
          </div>
          <div class="flex-1 flex flex-col justify-around gap-2 sm:grid sm:grid-cols-2 xl:flex xl:flex-col">
            <div v-for="s in seviyeler" :key="s.k" class="flex items-center justify-between gap-2">
              <Rozet :tur="s.k" boyut="xs" sekil="rounded" :nokta="true" :nabiz="s.k === 'kritik' && s.adet > 0">{{ seviye(s.k).etiket }}</Rozet>
              <span class="font-mono text-[11px] text-t-2 tabular-nums"><span class="text-t-1 font-semibold">{{ sayi(s.adet) }}</span> · %{{ s.yuzde }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- listeler: uc esit kart, her biri en fazla SATIR satir -->
      <div v-if="veri.riskli_faaliyetler || veri.son_hareketler || veri.denetim_gunlugu" class="grid grid-cols-12 gap-4">
        <!-- riskli faaliyetler -->
        <div v-if="veri.riskli_faaliyetler" class="kart-giris col-span-12 lg:col-span-6 xl:col-span-4 rounded-xl border border-line bg-bg-card overflow-hidden flex flex-col" style="animation-delay:440ms">
          <div class="border-b border-line bg-bg-1/70 px-4 py-3 flex items-center justify-between">
            <h3 class="text-xs font-bold uppercase tracking-wider text-t-1 flex items-center gap-2 min-w-0 truncate"><FaIcon icon="arrow-trend-up" class="h-3.5 w-3.5 text-rose-400" />En riskli faaliyetler</h3>
            <span class="text-[10.5px] font-mono text-t-3 shrink-0 hidden 2xl:inline">ilk {{ riskli.length }}</span>
          </div>
          <div class="flex-1 divide-y divide-line-60">
            <div v-for="(f, i) in riskli" :key="f.faaliyet" class="px-4 h-[42px] flex items-center gap-3 hover:bg-bg-hover/60 text-[11px]">
              <span class="w-4 text-[10px] font-mono text-t-muted text-right shrink-0">{{ i + 1 }}</span>
              <span class="min-w-0 flex-1 truncate font-semibold text-t-1" :title="f.faaliyet">{{ f.faaliyet }}</span>
              <span class="font-mono text-[10px] text-t-3 shrink-0 hidden sm:inline">{{ f.satir }} satır · {{ f.bulgu }} bulgu</span>
              <Rozet :tur="f.kritik ? 'kritik' : 'notr'" boyut="xs" sekil="rounded" :nokta="!!f.kritik">{{ sayi(f.kritik) }} kritik</Rozet>
            </div>
            <p v-if="!riskli.length" class="px-4 py-6 text-xs text-t-3">Kapsamınızda faaliyet yok.</p>
          </div>
          <button v-if="auth.can('findings.view')" class="border-t border-line px-4 py-2 text-[11px] text-indigo-400 hover:bg-bg-hover/60 flex items-center justify-center gap-1" @click="router.push({ name: 'bulgular' })">Bulgulara git <FaIcon icon="arrow-right" class="h-2.5 w-2.5" /></button>
        </div>

        <!-- son hareketler -->
        <div v-if="veri.son_hareketler" class="kart-giris col-span-12 lg:col-span-6 xl:col-span-4 rounded-xl border border-line bg-bg-card overflow-hidden flex flex-col" style="animation-delay:500ms">
          <div class="border-b border-line bg-bg-1/70 px-4 py-3 flex items-center justify-between">
            <h3 class="text-xs font-bold uppercase tracking-wider text-t-1 flex items-center gap-2 min-w-0 truncate"><FaIcon icon="bolt" class="h-3.5 w-3.5 text-amber-400" />Son hareketler</h3>
            <span class="text-[10.5px] font-mono text-t-3 shrink-0 hidden 2xl:inline">envanter</span>
          </div>
          <div class="flex-1 divide-y divide-line-60">
            <div v-for="h in hareketler" :key="h.id" class="px-4 h-[42px] flex items-center gap-2.5 text-[11px]">
              <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md" :class="islem(h.islem).sinif"><FaIcon :icon="islem(h.islem).ikon" class="h-3 w-3" /></span>
              <span class="min-w-0 flex-1 truncate"><span class="font-mono text-indigo-300">#{{ h.satir_no }}</span> {{ islem(h.islem).ad }}<span v-if="h.kullanici" class="text-t-3"> · {{ h.kullanici }}</span></span>
              <span class="font-mono text-[10px] text-t-3 shrink-0" :title="h.zaman">{{ goreliZaman(h.zaman) }}</span>
            </div>
            <p v-if="!hareketler.length" class="px-4 py-6 text-xs text-t-3">Hareket yok.</p>
          </div>
          <button class="border-t border-line px-4 py-2 text-[11px] text-indigo-400 hover:bg-bg-hover/60 flex items-center justify-center gap-1" @click="router.push({ name: 'envanter' })">Envantere git <FaIcon icon="arrow-right" class="h-2.5 w-2.5" /></button>
        </div>

        <!-- denetim gunlugu -->
        <div v-if="veri.denetim_gunlugu" class="kart-giris col-span-12 xl:col-span-4 rounded-xl border border-line bg-bg-card overflow-hidden flex flex-col" style="animation-delay:560ms">
          <div class="border-b border-line bg-bg-1/70 px-4 py-3 flex items-center justify-between">
            <h3 class="text-xs font-bold uppercase tracking-wider text-t-1 flex items-center gap-2 min-w-0 truncate"><FaIcon icon="clock-rotate-left" class="h-3.5 w-3.5 text-orange-400" />Denetim günlüğü</h3>
            <span class="text-[10.5px] font-mono text-t-3 shrink-0 hidden 2xl:inline">sistem</span>
          </div>
          <div class="flex-1 divide-y divide-line-60">
            <div v-for="k in gunluk" :key="k.id" class="px-4 h-[42px] flex items-center gap-2.5 text-[11px]">
              <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md" :class="eylem(k.action)[2]"><FaIcon :icon="eylem(k.action)[1]" class="h-3 w-3" /></span>
              <span class="min-w-0 flex-1 truncate"><span class="font-semibold text-t-1">{{ (k.user_email || 'sistem').split('@')[0] }}</span> <span class="text-t-2">{{ eylem(k.action)[0] }}</span><span v-if="k.target_label && !k.action.startsWith('auth.')" class="text-t-3"> · {{ kisalt(k.target_label, 20) }}</span></span>
              <span class="font-mono text-[10px] text-t-3 shrink-0" :title="k.created_at">{{ goreliZaman(k.created_at) }}</span>
            </div>
            <p v-if="!gunluk.length" class="px-4 py-6 text-xs text-t-3">Kayıt yok.</p>
          </div>
          <button class="border-t border-line px-4 py-2 text-[11px] text-indigo-400 hover:bg-bg-hover/60 flex items-center justify-center gap-1" @click="router.push({ name: 'gunluk' })">Tümünü gör <FaIcon icon="arrow-right" class="h-2.5 w-2.5" /></button>
        </div>
      </div>

      <div v-if="!env && !veri.yonetim" class="rounded-xl border border-line bg-bg-card p-6 text-xs text-t-3 flex items-center gap-2"><FaIcon icon="circle-info" class="h-4 w-4" />Rolünüz panelde gösterilecek bir modüle erişim vermiyor.</div>
    </template>
  </section>
</template>
