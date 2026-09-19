<script setup>
// Profilim: ad/e-posta, sifre degistirme, roller/kapsam (salt okunur), aktif oturumlar.
import { computed, onMounted, reactive, ref } from 'vue';
import { auth as authApi } from '../api';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import { tarih } from '../utils/format';
import DataTable from '../components/DataTable.vue';

const OTURUM_SUTUNLARI = [
  { key: 'cihaz', label: 'Cihaz' },
  { key: 'olusturma', label: 'Açılış', sortable: true },
  { key: 'son_kullanim', label: 'Son kullanım', sortable: true },
  { key: 'bitis', label: 'Bitiş' },
  { key: 'islem', label: '', align: 'right', width: 'w-16' },
];

const auth = useAuthStore();
const ui = useUiStore();

const profil = reactive({ name: auth.user?.name || '', email: auth.user?.email || '' });
const profilBekliyor = ref(false);
const profilHata = ref({});

const sifre = reactive({ current_password: '', password: '', password_confirmation: '' });
const sifreBekliyor = ref(false);
const sifreHata = ref({});

const oturumlar = ref([]);
const oturumYukleniyor = ref(false);

const kapsamlar = computed(() => Object.entries(auth.user?.scopes || {}));
const basHarf = computed(() => (auth.user?.name || '?').split(/\s+/).map((p) => p[0]).join('').slice(0, 2).toUpperCase());

async function profilKaydet() {
  profilHata.value = {};
  if (!profil.name.trim() || profil.name.trim().length < 2) { profilHata.value.name = 'Ad en az 2 karakter olmalıdır.'; return; }
  profilBekliyor.value = true;
  try {
    const d = await authApi.profilGuncelle({ name: profil.name.trim(), email: profil.email.trim().toLowerCase() });
    auth.user = d.user; auth.kaydet();
    ui.bildir('Profil güncellendi.');
  } catch (e) {
    if (e.errors) profilHata.value = Object.fromEntries(Object.entries(e.errors).map(([k, v]) => [k, v[0]]));
    else profilHata.value = { _: e.message };
  } finally { profilBekliyor.value = false; }
}

async function sifreDegistir() {
  sifreHata.value = {};
  if (sifre.password.length < 8) sifreHata.value.password = 'Şifre en az 8 karakter olmalıdır.';
  if (sifre.password !== sifre.password_confirmation) sifreHata.value.password_confirmation = 'Şifre tekrarı eşleşmiyor.';
  if (!sifre.current_password) sifreHata.value.current_password = 'Mevcut şifre zorunludur.';
  if (Object.keys(sifreHata.value).length) return;
  sifreBekliyor.value = true;
  try {
    const d = await authApi.sifreDegistir({ ...sifre });
    Object.assign(sifre, { current_password: '', password: '', password_confirmation: '' });
    ui.bildir(`${d.mesaj} ${d.iptal_edilen_oturum ? d.iptal_edilen_oturum + ' diğer oturum kapatıldı.' : ''}`);
    oturumlariYukle();
  } catch (e) {
    if (e.errors) sifreHata.value = Object.fromEntries(Object.entries(e.errors).map(([k, v]) => [k, v[0]]));
    else sifreHata.value = { _: e.message };
  } finally { sifreBekliyor.value = false; }
}

async function oturumlariYukle() {
  oturumYukleniyor.value = true;
  try { oturumlar.value = (await authApi.oturumlar()).oturumlar; } catch {}
  finally { oturumYukleniyor.value = false; }
}
async function oturumKapat(o) {
  try { await authApi.oturumKapat(o.id); ui.bildir('Oturum kapatıldı.'); oturumlariYukle(); }
  catch (e) { ui.bildir(e.message, 'hata'); }
}
async function digerleriniKapat() {
  try { const d = await authApi.digerOturumlariKapat(); ui.bildir(`${d.iptal_edilen_oturum} oturum kapatıldı.`); oturumlariYukle(); }
  catch (e) { ui.bildir(e.message, 'hata'); }
}

onMounted(oturumlariYukle);
</script>

<template>
  <section class="max-w-5xl mx-auto space-y-6">
    <div class="flex items-center gap-4">
      <div class="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600 text-lg font-bold text-white shadow-lg shadow-indigo-500/25">{{ basHarf }}</div>
      <div>
        <h1 class="text-2xl font-extrabold text-t-1 tracking-tight">{{ auth.user?.name }}</h1>
        <p class="text-xs text-t-2">{{ auth.user?.email }} · <span class="text-indigo-300">{{ auth.roller.join(', ') || 'rol yok' }}</span><span v-if="auth.user?.departments?.length"> · {{ auth.user.departments.join(', ') }}</span></p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
      <!-- Profil -->
      <form class="rounded-xl border border-line bg-bg-card p-5" @submit.prevent="profilKaydet" novalidate>
        <h3 class="text-xs font-bold uppercase tracking-wider text-t-1 mb-3">Hesap Bilgileri</h3>
        <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1" for="p-ad">Ad Soyad</label>
        <input id="p-ad" v-model="profil.name" class="girdi mb-1">
        <p v-if="profilHata.name" class="text-[11px] text-rose-400 mb-2">{{ profilHata.name }}</p>
        <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1 mt-3" for="p-eposta">E-posta</label>
        <input id="p-eposta" v-model="profil.email" type="email" class="girdi mb-1">
        <p v-if="profilHata.email" class="text-[11px] text-rose-400 mb-2">{{ profilHata.email }}</p>
        <p v-if="profilHata._" class="text-[11px] text-rose-400 mb-2">{{ profilHata._ }}</p>
        <div class="flex justify-end mt-4">
          <button type="submit" :disabled="profilBekliyor" class="rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 px-4 py-1.5 text-xs font-semibold text-white"><FaIcon :icon="profilBekliyor ? 'spinner' : 'floppy-disk'" class="h-3 w-3 mr-1.5" :class="profilBekliyor ? 'animate-spin' : ''" />{{ profilBekliyor ? 'Kaydediliyor…' : 'Kaydet' }}</button>
        </div>
      </form>

      <!-- Sifre -->
      <form class="rounded-xl border border-line bg-bg-card p-5" @submit.prevent="sifreDegistir" novalidate>
        <h3 class="text-xs font-bold uppercase tracking-wider text-t-1 mb-1">Şifre Değiştir</h3>
        <p class="text-[11px] text-t-3 mb-3">Kaydedince bu oturum dışındaki tüm oturumlar kapatılır.</p>
        <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1" for="s-mevcut">Mevcut şifre</label>
        <input id="s-mevcut" v-model="sifre.current_password" type="password" autocomplete="current-password" class="girdi mb-1">
        <p v-if="sifreHata.current_password" class="text-[11px] text-rose-400 mb-2">{{ sifreHata.current_password }}</p>
        <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1 mt-3" for="s-yeni">Yeni şifre</label>
        <input id="s-yeni" v-model="sifre.password" type="password" autocomplete="new-password" class="girdi mb-1">
        <p v-if="sifreHata.password" class="text-[11px] text-rose-400 mb-2">{{ sifreHata.password }}</p>
        <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1 mt-3" for="s-tekrar">Yeni şifre (tekrar)</label>
        <input id="s-tekrar" v-model="sifre.password_confirmation" type="password" autocomplete="new-password" class="girdi mb-1">
        <p v-if="sifreHata.password_confirmation" class="text-[11px] text-rose-400 mb-2">{{ sifreHata.password_confirmation }}</p>
        <p v-if="sifreHata._" class="text-[11px] text-rose-400 mb-2">{{ sifreHata._ }}</p>
        <div class="flex justify-end mt-4">
          <button type="submit" :disabled="sifreBekliyor" class="rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 px-4 py-1.5 text-xs font-semibold text-white"><FaIcon :icon="sifreBekliyor ? 'spinner' : 'key'" class="h-3 w-3 mr-1.5" :class="sifreBekliyor ? 'animate-spin' : ''" />{{ sifreBekliyor ? 'Kaydediliyor…' : 'Şifreyi Güncelle' }}</button>
        </div>
      </form>

      <!-- Yetkiler -->
      <div class="rounded-xl border border-line bg-bg-card p-5">
        <h3 class="text-xs font-bold uppercase tracking-wider text-t-1 mb-3">Rol, İzin ve Kapsam</h3>
        <div class="flex flex-wrap gap-1.5 mb-3">
          <span v-for="r in auth.roller" :key="r" class="rounded bg-indigo-500/10 px-2 py-0.5 text-[11px] font-semibold text-indigo-300 border border-indigo-500/20">{{ r }}</span>
          <span v-if="auth.isSuper" class="rounded bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-300 border border-emerald-500/20">Kapsam kontrolünü atlar</span>
        </div>
        <div v-if="kapsamlar.length" class="space-y-2">
          <div v-for="[modul, aksiyonlar] in kapsamlar" :key="modul" class="rounded-lg bg-bg-2 border border-line-60 p-2.5">
            <p class="text-[10.5px] font-bold uppercase tracking-wider text-t-3 mb-1">{{ modul }}</p>
            <div class="flex flex-wrap gap-1">
              <span v-for="(k, a) in aksiyonlar" :key="a" class="text-[10.5px] font-mono px-1.5 py-0.5 rounded bg-bg-3 border border-line text-t-2">{{ a }}: <span class="text-indigo-300">{{ k }}</span></span>
            </div>
          </div>
        </div>
        <p v-else class="text-[11px] text-t-3">Kapsamlı modül izni yok.</p>
        <p class="text-[10.5px] text-t-3 mt-3">{{ auth.isSuper ? 'Tüm izinler' : auth.permissions.length + ' izin' }} · rol ve kapsam değişiklikleri yöneticiniz tarafından yapılır.</p>
      </div>

      <!-- Oturumlar -->
      <div class="rounded-xl border border-line bg-bg-card p-5">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-xs font-bold uppercase tracking-wider text-t-1">Aktif Oturumlar</h3>
          <button v-if="oturumlar.length > 1" class="text-[11px] font-semibold text-rose-400 hover:text-rose-300" @click="digerleriniKapat"><FaIcon icon="power-off" class="h-3 w-3 mr-1" />Diğer oturumları kapat</button>
        </div>
        <div class="rounded-lg border border-line-60 bg-bg-2/40 overflow-hidden">
          <DataTable :columns="OTURUM_SUTUNLARI" :rows="oturumlar" row-key="id" :loading="oturumYukleniyor" dense empty-text="Oturum yok."
            :row-class="(o) => o.mevcut ? 'bg-emerald-500/5' : ''">
            <template #cell-cihaz="{ row: o }"><span class="font-semibold text-t-1">{{ o.cihaz }}</span><span v-if="o.mevcut" class="ml-1.5 rounded bg-emerald-500/10 px-1.5 py-0.5 text-[9.5px] font-semibold text-emerald-300">bu oturum</span></template>
            <template #cell-olusturma="{ value }"><span class="font-mono text-[10.5px] text-t-3">{{ tarih(value) }}</span></template>
            <template #cell-son_kullanim="{ value }"><span class="font-mono text-[10.5px] text-t-3">{{ value ? tarih(value) : '—' }}</span></template>
            <template #cell-bitis="{ value }"><span class="font-mono text-[10.5px] text-t-3">{{ value ? tarih(value) : '—' }}</span></template>
            <template #cell-islem="{ row: o }"><button v-if="!o.mevcut" class="text-[11px] text-t-3 hover:text-rose-300" @click="oturumKapat(o)"><FaIcon icon="power-off" class="h-3 w-3 mr-1" />Kapat</button></template>
          </DataTable>
        </div>
      </div>
    </div>
  </section>
</template>
