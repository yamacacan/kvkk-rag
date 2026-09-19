<script setup>
// Faaliyet belgeleri: envanterdeki her faaliyet icin Aydinlatma Metni + Acik Riza Beyani.
// Envanter ya da kurum profili degisince ilgili belgeler kuyrukta otomatik yenilenir
// (durum: kuyrukta -> uretiliyor -> guncel; eski = yeniden uretim bekliyor). Bekleyen is
// varken tablo 4 sn'de bir tazelenir.
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import { faaliyetBelgeleri as api } from '../api';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import { goreliZaman, kisalt, sayi, tarih } from '../utils/format';
import DataTable from '../components/DataTable.vue';
import SearchableSelect from '../components/SearchableSelect.vue';
import Rozet from '../components/Rozet.vue';
import KpiCard from '../components/KpiCard.vue';

const auth = useAuthStore();
const ui = useUiStore();
const route = useRoute();

const DURUM = {
  guncel: { ad: 'Güncel', tur: 'ok', ikon: 'file-circle-check' },
  eski: { ad: 'Yenileniyor', tur: 'uyari', ikon: 'file-circle-exclamation' },
  kuyrukta: { ad: 'Kuyrukta', tur: 'notr', ikon: 'hourglass-half' },
  uretiliyor: { ad: 'Üretiliyor', tur: 'bilgi', ikon: 'spinner' },
  hata: { ad: 'Hata', tur: 'kritik', ikon: 'file-circle-xmark' },
};
const SUTUNLAR = [
  { key: 'faaliyet', label: 'Faaliyet', sortable: true },
  { key: 'birim', label: 'Birim', width: 'w-48', sortable: true },
  { key: 'satir', label: 'Kayıt', width: 'w-20', align: 'right', sortable: true },
  { key: 'aydinlatma', label: 'Aydınlatma Metni', width: 'w-56' },
  { key: 'acik_riza', label: 'Açık Rıza Beyanı', width: 'w-56' },
  { key: 'islem', label: '', width: 'w-24', align: 'right' },
];

const faaliyetler = ref([]);
const ozet = ref({ faaliyet: 0, guncel: 0, eski: 0, kuyrukta: 0, hata: 0, bekleyen: 0 });
const sablonlar = ref({});
const yukleniyor = ref(false);
const yenileniyor = reactive({});
const indiriliyor = reactive({});
const arama = ref('');
const birim = ref('');
const durumFiltre = ref('');
const vurgulu = ref(route.query.faaliyet || '');
let yoklayici = null;

const birimSecenek = computed(() => [...new Set(faaliyetler.value.map((f) => f.birim).filter(Boolean))].sort().map((b) => ({ value: b, label: b })));
const DURUM_SECENEK = Object.entries(DURUM).map(([k, v]) => ({ value: k, label: v.ad }));
const satirlar = computed(() => faaliyetler.value.filter((f) => {
  if (birim.value && f.birim !== birim.value) return false;
  if (durumFiltre.value && !Object.values(f.belgeler).some((b) => b?.durum === durumFiltre.value)) return false;
  if (arama.value && !f.faaliyet.toLocaleLowerCase('tr').includes(arama.value.toLocaleLowerCase('tr'))) return false;
  return true;
}));
const uretebilir = computed(() => auth.can('documents.generate'));

async function yukle(sessiz = false) {
  if (!sessiz) yukleniyor.value = true;
  try {
    const d = await api.liste();
    faaliyetler.value = d.faaliyetler; ozet.value = d.ozet; sablonlar.value = d.sablonlar;
  } catch (e) { if (!sessiz) ui.hata('Faaliyet belgeleri yüklenemedi', e.message); }
  finally { yukleniyor.value = false; }
  clearInterval(yoklayici); yoklayici = null;
  if (ozet.value.bekleyen > 0 || ozet.value.eski > 0) yoklayici = setInterval(() => yukle(true), 4000);
}
async function yenile(faaliyet = null) {
  const k = faaliyet || '*';
  yenileniyor[k] = true;
  try {
    const d = await api.yenile(faaliyet);
    ui.bildir(faaliyet ? `"${kisalt(faaliyet, 40)}" belgeleri kuyruğa alındı.` : `${d.hedef} için ${d.kuyruga_alinan} iş kuyruğa alındı.`, 'bilgi');
    await yukle(true);
  } catch (e) { ui.hata('Yenilenemedi', e.message); }
  finally { delete yenileniyor[k]; }
}
async function indir(b) {
  indiriliyor[b.id] = true;
  try { await api.indir(b.id, b.ad); } catch (e) { ui.hata('İndirilemedi', e.message); }
  finally { delete indiriliyor[b.id]; }
}
onMounted(yukle);
onBeforeUnmount(() => clearInterval(yoklayici));
</script>

<template>
  <section class="space-y-5 max-w-[1780px] mx-auto">
    <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
      <div>
        <h1 class="text-2xl font-extrabold text-t-1 tracking-tight sm:text-3xl flex items-center gap-2.5"><FaIcon icon="file-contract" class="h-5 w-5 text-lime-400" />Faaliyet Belgeleri</h1>
        <p class="text-xs text-t-2 mt-1">Her işleme faaliyeti için Aydınlatma Metni (KVKK m.10) ve Açık Rıza Beyanı envanterden üretilir; envanter veya kurum profili değişince ilgili belgeler arka planda <span class="text-t-1 font-semibold">otomatik yenilenir</span>.</p>
      </div>
      <button v-if="uretebilir" class="flex items-center gap-1.5 rounded-lg border border-line bg-bg-2 px-3.5 py-1.5 text-xs font-medium text-t-2 hover:text-t-1 hover:bg-bg-3 disabled:opacity-60" :disabled="!!yenileniyor['*']" @click="yenile()">
        <FaIcon icon="arrows-rotate" class="h-3 w-3" :class="yenileniyor['*'] ? 'animate-spin' : ''" />Tümünü yeniden üret</button>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard baslik="Faaliyet" :deger="sayi(ozet.faaliyet)" alt="kapsamınızdaki işleme faaliyeti" renk="indigo" />
      <KpiCard baslik="Güncel Belge" :deger="sayi(ozet.guncel)" :alt="`${sayi(ozet.faaliyet * 2)} belgeden`" renk="emerald" />
      <KpiCard baslik="Yenilenen" :deger="sayi(ozet.eski + ozet.kuyrukta)" alt="kuyrukta / üretiliyor" renk="amber" :rozet="ozet.bekleyen ? 'sürüyor' : ''" />
      <KpiCard baslik="Hatalı" :deger="sayi(ozet.hata)" alt="üretilemeyen belge" :renk="ozet.hata ? 'rose' : 'emerald'" />
    </div>

    <div class="rounded-xl border border-line bg-bg-card overflow-hidden">
      <div class="border-b border-line bg-bg-1/80 px-4 py-3 flex flex-col md:flex-row md:items-center gap-2">
        <input v-model="arama" placeholder="Faaliyet ara…" class="girdi md:max-w-xs">
        <div class="md:w-56"><SearchableSelect v-model="birim" :options="birimSecenek" placeholder="Tüm birimler" size="sm" /></div>
        <div class="md:w-44"><SearchableSelect v-model="durumFiltre" :options="DURUM_SECENEK" placeholder="Tüm durumlar" size="sm" /></div>
        <span class="text-[11px] text-t-3 md:ml-auto font-mono flex items-center gap-2">{{ sayi(satirlar.length) }} faaliyet
          <button class="text-t-2 hover:text-t-1" title="Yenile" @click="yukle()"><FaIcon icon="rotate" class="h-3 w-3" :class="yukleniyor ? 'animate-spin' : ''" /></button></span>
      </div>
      <DataTable :columns="SUTUNLAR" :rows="satirlar" row-key="faaliyet" :loading="yukleniyor" empty-text="Kapsamınızda faaliyet yok." min-width="min-w-[980px]" dense :show-count="false"
        :row-class="(r) => r.faaliyet === vurgulu ? 'bg-indigo-500/10' : ''">
        <template #cell-faaliyet="{ row }"><span class="text-xs font-semibold text-t-1">{{ row.faaliyet }}</span><span v-if="row.bulgu" class="ml-2 text-[10px] font-mono text-rose-400">{{ row.bulgu }} bulgu</span></template>
        <template #cell-birim="{ value }"><span class="text-[11px] text-t-2">{{ value || '—' }}</span></template>
        <template #cell-satir="{ value }"><span class="font-mono text-[11px] text-t-2">{{ sayi(value) }}</span></template>
        <template v-for="s in ['aydinlatma', 'acik_riza']" :key="s" #[`cell-${s}`]="{ row }">
          <div v-if="row.belgeler[s]" class="flex items-center gap-2">
            <Rozet :tur="DURUM[row.belgeler[s].durum]?.tur || 'notr'" boyut="xs" sekil="rounded" :nokta="row.belgeler[s].durum === 'kuyrukta'" :nabiz="row.belgeler[s].durum === 'kuyrukta'">
              <FaIcon :icon="DURUM[row.belgeler[s].durum]?.ikon || 'circle-info'" class="h-2.5 w-2.5" :class="row.belgeler[s].durum === 'uretiliyor' ? 'animate-spin' : ''" />{{ DURUM[row.belgeler[s].durum]?.ad || row.belgeler[s].durum }}</Rozet>
            <button v-if="row.belgeler[s].indirilebilir" class="flex h-7 w-7 items-center justify-center rounded-md border border-line text-t-2 hover:text-indigo-400 hover:border-indigo-500/40 disabled:opacity-50" :title="`İndir · ${row.belgeler[s].son_uretim ? tarih(row.belgeler[s].son_uretim) : ''}`" :disabled="!!indiriliyor[row.belgeler[s].id]" @click="indir(row.belgeler[s])">
              <FaIcon :icon="indiriliyor[row.belgeler[s].id] ? 'spinner' : 'download'" class="h-3 w-3" :class="indiriliyor[row.belgeler[s].id] ? 'animate-spin' : ''" /></button>
            <span v-if="row.belgeler[s].son_uretim" class="text-[10px] font-mono text-t-muted" :title="tarih(row.belgeler[s].son_uretim)">{{ goreliZaman(row.belgeler[s].son_uretim) }}</span>
            <span v-if="row.belgeler[s].durum === 'hata'" class="text-[10px] text-rose-400 truncate max-w-[140px]" :title="row.belgeler[s].hata">{{ kisalt(row.belgeler[s].hata, 30) }}</span>
          </div>
          <span v-else class="text-[10px] text-t-3">—</span>
        </template>
        <template #cell-islem="{ row }">
          <button v-if="uretebilir" class="flex h-7 w-7 items-center justify-center rounded-md border border-line text-t-2 hover:text-t-1 disabled:opacity-50 ml-auto" title="Bu faaliyetin belgelerini yeniden üret" :disabled="!!yenileniyor[row.faaliyet]" @click="yenile(row.faaliyet)">
            <FaIcon icon="arrows-rotate" class="h-3 w-3" :class="yenileniyor[row.faaliyet] ? 'animate-spin' : ''" /></button>
        </template>
      </DataTable>
    </div>
  </section>
</template>
