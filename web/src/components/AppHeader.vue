<script setup>
// Ust uygulama cubugu: sidebar dugmesi, breadcrumb, komut paleti, denetim gunlugu, kullanici menusu.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import BildirimMenusu from './BildirimMenusu.vue';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();

const kirinti = computed(() => route.meta.kirinti || [route.meta.baslik || '']);
const menuAcik = ref(false);
const menuEl = ref(null);
const basHarf = computed(() => (auth.user?.name || '?').split(/\s+/).map((p) => p[0]).join('').slice(0, 2).toUpperCase());

function disTiklama(e) { if (menuEl.value && !menuEl.value.contains(e.target)) menuAcik.value = false; }
onMounted(() => document.addEventListener('click', disTiklama));
onBeforeUnmount(() => document.removeEventListener('click', disTiklama));

async function cikis() { menuAcik.value = false; await auth.oturumuKapat(); router.push({ name: 'login' }); }
function git(name) { menuAcik.value = false; router.push({ name }); }
</script>

<template>
  <header class="sticky top-0 z-40 flex items-center justify-between gap-4 border-b border-line bg-bg-1/90 px-4 lg:px-6 py-2.5 backdrop-blur-md">
    <div class="flex items-center gap-3 min-w-0">
      <button class="flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-bg-2 text-t-2 hover:text-t-1 hover:bg-bg-3" :title="ui.sidebarDar ? 'Menüyü genişlet' : 'Menüyü daralt'" @click="ui.sidebarToggle()">
        <FaIcon icon="bars" class="h-3.5 w-3.5" />
      </button>
      <nav class="hidden md:flex items-center gap-1.5 text-xs text-t-3 min-w-0" aria-label="Breadcrumb">
        <template v-for="(k, i) in kirinti" :key="i">
          <FaIcon v-if="i" icon="chevron-right" class="h-2.5 w-2.5 text-t-muted shrink-0" />
          <span class="truncate" :class="i === kirinti.length - 1 ? 'font-medium text-indigo-400' : ''">{{ k }}</span>
        </template>
      </nav>
    </div>

    <div class="flex items-center gap-2">
      <button class="relative w-44 lg:w-64 text-left rounded-lg border border-line bg-bg-2/80 pl-9 pr-3 py-1.5 text-xs text-t-3 hover:border-line-bright" @click="ui.paletAcik = true">
        <FaIcon icon="magnifying-glass" class="pointer-events-none absolute left-3 top-2 h-3.5 w-3.5 text-t-3" />
        <span class="truncate">Sayfa, kullanıcı, envanter ara…</span>
        <kbd class="absolute right-2 top-1.5 text-[10px] font-mono text-t-3 border border-line rounded px-1">⌘K</kbd>
      </button>

      <button class="flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-bg-2 text-t-2 hover:text-t-1 hover:bg-bg-3"
        :title="ui.etkinTema === 'dark' ? 'Aydınlık moda geç' : 'Karanlık moda geç'" @click="ui.temaDegistir()">
        <FaIcon :icon="ui.etkinTema === 'dark' ? 'sun' : 'moon'" class="h-3.5 w-3.5" />
      </button>

      <BildirimMenusu />

      <button v-if="auth.can('audit.view')" class="hidden lg:flex items-center gap-1.5 rounded-lg border border-line bg-bg-2 px-3 py-1.5 text-xs font-medium text-t-2 hover:bg-bg-3 hover:text-t-1" @click="git('gunluk')">
        <FaIcon icon="clock-rotate-left" class="h-3.5 w-3.5 text-amber-400" />
        <span>Denetim Günlüğü</span>
      </button>

      <div ref="menuEl" class="relative">
        <button class="flex items-center gap-2 rounded-lg border border-line bg-bg-2 pl-1 pr-2.5 py-1 hover:bg-bg-3" @click="menuAcik = !menuAcik" aria-haspopup="menu" :aria-expanded="menuAcik">
          <span class="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-600 text-[11px] font-bold text-white">{{ basHarf }}</span>
          <span class="hidden sm:block text-left leading-tight">
            <span class="block text-xs font-semibold text-t-1 max-w-[140px] truncate">{{ auth.user?.name }}</span>
            <span class="block text-[10px] text-t-3 max-w-[140px] truncate">{{ auth.roller.join(', ') || 'rol yok' }}</span>
          </span>
          <FaIcon icon="chevron-down" class="h-2.5 w-2.5 text-t-3 transition-transform" :class="menuAcik ? 'rotate-180' : ''" />
        </button>
        <div v-if="menuAcik" class="absolute right-0 mt-2 w-64 rounded-xl border border-line bg-bg-1 shadow-2xl overflow-hidden" role="menu">
          <div class="px-4 py-3 border-b border-line">
            <p class="text-xs font-bold text-t-1 truncate">{{ auth.user?.name }}</p>
            <p class="text-[11px] text-t-3 truncate">{{ auth.user?.email }}</p>
          </div>
          <button class="w-full flex items-center gap-2.5 text-left px-4 py-2 text-xs text-t-2 hover:bg-bg-2 hover:text-t-1" role="menuitem" @click="git('profil')"><FaIcon icon="id-badge" class="h-3.5 w-3.5 text-indigo-400" fixed-width />Profilim & güvenlik</button>
          <button class="w-full flex items-center gap-2.5 text-left px-4 py-2 text-xs text-t-2 hover:bg-bg-2 hover:text-t-1" role="menuitem" @click="git('bildirimler')"><FaIcon icon="bell" class="h-3.5 w-3.5 text-amber-400" fixed-width />Bildirimlerim</button>
          <button v-if="auth.can('users.view')" class="w-full flex items-center gap-2.5 text-left px-4 py-2 text-xs text-t-2 hover:bg-bg-2 hover:text-t-1" role="menuitem" @click="git('kullanicilar')"><FaIcon icon="sliders" class="h-3.5 w-3.5 text-violet-400" fixed-width />Yönetim paneli</button>
          <div class="px-4 py-2 border-t border-line">
            <p class="text-[10px] uppercase tracking-wider text-t-3 mb-1.5">Görünüm</p>
            <div class="flex rounded-lg border border-line bg-bg-2 p-0.5 text-[11px]">
              <button v-for="t in [['dark', 'moon', 'Koyu'], ['light', 'sun', 'Açık'], ['system', 'circle-half-stroke', 'Sistem']]" :key="t[0]"
                class="flex-1 flex items-center justify-center gap-1 rounded-md py-1" :class="ui.tema === t[0] ? 'bg-acc-soft text-indigo-300 font-semibold' : 'text-t-3 hover:text-t-1'" @click="ui.temaAyarla(t[0])">
                <FaIcon :icon="t[1]" class="h-3 w-3" />{{ t[2] }}
              </button>
            </div>
          </div>
          <button class="w-full flex items-center gap-2.5 text-left px-4 py-2 text-xs text-t-2 hover:bg-bg-2 hover:text-t-1" role="menuitem" @click="ui.paletAcik = true; menuAcik = false"><FaIcon icon="keyboard" class="h-3.5 w-3.5 text-t-3" fixed-width />Komut paleti <kbd class="ml-auto text-[10px] font-mono text-t-3 border border-line rounded px-1">⌘K</kbd></button>
          <button class="w-full flex items-center gap-2.5 text-left px-4 py-2 text-xs text-rose-300 hover:bg-bg-2 border-t border-line" role="menuitem" @click="cikis"><FaIcon icon="right-from-bracket" class="h-3.5 w-3.5" fixed-width />Çıkış yap</button>
        </div>
      </div>
    </div>
  </header>
</template>
