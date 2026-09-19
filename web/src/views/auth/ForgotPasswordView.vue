<script setup>
import { ref } from 'vue';
import { auth as authApi } from '../../api';

const email = ref('');
const hata = ref('');
const bekliyor = ref(false);
const sonuc = ref(null); // {mesaj, gelistirme?}

async function gonder() {
  hata.value = '';
  const e = email.value.trim().toLowerCase();
  if (!e || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e)) { hata.value = 'Geçerli bir e-posta adresi girin.'; return; }
  bekliyor.value = true;
  try {
    sonuc.value = await authApi.forgotPassword(e);
  } catch (err) {
    hata.value = err.message || 'İstek gönderilemedi.';
  } finally { bekliyor.value = false; }
}
</script>

<template>
  <div v-if="sonuc">
    <h2 class="text-sm font-bold text-white mb-2">Bağlantı gönderildi</h2>
    <p class="text-[12px] text-[var(--t1)] leading-relaxed mb-4">{{ sonuc.mesaj }} Gelen kutunuzu (ve spam klasörünü) kontrol edin; bağlantı 60 dakika geçerlidir.</p>

    <div v-if="sonuc.gelistirme" class="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/25">
      <p class="text-[10.5px] font-bold uppercase tracking-wider text-amber-400 mb-1">Geliştirme modu</p>
      <p class="text-[11px] text-[var(--t1)] mb-2">E-posta sürücüsü <code class="font-mono">log</code>: bağlantı sunucu günlüğüne yazıldı, kolaylık için burada da:</p>
      <router-link :to="sonuc.gelistirme.reset_url.replace(/^https?:\/\/[^/]+/, '')"
        class="block break-all text-[11px] font-mono text-indigo-300 hover:text-white underline">{{ sonuc.gelistirme.reset_url }}</router-link>
    </div>

    <router-link :to="{ name: 'login' }" class="block text-center text-[11px] text-indigo-400 hover:text-indigo-300">← Girişe dön</router-link>
  </div>

  <form v-else @submit.prevent="gonder" novalidate>
    <h2 class="text-sm font-bold text-white mb-1">Şifremi Unuttum</h2>
    <p class="text-[11px] text-[var(--t2)] mb-5">Kayıtlı e-posta adresinizi girin; yeni şifre belirlemeniz için tek kullanımlık bir bağlantı göndereceğiz.</p>

    <label class="block text-[11px] font-semibold text-[var(--t1)] mb-1" for="unut-eposta">E-posta</label>
    <input id="unut-eposta" v-model="email" type="email" autocomplete="username" autofocus class="girdi girdi-lg mb-4">

    <p v-if="hata" class="mb-3 text-[11px] text-rose-400" role="alert">{{ hata }}</p>

    <button type="submit" :disabled="bekliyor"
      class="w-full h-9 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white text-xs font-bold shadow-lg shadow-indigo-600/30">
      {{ bekliyor ? 'Gönderiliyor…' : 'Sıfırlama Bağlantısı Gönder' }}
    </button>
    <router-link :to="{ name: 'login' }" class="block mt-4 text-center text-[11px] text-indigo-400 hover:text-indigo-300">← Girişe dön</router-link>
  </form>
</template>
