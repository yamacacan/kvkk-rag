<script setup>
// Denetim gunlugu (audit trail): kim, ne zaman, neyi degistirdi; once/sonra farki.
import { onMounted, ref, watch } from 'vue';
import { gunluk as gunlukApi } from '../../api';
import { debounce, kisalt, sayi, tarih } from '../../utils/format';
import Sayfalama from '../../components/Sayfalama.vue';
import DataTable from '../../components/DataTable.vue';
import SearchableSelect from '../../components/SearchableSelect.vue';

const SUTUNLAR = [
  { key: 'created_at', label: 'Zaman', width: 'w-44' },
  { key: 'user_email', label: 'Kim' },
  { key: 'action', label: 'Eylem' },
  { key: 'target_label', label: 'Hedef' },
  { key: 'detay', label: 'Detay', width: 'w-20', align: 'right' },
];

const EYLEM = {
  'auth.login': { ad: 'Giriş', sinif: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20' },
  'auth.login_failed': { ad: 'Başarısız giriş', sinif: 'bg-rose-500/10 text-rose-300 border-rose-500/20' },
  'auth.profile_update': { ad: 'Profil', sinif: 'bg-sky-500/10 text-sky-300 border-sky-500/20' },
  'auth.password_change': { ad: 'Şifre değişimi', sinif: 'bg-amber-500/10 text-amber-300 border-amber-500/20' },
  'auth.password_reset': { ad: 'Şifre sıfırlama', sinif: 'bg-amber-500/10 text-amber-300 border-amber-500/20' },
  'users.create': { ad: 'Kullanıcı oluştur', sinif: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20' },
  'users.update': { ad: 'Kullanıcı güncelle', sinif: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20' },
  'users.delete': { ad: 'Kullanıcı sil', sinif: 'bg-rose-500/10 text-rose-300 border-rose-500/20' },
  'roles.create': { ad: 'Rol oluştur', sinif: 'bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/20' },
  'roles.update': { ad: 'Rol / izin güncelle', sinif: 'bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/20' },
  'roles.clone': { ad: 'Rol klonla', sinif: 'bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/20' },
  'roles.delete': { ad: 'Rol sil', sinif: 'bg-rose-500/10 text-rose-300 border-rose-500/20' },
  'departments.create': { ad: 'Birim oluştur', sinif: 'bg-sky-500/10 text-sky-300 border-sky-500/20' },
  'departments.update': { ad: 'Birim güncelle', sinif: 'bg-sky-500/10 text-sky-300 border-sky-500/20' },
  'departments.delete': { ad: 'Birim sil', sinif: 'bg-rose-500/10 text-rose-300 border-rose-500/20' },
  'profile.update': { ad: 'Kurum profili', sinif: 'bg-teal-500/10 text-teal-300 border-teal-500/20' },
  'auth.logout': { ad: 'Çıkış', sinif: 'bg-bg-3 text-t-2 border-line' },
  'page.view': { ad: 'Sayfa görüntüleme', sinif: 'bg-slate-500/10 text-slate-300 border-slate-500/20' },
  'inventory.create': { ad: 'Envanter kaydı', sinif: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20' },
  'inventory.update': { ad: 'Envanter güncelle', sinif: 'bg-amber-500/10 text-amber-300 border-amber-500/20' },
  'inventory.delete': { ad: 'Envanter sil', sinif: 'bg-rose-500/10 text-rose-300 border-rose-500/20' },
  'inventory.import': { ad: 'Veri içe aktarım', sinif: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/20' },
  'inventory.export': { ad: 'Veri dışa aktarım', sinif: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/20' },
  'inventory.assign': { ad: 'Sorumlu atama', sinif: 'bg-violet-500/10 text-violet-300 border-violet-500/20' },
  'inventory.reindex': { ad: 'Yeniden indeksleme', sinif: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/20' },
  'documents.generate': { ad: 'Belge istendi', sinif: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20' },
  'documents.ready': { ad: 'Belge üretildi', sinif: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20' },
  'documents.failed': { ad: 'Belge hatası', sinif: 'bg-rose-500/10 text-rose-300 border-rose-500/20' },
  'documents.auto_refresh': { ad: 'Faaliyet belgesi yenilendi', sinif: 'bg-lime-500/10 text-lime-300 border-lime-500/20' },
  'documents.auto_failed': { ad: 'Faaliyet belgesi hatası', sinif: 'bg-rose-500/10 text-rose-300 border-rose-500/20' },
  'documents.refresh': { ad: 'Belge yenileme istendi', sinif: 'bg-lime-500/10 text-lime-300 border-lime-500/20' },
  'consents.create': { ad: 'Açık rıza kaydı', sinif: 'bg-teal-500/10 text-teal-300 border-teal-500/20' },
  'consents.update': { ad: 'Açık rıza güncelle', sinif: 'bg-teal-500/10 text-teal-300 border-teal-500/20' },
  'consents.delete': { ad: 'Açık rıza sil', sinif: 'bg-rose-500/10 text-rose-300 border-rose-500/20' },
  'queue.failed': { ad: 'Kuyruk hatası', sinif: 'bg-rose-500/10 text-rose-300 border-rose-500/20' },
  'inventory.failed': { ad: 'Envanter işi hatası', sinif: 'bg-rose-500/10 text-rose-300 border-rose-500/20' },
  'queue.retry': { ad: 'Kuyruk yeniden dene', sinif: 'bg-amber-500/10 text-amber-300 border-amber-500/20' },
};

const kayitlar = ref([]);
const eylemler = ref([]);
const toplam = ref(0);
const limit = ref(50);
const offset = ref(0);
const action = ref('');
const arama = ref('');
const sayfaGoruntuleme = ref(true); // page.view kayitlari listede gorunsun mu
const yukleniyor = ref(false);
const acik = ref(null);

async function yukle() {
  yukleniyor.value = true;
  try {
    const d = await gunlukApi.liste({ action: action.value, arama: arama.value, sayfa_goruntuleme: sayfaGoruntuleme.value ? '' : 'false', limit: limit.value, offset: offset.value });
    kayitlar.value = d.kayitlar; toplam.value = d.toplam; eylemler.value = d.eylemler;
  } catch (e) { kayitlar.value = []; }
  finally { yukleniyor.value = false; }
}
const yukleGecikmeli = debounce(yukle, 320);
watch([action, sayfaGoruntuleme], () => { offset.value = 0; yukle(); });
watch(arama, () => { offset.value = 0; yukleGecikmeli(); });
function fark(k) {
  const a = k.before || {}, b = k.after || {};
  return [...new Set([...Object.keys(a), ...Object.keys(b)])].filter((x) => JSON.stringify(a[x]) !== JSON.stringify(b[x]))
    .map((x) => ({ alan: x, once: a[x], sonra: b[x] }));
}
onMounted(yukle);
</script>

<template>
  <section class="space-y-5 max-w-[1780px] mx-auto">
    <div>
      <h1 class="text-2xl font-extrabold text-t-1 tracking-tight">Denetim Günlüğü</h1>
      <p class="text-xs text-t-2 mt-1">Kimlik ve yönetim işlemlerinin izi (audit trail). Envanter satırı değişiklikleri ayrıca satır geçmişinde tutulur.</p>
    </div>

    <div class="rounded-xl border border-line bg-bg-card overflow-hidden">
      <div class="border-b border-line bg-bg-1/80 px-4 py-3 flex flex-col md:flex-row md:items-center gap-2">
        <input v-model="arama" placeholder="E-posta, hedef veya eylem ara…" class="girdi md:max-w-xs">
        <div class="md:w-64"><SearchableSelect v-model="action" :options="eylemler.map((e) => ({ value: e, label: EYLEM[e]?.ad || e, alt: e, badge: e }))" placeholder="Tüm eylemler" size="sm" /></div>
        <label class="flex items-center gap-1.5 text-[11px] text-t-2 cursor-pointer select-none rounded-lg border border-line bg-bg-2 px-2 py-1" title="page.view kayıtlarını göster/gizle">
          <input v-model="sayfaGoruntuleme" type="checkbox" class="accent-indigo-500 h-3 w-3"><FaIcon :icon="sayfaGoruntuleme ? 'eye' : 'eye-slash'" class="h-3 w-3 text-t-3" />Sayfa görüntülemeleri</label>
        <span class="text-[11px] text-t-3 md:ml-auto font-mono">{{ sayi(toplam) }} kayıt</span>
      </div>
      <DataTable :columns="SUTUNLAR" :rows="kayitlar" row-key="id" :loading="yukleniyor" empty-text="Kayıt yok." min-width="min-w-[900px]" dense
        :row-class="(k) => acik === k.id ? 'bg-bg-3/30' : ''">
        <template #cell-created_at="{ value }"><span class="font-mono text-[10.5px] text-t-2">{{ tarih(value) }}</span></template>
        <template #cell-user_email="{ value }"><span class="font-semibold text-t-1">{{ value || 'sistem' }}</span></template>
        <template #cell-action="{ value }"><span class="rounded px-1.5 py-0.5 text-[10px] font-semibold border" :class="EYLEM[value]?.sinif || 'bg-bg-3 text-t-2 border-line'">{{ EYLEM[value]?.ad || value }}</span> <span class="font-mono text-[10px] text-t-muted">{{ value }}</span></template>
        <template #cell-target_label="{ row: k }"><span class="text-t-2"><span v-if="k.target_type" class="text-[10px] text-t-3 font-mono mr-1">{{ k.target_type }}</span>{{ kisalt(k.target_label || k.target_id || '—', 40) }}</span></template>
        <template #cell-detay="{ row: k }">
          <button v-if="k.before || k.after" class="text-[11px] text-indigo-400 hover:text-indigo-300" @click="acik = acik === k.id ? null : k.id">{{ acik === k.id ? 'Gizle' : 'Göster' }}</button>
        </template>
        <template #footer></template>
      </DataTable>
      <div v-if="acik && kayitlar.find((k) => k.id === acik)" class="px-4 py-3 border-t border-line bg-bg-3/30">
        <p class="text-[10px] uppercase tracking-wider text-t-3 mb-2">Kayıt #{{ acik }} · önce → sonra</p>
        <template v-for="k in [kayitlar.find((x) => x.id === acik)]" :key="k.id">
          <div v-if="fark(k).length" class="space-y-1">
            <div v-for="f in fark(k)" :key="f.alan" class="text-[11px] flex flex-wrap items-baseline gap-2">
              <span class="font-mono text-t-3 w-32 shrink-0">{{ f.alan }}</span>
              <span v-if="f.once !== undefined" class="line-through text-rose-400/80 font-mono break-all">{{ typeof f.once === 'object' ? JSON.stringify(f.once) : f.once }}</span>
              <span v-if="f.sonra !== undefined" class="text-emerald-400 font-mono break-all">{{ typeof f.sonra === 'object' ? JSON.stringify(f.sonra) : f.sonra }}</span>
            </div>
          </div>
          <pre v-else class="text-[10.5px] font-mono text-t-2 whitespace-pre-wrap">{{ JSON.stringify(k.after || k.before, null, 1) }}</pre>
        </template>
      </div>
      <div class="p-3 border-t border-line bg-bg-1/80 flex items-center justify-between gap-3">
        <span class="text-[11px] text-t-3">{{ sayi(offset + 1) }}–{{ sayi(Math.min(offset + limit, toplam)) }} / {{ sayi(toplam) }}</span>
        <Sayfalama :toplam="toplam" :limit="limit" :offset="offset" @git="(o) => { offset = o; yukle(); }" />
      </div>
    </div>
  </section>
</template>
