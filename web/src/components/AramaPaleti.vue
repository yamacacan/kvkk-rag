<script setup>
// Komut paleti (⌘K / Ctrl+K): sayfalar, kullanicilar (izin varsa) ve envanter aramasi.
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { kullanicilar as kullaniciApi } from '../api';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';

const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();

const SAYFALAR = [
  { ad: 'Panel', name: 'panel', ipucu: 'Genel bakış' },
  { ad: 'Veri Envanteri', name: 'envanter', izin: 'inventory.view', ipucu: 'Kişisel veri işleme envanteri' },
  { ad: 'Uyum Bulguları', name: 'bulgular', izin: 'findings.view', ipucu: 'Kritik / yüksek bulgular' },
  { ad: 'Mevzuat Asistanı', name: 'asistan', izin: 'chat.use', ipucu: 'Sohbet ederek sorun' },
  { ad: 'Kurumsal Belgeler', name: 'belgeler', izin: 'documents.view', ipucu: 'Uyum belgeleri · politika, prosedür, form' },
  { ad: 'Faaliyet Belgeleri', name: 'faaliyet-belgeleri', izin: 'documents.view', ipucu: 'Aydınlatma metni & açık rıza beyanı (otomatik)' },
  { ad: 'Açık Rıza Kayıtları', name: 'acik-riza', izin: 'consents.view', ipucu: 'İlgili kişi rızaları' },
  { ad: 'Bilgi Grafiği', name: 'graf', izin: 'graph.view', ipucu: 'Madde etkisi, riskli faaliyetler' },
  { ad: 'Profilim', name: 'profil', ipucu: 'Hesap, şifre, oturumlar' },
  { ad: 'Bildirimler', name: 'bildirimler', ipucu: 'Tüm bildirimlerim' },
  { ad: 'Kullanıcılar', name: 'kullanicilar', izin: 'users.view', ipucu: 'Yönetim' },
  { ad: 'Roller & İzinler', name: 'roller', izin: 'roles.view', ipucu: 'Yönetim · yetki matrisi' },
  { ad: 'Birimler', name: 'birimler', izin: 'departments.view', ipucu: 'Yönetim · departmanlar' },
  { ad: 'Kurum Profili', name: 'kurum-profili', izin: 'profile.view', ipucu: 'Yönetim · belge başlıkları' },
  { ad: 'Denetim Günlüğü', name: 'gunluk', izin: 'audit.view', ipucu: 'Yönetim · audit trail' },
];

const q = ref('');
const secili = ref(0);
const girdi = ref(null);
const kullanicilar = ref([]);

const sayfalar = computed(() => SAYFALAR.filter((s) => !s.izin || auth.can(s.izin)));
const sonuclar = computed(() => {
  const t = q.value.trim().toLocaleLowerCase('tr');
  const out = [];
  sayfalar.value.filter((s) => !t || s.ad.toLocaleLowerCase('tr').includes(t) || (s.ipucu || '').toLocaleLowerCase('tr').includes(t))
    .forEach((s) => out.push({ tip: 'sayfa', ad: s.ad, ipucu: s.ipucu, git: () => router.push({ name: s.name }) }));
  if (t && auth.can('users.view')) {
    kullanicilar.value.filter((u) => u.name.toLocaleLowerCase('tr').includes(t) || u.email.includes(t)).slice(0, 5)
      .forEach((u) => out.push({ tip: 'kullanici', ad: u.name, ipucu: u.email + ' · ' + (u.roles || []).join(', '), git: () => router.push({ name: 'kullanicilar', query: { arama: u.email } }) }));
  }
  if (t && auth.can('inventory.view')) {
    out.push({ tip: 'envanter', ad: `Envanterde ara: "${q.value.trim()}"`, ipucu: 'Genel arama filtresiyle envanteri aç', git: () => router.push({ name: 'envanter', query: { arama: q.value.trim() } }) });
  }
  return out.slice(0, 12);
});

function kapat() { ui.paletAcik = false; q.value = ''; secili.value = 0; }
function sec(i) { const s = sonuclar.value[i]; if (s) { s.git(); kapat(); } }
function tus(e) {
  if (e.key === 'ArrowDown') { e.preventDefault(); secili.value = Math.min(secili.value + 1, sonuclar.value.length - 1); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); secili.value = Math.max(secili.value - 1, 0); }
  else if (e.key === 'Enter') { e.preventDefault(); sec(secili.value); }
  else if (e.key === 'Escape') kapat();
}
function kisayol(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); ui.paletAcik = !ui.paletAcik; }
}

watch(() => ui.paletAcik, async (acik) => {
  if (!acik) return;
  await nextTick(); girdi.value?.focus();
  if (auth.can('users.view') && !kullanicilar.value.length) {
    try { kullanicilar.value = (await kullaniciApi.liste()).kullanicilar || []; } catch {}
  }
});
watch(q, () => { secili.value = 0; });
onMounted(() => document.addEventListener('keydown', kisayol));
onBeforeUnmount(() => document.removeEventListener('keydown', kisayol));
</script>

<template>
  <div v-if="ui.paletAcik" class="fixed inset-0 z-[55] bg-black/60 backdrop-blur-sm flex items-start justify-center pt-[12vh] px-4" @click.self="kapat">
    <div class="w-full max-w-xl rounded-2xl border border-line bg-bg-1 shadow-2xl overflow-hidden">
      <div class="flex items-center gap-2 px-4 border-b border-line">
        <svg class="h-4 w-4 text-t-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        <input ref="girdi" v-model="q" @keydown="tus" placeholder="Sayfa, kullanıcı veya envanter ara…"
          class="flex-1 bg-transparent py-3 text-sm text-t-1 placeholder-t-3 focus:outline-none">
        <kbd class="text-[10px] font-mono text-t-3 border border-line rounded px-1.5 py-0.5">esc</kbd>
      </div>
      <ul class="max-h-80 overflow-y-auto custom-scroll py-1">
        <li v-for="(s, i) in sonuclar" :key="s.tip + s.ad" @mouseenter="secili = i" @click="sec(i)"
          class="px-4 py-2 flex items-center justify-between gap-3 cursor-pointer" :class="i === secili ? 'bg-acc-soft' : ''">
          <div class="min-w-0">
            <p class="text-xs font-semibold text-t-1 truncate">{{ s.ad }}</p>
            <p class="text-[10.5px] text-t-3 truncate">{{ s.ipucu }}</p>
          </div>
          <span class="text-[9.5px] font-mono uppercase tracking-wider text-t-3 border border-line rounded px-1.5 py-0.5 shrink-0">{{ s.tip }}</span>
        </li>
        <li v-if="!sonuclar.length" class="px-4 py-6 text-center text-xs text-t-3">Sonuç yok.</li>
      </ul>
    </div>
  </div>
</template>
