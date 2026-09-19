<script setup>
// Roller & izin matrisi: sol panel rol listesi, sag panel secili rolun modul x aksiyon
// matrisi (CRUD + ozel aksiyonlar) ve kapsam (all/department/assigned/own/none).
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { izinler as izinApi, roller as rolApi } from '../../api';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import Modal from '../../components/Modal.vue';
import Iskelet from '../../components/Iskelet.vue';

const auth = useAuthStore();
const ui = useUiStore();

const MODUL = {
  inventory: { ad: 'Veri Envanteri', aciklama: 'Kişisel veri işleme envanteri satırları', sira: 1 },
  findings: { ad: 'Uyum Bulguları', aciklama: 'Denetim kurallarından türeyen bulgu panosu', sira: 2 },
  documents: { ad: 'Uyum Belgeleri', aciklama: 'Aydınlatma metni, politika, protokol üretimi', sira: 3 },
  consents: { ad: 'Açık Rıza Kayıtları', aciklama: 'İlgili kişi rıza beyanları ve durumları', sira: 4 },
  chat: { ad: 'Mevzuat Asistanı', aciklama: 'RAG tabanlı sohbet', sira: 5 },
  graph: { ad: 'Bilgi Grafiği', aciklama: 'Madde etkisi ve riskli faaliyetler', sira: 6 },
  taxonomy: { ad: 'Taksonomi', aciklama: 'Kanonik listeler', sira: 7 },
  profile: { ad: 'Kurum Profili', aciklama: 'Belge başlık bilgileri', sira: 8 },
  users: { ad: 'Kullanıcılar', aciklama: 'Hesap, rol ve birim ataması', sira: 9 },
  roles: { ad: 'Roller & İzinler', aciklama: 'Yetki matrisi ve kapsam politikaları', sira: 10 },
  departments: { ad: 'Birimler', aciklama: 'Departman tanımları ve üyelikleri', sira: 11 },
  audit: { ad: 'Denetim Günlüğü', aciklama: 'Kimlik ve yönetim işlemleri kaydı', sira: 12 },
};
const CRUD = ['view', 'create', 'update', 'delete'];
const AKSIYON = { view: 'Görüntüle', create: 'Oluştur', update: 'Düzenle', delete: 'Sil', export: 'Dışa aktar', search: 'Anlamsal arama',
  suggest: 'YZ önerisi', history: 'Geçmiş', assign: 'Sorumlu atama', reindex: 'Yeniden indeksle', generate: 'Belge üret', use: 'Kullan' };
const KRITIK = new Set(['inventory.delete', 'inventory.reindex', 'inventory.export', 'users.delete', 'users.create', 'roles.update', 'roles.delete', 'departments.delete', 'consents.delete']);
const KAPSAM_RENK = { all: 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10', department: 'text-sky-300 border-sky-500/30 bg-sky-500/10',
  assigned: 'text-violet-300 border-violet-500/30 bg-violet-500/10', own: 'text-amber-300 border-amber-500/30 bg-amber-500/10', none: 'text-rose-300 border-rose-500/30 bg-rose-500/10' };
const ROL_RENK = ['bg-indigo-500/10 text-indigo-400 border-indigo-500/20', 'bg-blue-500/10 text-blue-400 border-blue-500/20', 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  'bg-amber-500/10 text-amber-400 border-amber-500/20', 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20', 'bg-fuchsia-500/10 text-fuchsia-400 border-fuchsia-500/20', 'bg-red-500/10 text-red-400 border-red-500/20'];

const roller = ref([]);
const kapsamlar = ref([]);
const katalog = ref({});      // {module: [{name, action, description}]}
const kapsamliModuller = ref(new Set());
const seciliId = ref(null);
const yukleniyor = ref(true);
const kaydediyor = ref(false);
const sekme = ref('tum');
const izinAra = ref('');
const acikSatir = reactive({}); // modul -> aksiyon bazli kapsam gorunumu
const modal = ref(null); // {tip: 'yeni'|'klon', name, description}

// Duzenleme tampon
const taslak = reactive({ name: '', description: '', izinler: new Set(), kapsam: {} }); // kapsam: {"module.action": scope}
const orijinal = ref('');

const secili = computed(() => roller.value.find((r) => r.id === seciliId.value) || null);
const moduller = computed(() => Object.keys(katalog.value).sort((a, b) => (MODUL[a]?.sira || 99) - (MODUL[b]?.sira || 99)));
const gorunenModuller = computed(() => {
  const q = izinAra.value.trim().toLocaleLowerCase('tr');
  if (!q) return moduller.value;
  return moduller.value.filter((m) => (MODUL[m]?.ad || m).toLocaleLowerCase('tr').includes(q) || m.includes(q)
    || (katalog.value[m] || []).some((p) => p.name.includes(q) || (AKSIYON[p.action] || '').toLocaleLowerCase('tr').includes(q)));
});
const listelenenRoller = computed(() => roller.value.filter((r) => sekme.value === 'tum' || (sekme.value === 'super' ? r.bypass : !r.bypass)));
const toplamIzin = computed(() => Object.values(katalog.value).reduce((a, l) => a + l.length, 0));
const kritikSayisi = computed(() => Object.values(katalog.value).flat().filter((p) => KRITIK.has(p.name)).length);
const toplamKullanici = computed(() => roller.value.reduce((a, r) => a + (r.user_count || 0), 0));
const kirli = computed(() => JSON.stringify(taslakDurum()) !== orijinal.value);
const duzenlenebilir = computed(() => auth.can('roles.update') && secili.value && (!secili.value.bypass));
const kod = (ad) => 'ROLE_' + ad.toLocaleUpperCase('tr').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^A-Z0-9]+/g, '_').replace(/^_|_$/g, '');

function taslakDurum() {
  return { name: taslak.name, description: taslak.description, izinler: [...taslak.izinler].sort(), kapsam: Object.fromEntries(Object.entries(taslak.kapsam).sort()) };
}
function ozelAksiyonlar(m) { return (katalog.value[m] || []).filter((p) => !CRUD.includes(p.action)); }
function izin(m, a) { return (katalog.value[m] || []).find((p) => p.action === a); }
function var_(m, a) { return taslak.izinler.has(`${m}.${a}`); }
function toggle(m, a) {
  if (!duzenlenebilir.value) return;
  const ad = `${m}.${a}`;
  if (taslak.izinler.has(ad)) { taslak.izinler.delete(ad); delete taslak.kapsam[ad]; }
  else { taslak.izinler.add(ad); if (kapsamliModuller.value.has(m)) taslak.kapsam[ad] = modulKapsami(m) || 'department'; }
}
function modulIzinSayisi(m) { return (katalog.value[m] || []).filter((p) => taslak.izinler.has(p.name)).length; }
function modulToggle(m) {
  if (!duzenlenebilir.value) return;
  const hepsi = (katalog.value[m] || []).every((p) => taslak.izinler.has(p.name));
  (katalog.value[m] || []).forEach((p) => { if (hepsi === taslak.izinler.has(p.name)) toggle(m, p.action); });
}
function modulKapsami(m) {
  // moduldeki verilmis aksiyonlarin kapsami; farkliysa 'karma'
  const k = [...new Set((katalog.value[m] || []).filter((p) => taslak.izinler.has(p.name)).map((p) => taslak.kapsam[p.name] || 'none'))];
  return k.length === 0 ? null : k.length === 1 ? k[0] : 'karma';
}
function modulKapsamAta(m, scope) {
  if (!duzenlenebilir.value || !scope || scope === 'karma') return;
  (katalog.value[m] || []).forEach((p) => { if (taslak.izinler.has(p.name)) taslak.kapsam[p.name] = scope; });
}
function tumunuSec(sec) {
  if (!duzenlenebilir.value) return;
  Object.values(katalog.value).flat().forEach((p) => {
    const [m] = p.name.split('.');
    if (sec && !taslak.izinler.has(p.name)) toggle(m, p.action);
    if (!sec && taslak.izinler.has(p.name)) toggle(m, p.action);
  });
}

function rolYukle(r) {
  seciliId.value = r.id;
  taslak.name = r.name; taslak.description = r.description || '';
  taslak.izinler = new Set(r.permissions || []);
  taslak.kapsam = {};
  Object.entries(r.scopes || {}).forEach(([m, aksiyonlar]) => Object.entries(aksiyonlar).forEach(([a, s]) => { taslak.kapsam[`${m}.${a}`] = s; }));
  // bypass rol: her sey all
  if (r.bypass) { Object.values(katalog.value).flat().forEach((p) => taslak.izinler.add(p.name)); }
  orijinal.value = JSON.stringify(taslakDurum());
}
function geriAl() { if (secili.value) rolYukle(secili.value); }

async function yukle(secilecek = null) {
  yukleniyor.value = true;
  try {
    const [r, i] = await Promise.all([rolApi.liste(), izinApi.liste()]);
    roller.value = r.roller; kapsamlar.value = r.kapsamlar;
    katalog.value = i.izinler;
    const kapsamli = new Set(); r.roller.forEach((x) => Object.keys(x.scopes || {}).forEach((m) => kapsamli.add(m)));
    ['inventory', 'findings', 'documents', 'consents'].forEach((m) => kapsamli.add(m));
    if (r.kapsamli_moduller) r.kapsamli_moduller.forEach((m) => kapsamli.add(m));
    kapsamliModuller.value = kapsamli;
    const hedef = roller.value.find((x) => x.id === (secilecek ?? seciliId.value)) || roller.value.find((x) => !x.bypass) || roller.value[0];
    if (hedef) rolYukle(hedef);
  } catch (e) { ui.bildir('Yüklenemedi: ' + e.message, 'hata'); }
  finally { yukleniyor.value = false; }
}

async function kaydet() {
  if (!secili.value || !kirli.value) return;
  kaydediyor.value = true;
  try {
    const scopes = [...taslak.izinler].filter((ad) => kapsamliModuller.value.has(ad.split('.')[0]))
      .map((ad) => { const [module, action] = ad.split('.'); return { module, action, scope: taslak.kapsam[ad] || 'none' }; });
    await rolApi.guncelle(secili.value.id, { name: taslak.name.trim(), description: taslak.description, permissions: [...taslak.izinler], scopes });
    ui.bildir('Rol izinleri kaydedildi; önbellek sürümü artırıldı.');
    if (auth.roller.includes(secili.value.name)) auth.fetchMe().catch(() => {});
    await yukle(secili.value.id);
  } catch (e) { ui.bildir(e.message, 'hata'); }
  finally { kaydediyor.value = false; }
}
async function modalKaydet() {
  const m = modal.value;
  if (!m.name.trim()) { m.hata = 'Rol adı zorunludur.'; return; }
  try {
    const d = m.tip === 'klon' ? await rolApi.klonla(secili.value.id, m.name.trim()) : await rolApi.olustur({ name: m.name.trim(), description: m.description || null, permissions: [], scopes: [] });
    ui.bildir(m.tip === 'klon' ? 'Rol klonlandı.' : 'Rol oluşturuldu.');
    modal.value = null; await yukle(d.rol.id);
  } catch (e) { m.hata = e.message; }
}
async function rolSec(r) {
  if (kirli.value && !(await ui.onay({ baslik: 'Kaydedilmemiş değişiklikler', tur: 'uyari', onayMetni: 'Devam et', iptalMetni: 'Kal',
    metin: 'Bu roldeki izin/kapsam değişiklikleri kaydedilmedi. Başka role geçince kaybolacak.' }))) return;
  rolYukle(r);
}
async function sil() {
  const r = secili.value;
  if (!r) return;
  const onay = await ui.onay({ baslik: `"${r.name}" rolü silinsin mi?`, tur: 'hata', onayMetni: 'Evet, sil',
    metin: 'Rolün izin ve kapsam tanımları kaldırılır.', detay: 'Kullanıcısı olan roller silinemez; önce kullanıcılardan kaldırın.' });
  if (!onay) return;
  try { await rolApi.sil(r.id); ui.bildir('Rol silindi.'); seciliId.value = null; await yukle(); }
  catch (e) { ui.bildir(e.message, 'hata'); }
}

watch(seciliId, () => { Object.keys(acikSatir).forEach((k) => delete acikSatir[k]); });
onMounted(() => yukle());
</script>

<template>
  <section class="space-y-6 max-w-[1780px] mx-auto">
    <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-2xl font-extrabold text-t-1 tracking-tight">Roller & Yetkilendirme</h1>
          <span class="rounded bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-400 border border-indigo-500/20">RBAC v2</span>
          <span class="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">İzin + Kapsam</span>
        </div>
        <p class="text-xs text-t-2 mt-1">Rol tabanlı erişim (<span class="font-mono">modul.aksiyon</span>) ve granüler veri kapsamı matrisi. Değişiklikler kaydedilince önbellek sürümü artar, anında geçerli olur.</p>
      </div>
    </div>

    <!-- KPI -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="rounded-xl border border-line bg-bg-card p-4">
        <div class="flex items-center justify-between mb-2"><span class="text-xs font-semibold uppercase tracking-wider text-t-3">Tanımlı Rol</span><span class="rounded bg-indigo-500/10 px-2 py-0.5 text-[11px] font-medium text-indigo-400">{{ roller.filter((r) => r.bypass).length }} süper yetki</span></div>
        <div class="text-2xl font-bold text-t-1 tracking-tight">{{ roller.length }} Rol</div>
        <div class="mt-2 text-xs text-t-3"><span class="text-emerald-400 font-medium">● {{ roller.filter((r) => !r.bypass).length }} kapsam denetimli</span></div>
      </div>
      <div class="rounded-xl border border-line bg-bg-card p-4">
        <div class="flex items-center justify-between mb-2"><span class="text-xs font-semibold uppercase tracking-wider text-t-3">Rol Ataması</span><span class="rounded bg-purple-500/10 px-2 py-0.5 text-[11px] font-medium text-purple-400">kullanıcı × rol</span></div>
        <div class="text-2xl font-bold text-t-1 tracking-tight">{{ toplamKullanici }} Atama</div>
        <div class="mt-2 text-xs text-t-3">Çoklu rolde en geniş kapsam kazanır</div>
      </div>
      <div class="rounded-xl border border-line bg-bg-card p-4">
        <div class="flex items-center justify-between mb-2"><span class="text-xs font-semibold uppercase tracking-wider text-t-3">Granüler İzin</span><span class="rounded bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-400">CRUD + özel</span></div>
        <div class="text-2xl font-bold text-t-1 tracking-tight">{{ toplamIzin }} Yetki</div>
        <div class="mt-2 text-xs text-t-3"><span class="text-amber-400 font-medium">{{ kritikSayisi }} kritik izin</span> (silme, dışa aktarım, yönetim)</div>
      </div>
      <div class="rounded-xl border border-line bg-bg-card p-4">
        <div class="flex items-center justify-between mb-2"><span class="text-xs font-semibold uppercase tracking-wider text-t-3">Veri İzolasyonu</span><span class="rounded bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-400">{{ kapsamliModuller.size }} modül</span></div>
        <div class="text-2xl font-bold text-emerald-400 tracking-tight">5 Kapsam Seviyesi</div>
        <div class="mt-2 text-xs text-t-3 font-mono">all › department › assigned › own › none</div>
      </div>
    </div>

    <div class="grid grid-cols-12 gap-6 items-start">
      <!-- SOL: roller -->
      <div class="col-span-12 lg:col-span-4 space-y-4">
        <div class="rounded-xl border border-line bg-bg-card overflow-hidden">
          <div class="border-b border-line bg-bg-1/70 px-4 py-3.5 flex items-center justify-between">
            <div><h2 class="text-xs font-bold uppercase tracking-wider text-t-1">Roller & Yetki Profilleri</h2><p class="text-[11px] text-t-3">Düzenlemek için rol seçin</p></div>
            <button v-if="auth.can('roles.create')" class="flex items-center gap-1 rounded-md bg-indigo-600/90 hover:bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white" @click="modal = { tip: 'yeni', name: '', description: '' }"><FaIcon icon="plus" class="h-3 w-3" />Yeni Rol</button>
          </div>
          <div class="flex border-b border-line-60 bg-bg-2/50 px-3 pt-2 text-xs">
            <button v-for="s in [['tum', 'Tüm Roller', roller.length], ['super', 'Süper Yetki', roller.filter((r) => r.bypass).length], ['normal', 'Kapsam Denetimli', roller.filter((r) => !r.bypass).length]]" :key="s[0]"
              class="border-b-2 px-3 pb-2" :class="sekme === s[0] ? 'border-indigo-500 font-semibold text-indigo-400' : 'border-transparent text-t-3 hover:text-t-1'" @click="sekme = s[0]">{{ s[1] }} ({{ s[2] }})</button>
          </div>
          <div class="p-2 space-y-1.5 max-h-[620px] overflow-y-auto custom-scroll">
            <template v-if="yukleniyor"><div v-for="i in 5" :key="i" class="rounded-lg border border-line bg-bg-2/60 p-3.5 space-y-2" aria-busy="true"><div class="flex items-center gap-2.5"><Iskelet class="h-8 w-8" /><div class="flex-1 space-y-1.5"><Iskelet class="h-3 w-1/2" /><Iskelet class="h-2.5 w-3/4" /></div></div><Iskelet class="h-2.5 w-1/3" /></div></template>
            <div v-for="(r, i) in listelenenRoller" :key="r.id" @click="rolSec(r)"
              class="group relative rounded-lg border p-3.5 transition-all cursor-pointer"
              :class="r.id === seciliId ? 'border-indigo-500/40 bg-indigo-500/10' : 'border-line bg-bg-2/60 hover:border-line-bright hover:bg-bg-hover'">
              <div class="flex items-start justify-between gap-2">
                <div class="flex items-center gap-2.5 min-w-0">
                  <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold border" :class="r.bypass ? 'bg-indigo-600 text-white border-indigo-500 shadow-md shadow-indigo-600/30' : ROL_RENK[i % ROL_RENK.length]">{{ r.name.slice(0, 2).toLocaleUpperCase('tr') }}</div>
                  <div class="min-w-0">
                    <div class="flex items-center gap-1.5 flex-wrap"><h3 class="text-xs font-bold text-t-1">{{ r.name }}</h3>
                      <span v-if="r.bypass" class="rounded bg-indigo-500/20 px-1.5 py-0.5 text-[9.5px] font-semibold text-indigo-300">Süper Yetki</span>
                      <span v-else-if="!r.permissions?.length" class="rounded bg-bg-3 px-1.5 py-0.5 text-[9.5px] font-semibold text-t-3">Boş</span></div>
                    <p class="text-[11px] text-t-3 line-clamp-2">{{ r.description || '—' }}</p>
                  </div>
                </div>
                <span class="rounded-full px-2 py-0.5 text-[10px] font-mono shrink-0" :class="r.id === seciliId ? 'bg-indigo-400/10 text-indigo-300' : 'bg-line text-t-2'">{{ r.user_count }} kullanıcı</span>
              </div>
              <div class="mt-3 flex items-center justify-between text-[11px] pt-2 border-t" :class="r.id === seciliId ? 'border-indigo-500/20' : 'border-line-60'">
                <span class="text-t-3 font-mono truncate">{{ kod(r.name) }}</span>
                <span class="font-medium shrink-0" :class="r.bypass ? 'text-emerald-400' : 'text-indigo-300'">{{ r.bypass ? toplamIzin + ' / ' + toplamIzin : r.permissions?.length + ' / ' + toplamIzin }} izin</span>
              </div>
            </div>
          </div>
          <div v-if="secili" class="border-t border-line bg-bg-1/80 p-3 flex items-center justify-between text-xs">
            <button v-if="auth.can('roles.create') && !secili.bypass" class="text-t-3 hover:text-indigo-400 flex items-center gap-1" @click="modal = { tip: 'klon', name: secili.name + ' (Kopya)' }"><FaIcon icon="clone" class="h-3 w-3" />Rolü Klonla</button>
            <span v-else></span>
            <button v-if="auth.can('roles.delete') && !secili.bypass" class="text-t-3 hover:text-rose-400 flex items-center gap-1" @click="sil"><FaIcon icon="trash" class="h-3 w-3" />Sil</button>
          </div>
        </div>

        <div class="rounded-xl border border-line bg-bg-card p-4">
          <h3 class="text-xs font-bold uppercase tracking-wider text-t-1 mb-2">Kapsam Seviyeleri</h3>
          <div class="space-y-1.5 text-xs">
            <div v-for="k in kapsamlar" :key="k.ad" class="flex items-center justify-between p-2 rounded-lg bg-bg-2 border border-line-60">
              <span class="flex items-center gap-2"><span class="rounded px-1.5 py-0.5 text-[10px] font-mono font-semibold border" :class="KAPSAM_RENK[k.ad]">{{ k.ad }}</span><span class="text-t-2 text-[11px]">{{ k.aciklama }}</span></span>
              <span class="text-[10.5px] font-mono text-t-3">{{ k.oncelik }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- SAG: matris -->
      <div class="col-span-12 lg:col-span-8 space-y-4">
        <div v-if="secili" class="rounded-xl border border-line bg-bg-card p-4">
          <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div class="flex items-start gap-3 min-w-0 flex-1">
              <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white font-bold shadow-lg shadow-indigo-600/30">{{ taslak.name.slice(0, 2).toLocaleUpperCase('tr') }}</div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2 flex-wrap">
                  <input v-if="duzenlenebilir" v-model="taslak.name" class="girdi !w-auto min-w-[220px] !text-base !font-bold !py-1">
                  <h2 v-else class="text-base font-bold text-t-1">{{ taslak.name }}</h2>
                  <span class="rounded bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-400 border border-emerald-500/20">{{ secili.bypass ? 'Kapsam Atlar' : 'Aktif Rol' }}</span>
                  <span class="rounded bg-indigo-500/10 px-2 py-0.5 text-[11px] font-mono text-indigo-300">ID: ROL-{{ String(secili.id).padStart(2, '0') }}</span>
                </div>
                <input v-if="duzenlenebilir" v-model="taslak.description" placeholder="Rol açıklaması" class="girdi mt-2 !bg-transparent !border-dashed">
                <p v-else class="text-xs text-t-3 mt-1">{{ secili.bypass ? 'Superadmin ve Admin kapsam kontrolünü atlar; tüm izinlere doğrudan sahiptir, izin/kapsam düzenlenmez.' : (taslak.description || '—') }}</p>
              </div>
            </div>
            <div v-if="duzenlenebilir" class="flex items-center gap-2 self-end sm:self-auto shrink-0">
              <button class="flex items-center gap-1.5 rounded-lg border border-line bg-bg-2 px-3 py-1.5 text-xs font-medium text-t-2 hover:text-t-1 hover:bg-bg-3 disabled:opacity-50" :disabled="!kirli" @click="geriAl"><FaIcon icon="rotate-left" class="h-3 w-3" />Geri Al</button>
              <button class="rounded-lg bg-indigo-600 hover:bg-indigo-500 px-4 py-1.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 disabled:opacity-50 flex items-center gap-1.5" :disabled="!kirli || kaydediyor" @click="kaydet">
                <FaIcon :icon="kaydediyor ? 'spinner' : kirli ? 'floppy-disk' : 'check'" class="h-3 w-3" :class="kaydediyor ? 'animate-spin' : ''" /><span>{{ kaydediyor ? 'Kaydediliyor…' : (kirli ? 'İzinleri Kaydet' : 'Kaydedildi') }}</span></button>
            </div>
          </div>
          <div v-if="kirli" class="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-300">Kaydedilmemiş değişiklikler var. Kaydedince bu roldeki kullanıcıların yetkileri anında değişir.</div>
        </div>

        <div v-if="secili" class="rounded-xl border border-line bg-bg-card overflow-hidden">
          <div class="border-b border-line bg-bg-1/80 px-4 py-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div class="flex items-center gap-3">
              <h3 class="text-xs font-bold uppercase tracking-wider text-t-1">Yetki Matrisi (CRUD + Özel Aksiyonlar)</h3>
              <span class="rounded bg-line px-2 py-0.5 text-[10px] text-t-2 font-mono">{{ moduller.length }} modül / {{ toplamIzin }} yetki</span>
            </div>
            <div class="flex items-center gap-2 text-xs">
              <template v-if="duzenlenebilir">
                <button class="text-[11px] font-medium text-indigo-400 hover:text-indigo-300" @click="tumunuSec(true)">Tümünü Seç</button>
                <span class="text-t-muted">|</span>
                <button class="text-[11px] font-medium text-t-3 hover:text-t-2" @click="tumunuSec(false)">Temizle</button>
                <div class="h-4 w-px bg-line"></div>
              </template>
              <input v-model="izinAra" placeholder="İzin adı filtrele…" class="girdi !w-40 !py-1">
            </div>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs border-collapse min-w-[860px]">
              <thead>
                <tr class="border-b border-line bg-bg-2/80 text-[11px] font-semibold uppercase tracking-wider text-t-3">
                  <th class="py-3 px-4 w-[260px]">Modül & İzin Kapsamı</th>
                  <th v-for="a in CRUD" :key="a" class="py-3 px-2 text-center w-16">{{ AKSIYON[a] }}<br><span class="text-[9px] text-t-muted lowercase font-normal">({{ a }})</span></th>
                  <th class="py-3 px-3 text-left">Özel Aksiyonlar<br><span class="text-[9px] text-amber-400/80 lowercase font-normal">(kritik izinler işaretli)</span></th>
                  <th class="py-3 px-3 text-left w-44">Veri Kapsamı<br><span class="text-[9px] text-t-muted lowercase font-normal">(hangi kayıtlar?)</span></th>
                </tr>
              </thead>
              <tbody class="divide-y divide-line-60">
                <template v-for="m in gorunenModuller" :key="m">
                  <tr class="hover:bg-bg-hover/60 transition-colors" :class="modulIzinSayisi(m) ? '' : 'opacity-70'">
                    <td class="py-3 px-4">
                      <div class="flex items-center gap-2">
                        <input type="checkbox" :checked="modulIzinSayisi(m) === (katalog[m] || []).length" :indeterminate.prop="modulIzinSayisi(m) > 0 && modulIzinSayisi(m) < (katalog[m] || []).length" :disabled="!duzenlenebilir" @change="modulToggle(m)" class="h-4 w-4 rounded border-line bg-bg-3 text-indigo-600 focus:ring-0" title="Modülün tüm izinleri">
                        <div><div class="font-semibold text-t-1">{{ MODUL[m]?.ad || m }} <span class="font-mono text-[10px] text-t-muted">{{ m }}.*</span></div>
                          <div class="text-[11px] text-t-3">{{ MODUL[m]?.aciklama }}</div></div>
                      </div>
                    </td>
                    <td v-for="a in CRUD" :key="a" class="py-3 px-2 text-center" :class="izin(m, a) ? '' : 'opacity-30'">
                      <input v-if="izin(m, a)" type="checkbox" :checked="var_(m, a)" :disabled="!duzenlenebilir" @change="toggle(m, a)" class="h-4 w-4 rounded border-line bg-bg-3 text-indigo-600 focus:ring-0" :title="izin(m, a).description">
                      <span v-else class="text-t-muted">—</span>
                    </td>
                    <td class="py-3 px-3">
                      <div class="flex flex-wrap gap-1">
                        <button v-for="p in ozelAksiyonlar(m)" :key="p.name" type="button" :disabled="!duzenlenebilir" :title="p.description" @click="toggle(m, p.action)"
                          class="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold border transition-colors"
                          :class="var_(m, p.action) ? (KRITIK.has(p.name) ? 'bg-amber-500/15 text-amber-300 border-amber-500/30' : 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30') : 'bg-bg-3 text-t-3 border-line hover:text-t-1'">
                          <span>{{ var_(m, p.action) ? '✓' : '+' }}</span>{{ AKSIYON[p.action] || p.action }}
                        </button>
                        <span v-if="!ozelAksiyonlar(m).length" class="text-[10.5px] text-t-muted">—</span>
                      </div>
                    </td>
                    <td class="py-3 px-3">
                      <template v-if="kapsamliModuller.has(m)">
                        <div v-if="modulIzinSayisi(m)" class="flex items-center gap-1.5">
                          <select :value="modulKapsami(m)" :disabled="!duzenlenebilir" @change="modulKapsamAta(m, $event.target.value)"
                            class="rounded border px-2 py-1 text-[11px] font-mono font-semibold focus:outline-none bg-bg-2" :class="KAPSAM_RENK[modulKapsami(m)] || 'text-t-2 border-line'">
                            <option v-if="modulKapsami(m) === 'karma'" value="karma">karma</option>
                            <option v-for="k in kapsamlar" :key="k.ad" :value="k.ad">{{ k.ad }}</option>
                          </select>
                          <button type="button" class="text-[10px] text-t-3 hover:text-t-1" :title="acikSatir[m] ? 'Aksiyon bazlı görünümü kapat' : 'Aksiyon bazlı kapsam'" @click="acikSatir[m] = !acikSatir[m]">{{ acikSatir[m] ? '▴' : '▾' }}</button>
                        </div>
                        <span v-else class="text-[10.5px] text-t-muted">izin yok</span>
                      </template>
                      <span v-else class="rounded bg-line-60 px-2 py-0.5 text-[10.5px] font-mono text-t-2">kapsam uygulanmaz</span>
                    </td>
                  </tr>
                  <tr v-if="acikSatir[m] && kapsamliModuller.has(m)" class="bg-bg-3/30">
                    <td colspan="7" class="px-4 py-2">
                      <div class="flex flex-wrap gap-2">
                        <label v-for="p in (katalog[m] || []).filter((p) => taslak.izinler.has(p.name))" :key="p.name" class="flex items-center gap-1.5 text-[10.5px] text-t-2">
                          <span class="font-mono">{{ p.action }}</span>
                          <select v-model="taslak.kapsam[p.name]" :disabled="!duzenlenebilir" class="rounded border px-1.5 py-0.5 text-[10.5px] font-mono bg-bg-2" :class="KAPSAM_RENK[taslak.kapsam[p.name]] || 'text-t-2 border-line'">
                            <option v-for="k in kapsamlar" :key="k.ad" :value="k.ad">{{ k.ad }}</option>
                          </select>
                        </label>
                      </div>
                    </td>
                  </tr>
                </template>
                <tr v-if="!gorunenModuller.length"><td colspan="7" class="py-8 text-center text-t-3">Filtreye uyan modül yok.</td></tr>
              </tbody>
            </table>
          </div>

          <div class="border-t border-line bg-bg-1/90 px-4 py-3 flex flex-wrap items-center justify-between gap-4 text-xs">
            <div class="flex flex-wrap items-center gap-4 text-[11px]">
              <span class="text-t-3 font-medium">Açıklama:</span>
              <span class="flex items-center gap-1 text-t-2"><span class="h-2 w-2 rounded-full bg-indigo-500"></span> İzin verildi</span>
              <span class="flex items-center gap-1 text-t-2"><span class="h-2 w-2 rounded-full bg-amber-500"></span> Kritik izin</span>
              <span class="flex items-center gap-1 text-t-2"><span class="h-2 w-2 rounded-full bg-emerald-500"></span> all: tüm kayıtlar</span>
              <span class="flex items-center gap-1 text-t-3"><span class="h-2 w-2 rounded-full bg-bg-3 border border-line"></span> — : bu modülde tanımsız</span>
            </div>
            <span class="text-[10.5px] text-t-3 font-mono">{{ taslak.izinler.size }} izin seçili</span>
          </div>
        </div>

        <div class="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
          <div class="flex items-start gap-3">
            <div class="flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30 font-bold">!</div>
            <div class="flex-1">
              <div class="flex items-center justify-between"><h4 class="text-xs font-bold text-amber-300">Çakışma Çözümü ve Bypass Kuralı</h4><span class="text-[10px] font-mono text-amber-400/80">KURAL: SCOPE-PRIORITY</span></div>
              <p class="text-xs text-t-2 mt-1 leading-relaxed">Bir kullanıcı birden fazla role sahipse aynı <span class="font-mono">modul.aksiyon</span> için rollerin tanımladığı <strong class="text-amber-300">en geniş kapsam</strong> (all 5 › department 4 › assigned 3 › own 2 › none 1) uygulanır. <strong>Superadmin</strong> ve <strong>Admin</strong> kapsam kontrolünü atlar. Kapsam tanımlanmamış izin <span class="font-mono">none</span> sayılır.</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <Modal v-if="modal" :baslik="modal.tip === 'klon' ? 'Rolü Klonla' : 'Yeni Rol'" :alt-baslik="modal.tip === 'klon' ? `${secili?.name} rolünün izin ve kapsamları kopyalanır` : 'Boş rol oluşturulur; izinler matristen verilir'" genislik="max-w-md" @kapat="modal = null">
      <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Rol adı</label>
      <input v-model="modal.name" class="girdi mb-3" @keydown.enter="modalKaydet">
      <template v-if="modal.tip === 'yeni'">
        <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Açıklama</label>
        <input v-model="modal.description" class="girdi">
      </template>
      <p v-if="modal.hata" class="text-[11px] text-rose-400 mt-2">{{ modal.hata }}</p>
      <template #alt>
        <span></span>
        <div class="flex gap-2">
          <button class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-bg-3 border border-line text-t-2 hover:text-t-1" @click="modal = null"><FaIcon icon="xmark" class="h-3 w-3" />Vazgeç</button>
          <button class="px-5 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white" @click="modalKaydet"><FaIcon :icon="modal.tip === 'klon' ? 'clone' : 'plus'" class="h-3 w-3 mr-1.5" />{{ modal.tip === 'klon' ? 'Klonla' : 'Oluştur' }}</button>
        </div>
      </template>
    </Modal>
  </section>
</template>
