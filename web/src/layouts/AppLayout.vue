<script setup>
// Uygulama kabugu: daraltilabilir sidebar (Font Awesome ikonlu moduller + yonetim),
// ust cubuk, komut paleti, toast.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import { useBildirimStore } from '../stores/bildirim';
import { graf, sistem } from '../api';
import { sayi } from '../utils/format';
import AppHeader from '../components/AppHeader.vue';
import AramaPaleti from '../components/AramaPaleti.vue';
import YuklemeGostergesi from '../components/YuklemeGostergesi.vue';
import Logo from '../components/Logo.vue';

const auth = useAuthStore();
const ui = useUiStore();
const route = useRoute();
const bildirim = useBildirimStore();

// Menü: izin olmayan modül görünmez (backend aynı izni rota başına ayrıca denetler).
// renk: ikon rengi; aktifken kutu indigo'ya döner.
const GRUPLAR = [
  { ad: 'Genel', ikon: 'gauge-high', ogeler: [
    { name: 'panel', ad: 'Panel', ikon: 'gauge-high', renk: 'text-indigo-400', aciklama: 'Genel bakış' },
  ] },
  { ad: 'Modüller', ikon: 'layer-group', ogeler: [
    { name: 'envanter', ad: 'Veri Envanteri', ikon: 'database', renk: 'text-amber-400', aciklama: 'Kişisel veri işleme envanteri', izin: 'inventory.view' },
    { name: 'bulgular', ad: 'Uyum Bulguları', ikon: 'triangle-exclamation', renk: 'text-rose-400', aciklama: 'Kritik / yüksek bulgular', izin: 'findings.view' },
    { name: 'asistan', ad: 'Mevzuat Asistanı', ikon: 'scale-balanced', renk: 'text-indigo-400', aciklama: 'Kaynak dayanaklı sohbet', izin: 'chat.use' },
    { name: 'acik-riza', ad: 'Açık Rıza Kayıtları', ikon: 'clipboard-check', renk: 'text-teal-400', aciklama: 'İlgili kişi rızaları', izin: 'consents.view' },
    { name: 'graf', ad: 'Bilgi Grafiği', ikon: 'diagram-project', renk: 'text-cyan-400', aciklama: 'Madde etkisi, riskli faaliyetler', izin: 'graph.view' },
  ] },
  { ad: 'Uyum Belgeleri', ikon: 'file-signature', ogeler: [
    { name: 'belgeler', ad: 'Kurumsal Belgeler', ikon: 'file-signature', renk: 'text-emerald-400', aciklama: 'Politika, prosedür, form', izin: 'documents.view' },
    { name: 'faaliyet-belgeleri', ad: 'Faaliyet Belgeleri', ikon: 'file-contract', renk: 'text-lime-400', aciklama: 'Aydınlatma & açık rıza · otomatik', izin: 'documents.view' },
  ] },
  { ad: 'Yönetim', ikon: 'shield-halved', ogeler: [
    { name: 'kullanicilar', ad: 'Kullanıcılar', ikon: 'users', renk: 'text-violet-400', aciklama: 'Hesaplar, rol ve birim ataması', izin: 'users.view' },
    { name: 'roller', ad: 'Roller & İzinler', ikon: 'user-shield', renk: 'text-fuchsia-400', aciklama: 'Yetki matrisi ve kapsam', izin: 'roles.view' },
    { name: 'birimler', ad: 'Birimler', ikon: 'sitemap', renk: 'text-sky-400', aciklama: 'Departmanlar ve üyeler', izin: 'departments.view' },
    { name: 'kurum-profili', ad: 'Kurum Profili', ikon: 'building-user', renk: 'text-teal-400', aciklama: 'Veri sorumlusu bilgileri', izin: 'profile.view' },
    { name: 'gunluk', ad: 'Denetim Günlüğü', ikon: 'clock-rotate-left', renk: 'text-orange-400', aciklama: 'Audit trail', izin: 'audit.view' },
  ] },
];
const gruplar = computed(() => GRUPLAR
  .map((g) => ({ ...g, ogeler: g.ogeler.filter((o) => !o.izin || auth.can(o.izin)) }))
  .filter((g) => g.ogeler.length));

const saglik = ref({ ok: null, metin: 'Bağlanıyor…' });
const grafDugum = ref('—');
const aktif = (name) => route.name === name;

onBeforeUnmount(() => bildirim.durdur());
onMounted(async () => {
  bildirim.basla();
  try {
    const h = await sistem.health();
    saglik.value = { ok: true, metin: 'API bağlı' };
  } catch { saglik.value = { ok: false, metin: 'API bağlantısı yok' }; }
  if (auth.can('graph.view')) {
    try { grafDugum.value = sayi((await graf.risk(1)).graf.toplam_dugum); } catch { grafDugum.value = '—'; }
  }
});
</script>

<template>
  <div class="min-h-screen flex">
    <aside class="shrink-0 border-r border-line bg-bg-1 flex flex-col justify-between sticky top-0 h-screen overflow-y-auto overflow-x-hidden custom-scroll transition-[width] duration-200"
      :class="ui.sidebarDar ? 'w-[72px]' : 'w-64'">
      <div :class="ui.sidebarDar ? 'p-2.5' : 'p-4'">
        <!-- marka -->
        <div class="flex items-center gap-3 pb-4 border-b border-line mb-3" :class="ui.sidebarDar ? 'justify-center' : ''">
          <!-- logo: satir ici SVG; karanlik temada beyaz, aydinlik temada mor (style.css --logo-*) -->
          <Logo class="w-9 h-9 shrink-0 select-none" />
          <div v-if="!ui.sidebarDar" class="leading-tight min-w-0">
            <h2 class="text-sm font-bold text-t-1 tracking-wide">KVKK Uyum</h2>
            <p class="text-[11px] text-t-3 font-medium">6698 · Denetim v1.0</p>
          </div>
        </div>

        <!-- gruplar -->
        <nav v-for="g in gruplar" :key="g.ad" class="mb-4" :aria-label="g.ad">
          <div v-if="!ui.sidebarDar" class="flex items-center gap-1.5 px-2 mb-1.5 text-[11px] font-bold uppercase tracking-wider text-t-3">
            <FaIcon :icon="g.ikon" class="h-3 w-3 text-t-muted" /><span>{{ g.ad }}</span>
          </div>
          <div v-else class="mx-2 mb-2 border-t border-line" :title="g.ad"></div>
          <div class="space-y-1">
            <router-link v-for="m in g.ogeler" :key="m.name" :to="{ name: m.name }" custom v-slot="{ navigate }">
              <button @click="navigate" :title="ui.sidebarDar ? m.ad + ' — ' + m.aciklama : m.aciklama"
                class="group relative w-full flex items-center rounded-lg text-[13px] transition-colors"
                :class="[ui.sidebarDar ? 'justify-center px-0 py-2.5' : 'gap-3 pl-2.5 pr-2 py-2',
                         aktif(m.name) ? 'font-bold text-t-1 bg-acc-soft border border-indigo-500/30' : 'font-medium text-t-2 hover:text-t-1 hover:bg-bg-2 border border-transparent']">
                <span v-if="aktif(m.name)" class="absolute left-0 top-2 bottom-2 w-0.5 rounded-r bg-indigo-400"></span>
                <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md transition-colors"
                  :class="aktif(m.name) ? 'bg-indigo-500/20 text-indigo-300' : 'bg-bg-2 group-hover:bg-bg-3 ' + m.renk">
                  <FaIcon :icon="m.ikon" class="h-3.5 w-3.5" fixed-width />
                </span>
                <template v-if="!ui.sidebarDar">
                  <span class="truncate flex-1 text-left">{{ m.ad }}</span>
                  <FaIcon v-if="aktif(m.name)" icon="chevron-right" class="h-2.5 w-2.5 text-indigo-400/70" />
                </template>
              </button>
            </router-link>
          </div>
        </nav>
        <p v-if="!gruplar.some((g) => g.ad === 'Modüller') && !ui.sidebarDar" class="px-2.5 py-2 text-[11px] text-t-3">Hiçbir modül için izniniz yok.</p>

        <!-- kaynak ozeti -->
        <div v-if="!ui.sidebarDar" class="mt-2">
          <div class="flex items-center gap-1.5 px-2 mb-2 text-[11px] font-bold uppercase tracking-wider text-t-3">
            <FaIcon icon="book" class="h-3 w-3 text-t-muted" /><span>Kaynak</span>
          </div>
          <div class="px-2.5 py-2 rounded-lg bg-bg-2 border border-line text-[11px] text-t-2 space-y-1.5">
            <div class="flex items-center justify-between"><span class="flex items-center gap-1.5"><FaIcon icon="book" class="h-3 w-3 text-indigo-400" fixed-width />Mevzuat belgesi</span><span class="font-mono text-t-1">363</span></div>
            <div class="flex items-center justify-between"><span class="flex items-center gap-1.5"><FaIcon icon="cubes" class="h-3 w-3 text-amber-400" fixed-width />Chunk</span><span class="font-mono text-t-1">4.868</span></div>
            <div class="flex items-center justify-between"><span class="flex items-center gap-1.5"><FaIcon icon="circle-nodes" class="h-3 w-3 text-cyan-400" fixed-width />Graf düğümü</span><span class="font-mono text-t-1">{{ grafDugum }}</span></div>
          </div>
        </div>
      </div>

      <!-- alt: durum + daralt -->
      <div :class="ui.sidebarDar ? 'm-2 space-y-2' : 'm-3 space-y-2'">
        <div class="rounded-xl bg-bg-2 border border-line" :class="ui.sidebarDar ? 'p-2 flex justify-center' : 'p-3'" :title="saglik.metin">
          <div class="flex items-center gap-2 text-[11px] min-w-0">
            <span class="relative flex h-2.5 w-2.5 shrink-0">
              <span v-if="saglik.ok" class="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60 animate-ping"></span>
              <span class="relative inline-flex h-2.5 w-2.5 rounded-full" :class="saglik.ok === null ? 'bg-slate-500' : saglik.ok ? 'bg-emerald-500' : 'bg-rose-500'"></span>
            </span>
            <template v-if="!ui.sidebarDar">
              <FaIcon icon="server" class="h-3 w-3 text-t-3 shrink-0" />
              <span class="text-t-2 truncate">{{ saglik.metin }}</span>
            </template>
          </div>
        </div>
        <button class="w-full flex items-center justify-center gap-2 rounded-lg border border-line bg-bg-2 py-1.5 text-[11px] font-semibold text-t-3 hover:text-t-1 hover:bg-bg-3"
          :title="ui.sidebarDar ? 'Menüyü genişlet' : 'Menüyü daralt'" @click="ui.sidebarToggle()">
          <FaIcon :icon="ui.sidebarDar ? 'chevron-right' : 'chevron-left'" class="h-3 w-3" />
          <span v-if="!ui.sidebarDar">Daralt</span>
        </button>
      </div>
    </aside>

    <div class="flex-1 min-w-0 flex flex-col">
      <AppHeader />
      <main class="relative flex-1 min-w-0 p-4 lg:p-6 xl:p-8">
        <YuklemeGostergesi />
        <router-view v-slot="{ Component }">
          <transition name="sayfa" mode="out-in" :duration="{ enter: 180, leave: 100 }">
            <component :is="Component" :key="route.path" />
          </transition>
        </router-view>
      </main>
    </div>

    <AramaPaleti />
  </div>
</template>
