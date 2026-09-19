<script setup>
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../../stores/auth';
import { ilkSayfa } from '../../router';

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const email = ref('');
const sifre = ref('');
const hata = ref('');
const bekliyor = ref(false);
const bilgi = ref(route.query.mesaj || '');

async function giris() {
  hata.value = '';
  if (!email.value.trim() || !sifre.value) { hata.value = 'E-posta ve şifre zorunludur.'; return; }
  bekliyor.value = true;
  try {
    await auth.login(email.value.trim(), sifre.value);
    const hedef = route.query.redirect;
    router.push(hedef && String(hedef).startsWith('/') ? String(hedef) : ilkSayfa(auth));
  } catch (e) {
    hata.value = e.status === 401 ? 'E-posta veya şifre hatalı.' : (e.message || 'Giriş yapılamadı.');
    sifre.value = '';
  } finally { bekliyor.value = false; }
}
</script>

<template>
  <form @submit.prevent="giris" novalidate>
    <h2 class="text-sm font-bold text-white mb-1">Oturum Aç</h2>

    <p v-if="bilgi" class="mb-4 px-3 py-2 rounded-lg text-[11px] bg-emerald-500/10 border border-emerald-500/25 text-emerald-300">{{ bilgi }}</p>

    <label class="block text-[11px] font-semibold text-[var(--t1)] mb-1" for="giris-eposta">E-posta</label>
    <input id="giris-eposta" v-model="email" type="email" autocomplete="username" autofocus class="girdi girdi-lg mb-3">

    <div class="flex items-center justify-between mb-1">
      <label class="text-[11px] font-semibold text-[var(--t1)]" for="giris-sifre">Şifre</label>
      <router-link :to="{ name: 'sifremi-unuttum' }" class="text-[11px] text-indigo-400 hover:text-indigo-300">Şifremi unuttum</router-link>
    </div>
    <input id="giris-sifre" v-model="sifre" type="password" autocomplete="current-password" class="girdi girdi-lg mb-4">

    <p v-if="hata" class="mb-3 text-[11px] text-rose-400" role="alert">{{ hata }}</p>

    <button type="submit" :disabled="bekliyor"
      class="w-full h-9 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white text-xs font-bold shadow-lg shadow-indigo-600/30">
      {{ bekliyor ? 'Giriş yapılıyor…' : 'Giriş Yap' }}
    </button>
    <div class="mt-4">
      <p class="text-[11px] font-semibold text-[var(--t1)] mb-1">Demo Bilgileri:</p>
      <div class="mb-2">
        <p class="text-[11px] text-[var(--t2)]"><strong class="font-semibold">E-posta:</strong> admin@kvkk.local</p>
        <p class="text-[11px] text-[var(--t2)]"><strong class="font-semibold">Şifre:</strong> admin1234</p>
      </div>
    </div>
  </form>
</template>
