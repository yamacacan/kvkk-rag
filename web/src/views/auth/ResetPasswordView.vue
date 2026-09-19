<script setup>
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { auth as authApi } from '../../api';

const route = useRoute();
const router = useRouter();

const token = computed(() => String(route.query.token || ''));
const email = ref(String(route.query.email || ''));
const sifre = ref('');
const tekrar = ref('');
const hata = ref('');
const alanHatalari = ref({});
const bekliyor = ref(false);
const gecersizBaglanti = computed(() => !token.value);

function dogrula() {
  const h = {};
  if (!email.value.trim()) h.email = 'E-posta zorunludur.';
  if (sifre.value.length < 8) h.password = 'Şifre en az 8 karakter olmalıdır.';
  if (sifre.value !== tekrar.value) h.password_confirmation = 'Şifre tekrarı eşleşmiyor.';
  alanHatalari.value = h;
  return !Object.keys(h).length;
}

async function sifirla() {
  hata.value = '';
  if (!dogrula()) return;
  bekliyor.value = true;
  try {
    const d = await authApi.resetPassword({
      email: email.value.trim().toLowerCase(), token: token.value,
      password: sifre.value, password_confirmation: tekrar.value,
    });
    router.push({ name: 'login', query: { mesaj: d.mesaj } });
  } catch (e) {
    if (e.errors) alanHatalari.value = Object.fromEntries(Object.entries(e.errors).map(([k, v]) => [k, v[0]]));
    hata.value = e.message || 'Şifre sıfırlanamadı.';
  } finally { bekliyor.value = false; }
}
</script>

<template>
  <div v-if="gecersizBaglanti">
    <h2 class="text-sm font-bold text-white mb-2">Bağlantı geçersiz</h2>
    <p class="text-[12px] text-[var(--t1)] mb-4">Bu sayfaya e-postadaki sıfırlama bağlantısıyla gelinmelidir.</p>
    <router-link :to="{ name: 'sifremi-unuttum' }" class="block text-center text-[11px] text-indigo-400 hover:text-indigo-300">Yeni bağlantı iste →</router-link>
  </div>

  <form v-else @submit.prevent="sifirla" novalidate>
    <h2 class="text-sm font-bold text-white mb-1">Yeni Şifre Belirle</h2>
    <p class="text-[11px] text-[var(--t2)] mb-5">Şifre en az 8 karakter olmalı. Kaydedince tüm açık oturumlarınız kapatılır.</p>

    <label class="block text-[11px] font-semibold text-[var(--t1)] mb-1" for="sif-eposta">E-posta</label>
    <input id="sif-eposta" v-model="email" type="email" autocomplete="username" class="girdi girdi-lg mb-1">
    <p v-if="alanHatalari.email" class="mb-2 text-[11px] text-rose-400">{{ alanHatalari.email }}</p>
    <div v-else class="mb-3"></div>

    <label class="block text-[11px] font-semibold text-[var(--t1)] mb-1" for="sif-yeni">Yeni şifre</label>
    <input id="sif-yeni" v-model="sifre" type="password" autocomplete="new-password" autofocus class="girdi girdi-lg mb-1">
    <p v-if="alanHatalari.password" class="mb-2 text-[11px] text-rose-400">{{ alanHatalari.password }}</p>
    <div v-else class="mb-3"></div>

    <label class="block text-[11px] font-semibold text-[var(--t1)] mb-1" for="sif-tekrar">Yeni şifre (tekrar)</label>
    <input id="sif-tekrar" v-model="tekrar" type="password" autocomplete="new-password" class="girdi girdi-lg mb-1">
    <p v-if="alanHatalari.password_confirmation" class="mb-2 text-[11px] text-rose-400">{{ alanHatalari.password_confirmation }}</p>
    <div v-else class="mb-3"></div>

    <p v-if="hata" class="mb-3 text-[11px] text-rose-400" role="alert">{{ hata }}</p>

    <button type="submit" :disabled="bekliyor"
      class="w-full h-9 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white text-xs font-bold shadow-lg shadow-indigo-600/30">
      {{ bekliyor ? 'Kaydediliyor…' : 'Şifreyi Güncelle' }}
    </button>
    <router-link :to="{ name: 'login' }" class="block mt-4 text-center text-[11px] text-indigo-400 hover:text-indigo-300">← Girişe dön</router-link>
  </form>
</template>
