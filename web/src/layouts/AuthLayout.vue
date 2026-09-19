<script setup>
import { onMounted, ref } from 'vue';
import { sistem } from '../api';
import { useUiStore } from '../stores/ui';
import Logo from '../components/Logo.vue';

const ui = useUiStore();
const saglik = ref(null);
onMounted(async () => {
  try { saglik.value = await sistem.health(); } catch { saglik.value = false; }
});
</script>

<template>
  <div class="min-h-screen flex items-center justify-center p-4 bg-[var(--bg-0)] relative">
    <button class="absolute top-4 right-4 flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-bg-2 text-t-2 hover:text-t-1"
      :title="ui.etkinTema === 'dark' ? 'Aydınlık moda geç' : 'Karanlık moda geç'" @click="ui.temaDegistir()">
      <FaIcon :icon="ui.etkinTema === 'dark' ? 'sun' : 'moon'" class="h-3.5 w-3.5" />
    </button>
    <div class="w-full max-w-sm">
      <div class="flex flex-col items-center mb-6">
        <Logo tam class="h-40 w-40 select-none" />
        <p class="text-[11px] text-[var(--t2)] font-medium -mt-3">6698 · Veri Envanteri & Denetim</p>
      </div>

      <div class="p-6 rounded-2xl border border-[var(--line)] bg-[var(--bg-1)] shadow-2xl">
        <router-view v-slot="{ Component }">
          <transition name="sayfa" mode="out-in" :duration="{ enter: 180, leave: 100 }"><component :is="Component" /></transition>
        </router-view>
      </div>
    </div>
  </div>
</template>
