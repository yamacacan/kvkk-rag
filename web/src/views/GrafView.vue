<script setup>
import { computed, onMounted, ref } from 'vue';
import { graf as grafApi } from '../api';
import { kisalt, sayi } from '../utils/format';
import DataTable from '../components/DataTable.vue';

const RISK_SUTUNLARI = [
  { key: 'faaliyet', label: 'Faaliyet', sortable: true },
  { key: 'satir', label: 'Satır', align: 'right', width: 'w-20', sortable: true },
  { key: 'bulgu', label: 'Bulgu', align: 'right', width: 'w-20', sortable: true },
  { key: 'kritik', label: 'Kritik', align: 'right', width: 'w-24', sortable: true },
];

const risk = ref(null);   // {faaliyetler, graf}
const hata = ref('');
const maddeNo = ref('6');
const madde = ref(null);
const maddeHata = ref('');
const maddeBekliyor = ref(false);

const dugumler = computed(() => Object.entries(risk.value?.graf?.nodes || {}).sort((a, b) => b[1] - a[1]));

async function maddeGetir() {
  maddeBekliyor.value = true; maddeHata.value = ''; madde.value = null;
  try { madde.value = await grafApi.madde(maddeNo.value.trim()); }
  catch (e) { maddeHata.value = e.message; }
  finally { maddeBekliyor.value = false; }
}

onMounted(async () => {
  try { risk.value = await grafApi.risk(10); } catch (e) { hata.value = e.message; }
  maddeGetir();
});
</script>

<template>
  <section>
    <h1 class="text-2xl font-extrabold text-white tracking-tight sm:text-3xl mb-1">Bilgi Grafiği</h1>
    <p class="text-xs text-[var(--t1)] mb-5">Envanter satırları, faaliyetler ve KVKK maddeleri arasındaki ilişkiler.</p>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div class="rounded-2xl border border-[var(--line)] bg-[var(--bg-2)] overflow-hidden">
        <div class="px-5 py-3 border-b border-[var(--line)] bg-[var(--bg-1)]/70"><h3 class="text-sm font-bold text-white">En Riskli Faaliyetler</h3></div>
        <DataTable :columns="RISK_SUTUNLARI" :rows="risk?.faaliyetler || []" row-key="faaliyet" :loading="!risk && !hata" :error="hata" dense empty-text="Faaliyet yok.">
          <template #cell-faaliyet="{ value }"><span class="text-xs font-semibold text-white">{{ value }}</span></template>
          <template #cell-satir="{ value }"><span class="font-mono text-[11px] text-[var(--t2)]">{{ sayi(value) }}</span></template>
          <template #cell-bulgu="{ value }"><span class="font-mono text-xs text-[var(--t1)]">{{ sayi(value) }}</span></template>
          <template #cell-kritik="{ value }"><span class="text-[10px] font-bold px-2 py-0.5 rounded" :class="value ? 'bg-rose-500/15 text-rose-400' : 'bg-[var(--bg-3)] text-[var(--t2)]'">{{ sayi(value) }} kritik</span></template>
        </DataTable>
      </div>
      <div class="rounded-2xl border border-[var(--line)] bg-[var(--bg-2)] overflow-hidden">
        <div class="px-5 py-3 border-b border-[var(--line)] bg-[var(--bg-1)]/70 flex items-center gap-2">
          <h3 class="text-sm font-bold text-white">Madde Etkisi</h3>
          <input v-model="maddeNo" class="w-16 bg-[var(--bg-inset)] border border-[var(--line)] rounded px-2 py-1 text-xs font-mono text-white focus:outline-none" @keydown.enter="maddeGetir">
          <button class="px-2.5 py-1 text-[11px] font-semibold rounded bg-[var(--bg-3)] border border-[var(--line)] text-[var(--t1)] hover:text-white" @click="maddeGetir">Getir</button>
        </div>
        <div class="p-5 text-xs text-[var(--t1)]">
          <span v-if="maddeBekliyor">Yükleniyor…</span>
          <span v-else-if="maddeHata" class="text-rose-400">Bulunamadı: {{ maddeHata }}</span>
          <template v-else-if="madde">
            <p class="text-sm font-bold text-white mb-1">KVKK m.{{ maddeNo }} — {{ madde.madde?.props?.baslik || '' }}</p>
            <p class="mb-3">Bu maddeye <strong class="text-indigo-400 font-mono">{{ madde.atif_yapan_karar }}</strong> Kurul kararı atıf yapıyor.</p>
            <p class="text-[11px] font-bold uppercase tracking-wider text-[var(--t2)] mb-1">Bağlı hukuki sebepler</p>
            <ul class="space-y-1 mb-3">
              <li v-for="s in madde.hukuki_sebepler" :key="s" class="text-[11px] text-slate-300">• {{ kisalt(s, 80) }}</li>
              <li v-if="!madde.hukuki_sebepler?.length" class="text-[11px] text-[var(--t2)]">—</li>
            </ul>
            <p class="text-[11px] font-bold uppercase tracking-wider text-[var(--t2)] mb-1">Atıf yapan kararlar (ilk 10)</p>
            <div class="flex flex-wrap gap-1">
              <span v-for="k in (madde.kararlar || []).slice(0, 10)" :key="k.label" class="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-3)] border border-[var(--line)] text-indigo-300">{{ k.label }}</span>
            </div>
          </template>
        </div>
      </div>
      <div class="rounded-2xl border border-[var(--line)] bg-[var(--bg-2)] overflow-hidden lg:col-span-2">
        <div class="px-5 py-3 border-b border-[var(--line)] bg-[var(--bg-1)]/70"><h3 class="text-sm font-bold text-white">Graf İstatistikleri</h3></div>
        <div class="p-5 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 text-xs">
          <div v-for="[t, n] in dugumler" :key="t" class="p-3 rounded-lg bg-[var(--bg-inset)] border border-[var(--line)]">
            <p class="text-[10px] uppercase tracking-wider text-[var(--t2)]">{{ t }}</p>
            <p class="font-mono text-lg font-bold text-white">{{ sayi(n) }}</p>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
