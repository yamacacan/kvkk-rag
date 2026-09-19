<script setup>
// Birimler (departmanlar): liste, olusturma/duzenleme, uye (kullanici) atama.
// Kullanici <-> birim iliskisi department kapsaminin dayanagidir.
import { computed, onMounted, ref } from 'vue';
import { birimler as birimApi, kullanicilar as kullaniciApi } from '../../api';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import Modal from '../../components/Modal.vue';
import DataTable from '../../components/DataTable.vue';
import Iskelet from '../../components/Iskelet.vue';

const UYE_SUTUNLARI = [
  { key: 'name', label: 'Üye', sortable: true },
  { key: 'email', label: 'E-posta', sortable: true },
  { key: 'roles', label: 'Roller' },
];

const auth = useAuthStore();
const ui = useUiStore();

const liste = ref([]);
const kullanicilar = ref([]);
const yukleniyor = ref(true);
const arama = ref('');
const secili = ref(null); // detay (departman + users)
const form = ref(null);
const formHata = ref('');
const kaydediyor = ref(false);
const uyeAra = ref('');
const RENK = ['bg-indigo-500', 'bg-emerald-500', 'bg-amber-500', 'bg-sky-500', 'bg-fuchsia-500', 'bg-rose-500', 'bg-cyan-500', 'bg-violet-500'];

const filtreli = computed(() => {
  const q = arama.value.trim().toLocaleLowerCase('tr');
  return liste.value.filter((b) => !q || b.name.toLocaleLowerCase('tr').includes(q) || (b.description || '').toLocaleLowerCase('tr').includes(q));
});
const uyeAdaylari = computed(() => {
  const q = uyeAra.value.trim().toLocaleLowerCase('tr');
  return kullanicilar.value.filter((u) => !q || u.name.toLocaleLowerCase('tr').includes(q) || u.email.includes(q));
});

async function yukle() {
  yukleniyor.value = true;
  try {
    const [b, k] = await Promise.all([birimApi.liste(), auth.can('users.view') ? kullaniciApi.liste() : Promise.resolve({ kullanicilar: [] })]);
    liste.value = b.departmanlar; kullanicilar.value = k.kullanicilar || [];
    if (secili.value) await ac(liste.value.find((x) => x.id === secili.value.id) || null);
  } catch (e) { ui.bildir('Yüklenemedi: ' + e.message, 'hata'); }
  finally { yukleniyor.value = false; }
}
async function ac(b) {
  if (!b) { secili.value = null; return; }
  try { secili.value = (await birimApi.getir(b.id)).departman; } catch (e) { ui.bildir(e.message, 'hata'); }
}
function yeni() { form.value = { name: '', description: '', users: [] }; formHata.value = ''; uyeAra.value = ''; }
function duzenle(b) { form.value = { id: b.id, name: b.name, description: b.description || '', users: (b.users || []).map((u) => u.id) }; formHata.value = ''; uyeAra.value = ''; }
function uyeToggle(id) { const i = form.value.users.indexOf(id); i >= 0 ? form.value.users.splice(i, 1) : form.value.users.push(id); }

async function kaydet() {
  const f = form.value; formHata.value = '';
  if (!f.name.trim()) { formHata.value = 'Birim adı zorunludur.'; return; }
  kaydediyor.value = true;
  try {
    const govde = { name: f.name.trim(), description: f.description || null };
    if (auth.can('users.view')) govde.users = f.users;
    if (f.id) { await birimApi.guncelle(f.id, govde); ui.bildir('Birim güncellendi.'); }
    else { const d = await birimApi.olustur(govde); ui.bildir('Birim oluşturuldu.'); secili.value = d.departman; }
    form.value = null; await yukle();
  } catch (e) { formHata.value = e.message; }
  finally { kaydediyor.value = false; }
}
async function sil(b) {
  const onay = await ui.onay({ baslik: `"${b.name}" silinsin mi?`, tur: 'hata', onayMetni: 'Evet, sil',
    metin: 'Birim tanımı kaldırılır; envanter satırlarındaki birim metni değişmez.' });
  if (!onay) return;
  try { await birimApi.sil(b.id); ui.bildir('Birim silindi.'); if (secili.value?.id === b.id) secili.value = null; await yukle(); }
  catch (e) { ui.bildir(e.message, 'hata'); }
}

onMounted(yukle);
</script>

<template>
  <section class="space-y-5 max-w-[1780px] mx-auto">
    <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
      <div>
        <h1 class="text-2xl font-extrabold text-t-1 tracking-tight">Birimler</h1>
        <p class="text-xs text-t-2 mt-1">{{ liste.length }} birim · envanterdeki "Birim" sütunuyla ad üzerinden eşleşir; <span class="font-mono">department</span> kapsamındaki kullanıcılar yalnızca üyesi oldukları birimlerin kayıtlarını görür.</p>
      </div>
      <button v-if="auth.can('departments.create')" class="flex items-center gap-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/20" @click="yeni"><FaIcon icon="plus" class="h-3 w-3" />Yeni Birim</button>
    </div>

    <div class="grid grid-cols-12 gap-6 items-start">
      <div class="col-span-12 lg:col-span-5 rounded-xl border border-line bg-bg-card overflow-hidden">
        <div class="border-b border-line bg-bg-1/80 px-4 py-3 flex items-center gap-2">
          <input v-model="arama" placeholder="Birim ara…" class="girdi"><span class="text-[11px] text-t-3 font-mono shrink-0">{{ filtreli.length }}</span>
        </div>
        <div class="p-2 space-y-1.5 max-h-[640px] overflow-y-auto custom-scroll">
          <template v-if="yukleniyor"><div v-for="i in 5" :key="i" class="flex items-center justify-between p-3 rounded-lg border border-line bg-bg-2/60" aria-busy="true"><div class="flex items-center gap-2.5 flex-1"><Iskelet class="h-2.5 w-2.5" daire /><div class="flex-1 space-y-1.5"><Iskelet class="h-3 w-1/2" /><Iskelet class="h-2.5 w-2/3" /></div></div><Iskelet class="h-3 w-12" /></div></template>
          <p v-else-if="!filtreli.length" class="p-4 text-xs text-t-3">Birim yok.</p>
          <div v-for="(b, i) in filtreli" :key="b.id" @click="ac(b)" class="flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-all"
            :class="secili?.id === b.id ? 'border-indigo-500/40 bg-indigo-500/10' : 'border-line bg-bg-2/60 hover:border-line-bright hover:bg-bg-hover'">
            <div class="flex items-center gap-2.5 min-w-0">
              <span class="h-2.5 w-2.5 rounded-full shrink-0" :class="RENK[i % RENK.length]"></span>
              <div class="min-w-0"><p class="text-xs font-semibold text-t-1 truncate">{{ b.name }}</p><p class="text-[10.5px] text-t-3 truncate">{{ b.description || 'açıklama yok' }}</p></div>
            </div>
            <div class="text-right shrink-0 ml-3">
              <p class="text-[11px] font-mono text-t-2">{{ b.user_count }} üye</p>
              <p class="text-[10px] font-mono text-t-3">{{ b.envanter_sayisi }} kayıt</p>
            </div>
          </div>
        </div>
      </div>

      <div class="col-span-12 lg:col-span-7">
        <div v-if="!secili" class="rounded-xl border border-line bg-bg-card p-8 text-center text-xs text-t-3">Detay için soldan bir birim seçin.</div>
        <div v-else class="rounded-xl border border-line bg-bg-card overflow-hidden">
          <div class="border-b border-line bg-bg-1/70 px-5 py-4 flex items-start justify-between gap-3">
            <div>
              <h2 class="text-base font-bold text-t-1">{{ secili.name }}</h2>
              <p class="text-xs text-t-3 mt-0.5">{{ secili.description || 'Açıklama girilmemiş.' }}</p>
              <div class="mt-2 flex items-center gap-2 text-[11px]">
                <span class="rounded bg-sky-500/10 px-2 py-0.5 text-sky-300 border border-sky-500/20 font-mono">{{ secili.user_count }} üye</span>
                <span class="rounded bg-amber-500/10 px-2 py-0.5 text-amber-300 border border-amber-500/20 font-mono">{{ secili.envanter_sayisi }} envanter kaydı</span>
              </div>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <button v-if="auth.can('departments.update')" class="rounded-lg border border-line bg-bg-2 px-3 py-1.5 text-xs font-medium text-t-2 hover:text-t-1" @click="duzenle(secili)"><FaIcon icon="users-gear" class="h-3 w-3 mr-1.5" />Düzenle / Üyeler</button>
              <button v-if="auth.can('departments.delete')" class="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-300 hover:bg-rose-500/20" @click="sil(secili)"><FaIcon icon="trash" class="h-3 w-3 mr-1.5" />Sil</button>
            </div>
          </div>
          <div class="p-5">
            <h3 class="text-xs font-bold uppercase tracking-wider text-t-1 mb-2">Üyeler</h3>
            <div class="rounded-lg border border-line-60 bg-bg-2/40 overflow-hidden">
              <DataTable :columns="UYE_SUTUNLARI" :rows="secili.users || []" row-key="id" dense :page-size="10" empty-text="Bu birime atanmış kullanıcı yok.">
                <template #cell-name="{ value }"><span class="font-semibold text-t-1">{{ value }}</span></template>
                <template #cell-email="{ value }"><span class="text-[11px] text-t-3">{{ value }}</span></template>
                <template #cell-roles="{ value }"><div class="flex flex-wrap gap-1"><span v-for="r in value" :key="r" class="rounded px-1.5 py-0.5 text-[10px] bg-bg-3 border border-line text-t-2">{{ r }}</span></div></template>
              </DataTable>
            </div>
          </div>
        </div>
      </div>
    </div>

    <Modal v-if="form" :baslik="form.id ? 'Birimi Düzenle' : 'Yeni Birim'" alt-baslik="Ad envanterdeki Birim sütunuyla eşleşir; yeniden adlandırınca envanter de güncellenir" genislik="max-w-2xl" @kapat="form = null">
      <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Birim adı</label>
      <input v-model="form.name" class="girdi mb-3">
      <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Açıklama</label>
      <input v-model="form.description" class="girdi mb-4" placeholder="Örn: İnsan kaynakları süreçleri ve özlük dosyaları">
      <template v-if="auth.can('users.view')">
        <div class="flex items-center justify-between mb-1">
          <label class="text-[10px] uppercase tracking-wider text-t-3">Üyeler <span class="normal-case text-t-muted">({{ form.users.length }} seçili)</span></label>
          <input v-model="uyeAra" placeholder="Kullanıcı ara…" class="girdi !w-48 !py-1">
        </div>
        <div class="rounded-lg border border-line bg-bg-inset p-2 space-y-1 max-h-60 overflow-y-auto custom-scroll">
          <label v-for="u in uyeAdaylari" :key="u.id" class="flex items-center gap-2 text-[11px] text-slate-300 cursor-pointer hover:text-white">
            <input type="checkbox" :checked="form.users.includes(u.id)" @change="uyeToggle(u.id)" class="rounded border-[var(--line-2)] bg-bg-2 text-indigo-600 focus:ring-0">
            <span class="font-semibold">{{ u.name }}</span><span class="text-t-3">{{ u.email }}</span>
          </label>
          <p v-if="!uyeAdaylari.length" class="text-[10.5px] text-t-3">Kullanıcı yok.</p>
        </div>
      </template>
      <p v-if="formHata" class="text-[11px] text-rose-400 mt-3">{{ formHata }}</p>
      <template #alt>
        <span></span>
        <div class="flex gap-2">
          <button class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-bg-3 border border-line text-t-2 hover:text-t-1" @click="form = null"><FaIcon icon="xmark" class="h-3 w-3" />Vazgeç</button>
          <button :disabled="kaydediyor" class="px-5 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white" @click="kaydet"><FaIcon :icon="kaydediyor ? 'spinner' : 'floppy-disk'" class="h-3 w-3 mr-1.5" :class="kaydediyor ? 'animate-spin' : ''" />{{ kaydediyor ? 'Kaydediliyor…' : (form.id ? 'Güncelle' : 'Oluştur') }}</button>
        </div>
      </template>
    </Modal>
  </section>
</template>
