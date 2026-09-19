<script setup>
// Kullanici yonetimi: liste/arama, olusturma ve duzenleme (rol + birim iliskisi), pasife alma, silme.
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import { birimler as birimApi, kullanicilar as kullaniciApi, roller as rolApi } from '../../api';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { tarih } from '../../utils/format';
import Modal from '../../components/Modal.vue';
import Toggle from '../../components/Toggle.vue';
import DataTable from '../../components/DataTable.vue';
import SearchableSelect from '../../components/SearchableSelect.vue';

const SUTUNLAR = [
  { key: 'name', label: 'Kullanıcı', sortable: true },
  { key: 'roles', label: 'Roller' },
  { key: 'departments', label: 'Birimler' },
  { key: 'last_login_at', label: 'Son giriş', sortable: true, width: 'w-40' },
  { key: 'is_active', label: 'Aktif', align: 'center', width: 'w-20', sortable: true },
  { key: 'islem', label: 'İşlem', align: 'right', width: 'w-32' },
];

const auth = useAuthStore();
const ui = useUiStore();
const route = useRoute();

const liste = ref([]);
const roller = ref([]);
const birimler = ref([]);
const yukleniyor = ref(true);
const arama = ref(String(route.query.arama || ''));
const rolFiltre = ref('');
const birimFiltre = ref('');

const form = ref(null); // {id?, ...}
const formHata = ref({});
const kaydediyor = ref(false);

const filtreli = computed(() => {
  const q = arama.value.trim().toLocaleLowerCase('tr');
  return liste.value.filter((u) =>
    (!q || u.name.toLocaleLowerCase('tr').includes(q) || u.email.includes(q)) &&
    (!rolFiltre.value || (u.roles || []).includes(rolFiltre.value)) &&
    (!birimFiltre.value || (u.department_ids || []).includes(+birimFiltre.value)));
});
const sayac = computed(() => ({ aktif: liste.value.filter((u) => u.is_active).length, pasif: liste.value.filter((u) => !u.is_active).length }));
const basHarf = (ad) => (ad || '?').split(/\s+/).map((p) => p[0]).join('').slice(0, 2).toUpperCase();
const bypassRolleri = computed(() => roller.value.filter((r) => r.bypass).map((r) => r.name));

async function yukle() {
  yukleniyor.value = true;
  try {
    const [k, r, b] = await Promise.all([kullaniciApi.liste(), rolApi.liste().catch(() => ({ roller: [] })), birimApi.liste().catch(() => ({ departmanlar: [] }))]);
    liste.value = k.kullanicilar; roller.value = r.roller || []; birimler.value = b.departmanlar || [];
  } catch (e) { ui.bildir('Yüklenemedi: ' + e.message, 'hata'); }
  finally { yukleniyor.value = false; }
}

function yeni() {
  form.value = { name: '', email: '', password: '', roles: [], departments: [], department_id: null, is_active: true };
  formHata.value = {};
}
function duzenle(u) {
  form.value = { id: u.id, name: u.name, email: u.email, password: '', roles: [...(u.roles || [])],
    departments: [...(u.department_ids || [])], department_id: u.department_id || null, is_active: !!u.is_active };
  formHata.value = {};
}
function rolToggle(ad) {
  const i = form.value.roles.indexOf(ad);
  i >= 0 ? form.value.roles.splice(i, 1) : form.value.roles.push(ad);
}
function birimToggle(id) {
  const i = form.value.departments.indexOf(id);
  i >= 0 ? form.value.departments.splice(i, 1) : form.value.departments.push(id);
  if (i >= 0 && form.value.department_id === id) form.value.department_id = null;
}

async function kaydet() {
  const f = form.value; formHata.value = {};
  if (!f.name.trim()) formHata.value.name = 'Ad zorunludur.';
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email.trim())) formHata.value.email = 'Geçerli bir e-posta girin.';
  if (!f.id && f.password.length < 8) formHata.value.password = 'Şifre en az 8 karakter olmalıdır.';
  if (f.id && f.password && f.password.length < 8) formHata.value.password = 'Şifre en az 8 karakter olmalıdır.';
  if (Object.keys(formHata.value).length) return;
  kaydediyor.value = true;
  try {
    const govde = { name: f.name.trim(), email: f.email.trim().toLowerCase(), roles: f.roles, departments: f.departments,
      department_id: f.department_id, is_active: f.is_active };
    if (f.password) govde.password = f.password;
    if (f.id) { await kullaniciApi.guncelle(f.id, govde); ui.bildir('Kullanıcı güncellendi.'); }
    else { await kullaniciApi.olustur(govde); ui.bildir('Kullanıcı oluşturuldu.'); }
    if (f.id === auth.user?.id) auth.fetchMe().catch(() => {});
    form.value = null; yukle();
  } catch (e) {
    if (e.errors) formHata.value = Object.fromEntries(Object.entries(e.errors).map(([k, v]) => [k, v[0]]));
    formHata.value._ = e.message;
  } finally { kaydediyor.value = false; }
}

async function aktifToggle(u) {
  try { await kullaniciApi.guncelle(u.id, { is_active: !u.is_active }); u.is_active = !u.is_active; ui.bildir(u.is_active ? 'Kullanıcı aktif.' : 'Kullanıcı pasife alındı.', 'bilgi'); }
  catch (e) { ui.bildir(e.message, 'hata'); }
}
async function sil(u) {
  const onay = await ui.onay({ baslik: 'Kullanıcı silinsin mi?', tur: 'hata', onayMetni: 'Evet, sil',
    metin: `${u.name} (${u.email}) hesabı ve rol/birim atamaları kaldırılır.`, detay: 'Denetim günlüğündeki kayıtları korunur.' });
  if (!onay) return;
  try { await kullaniciApi.sil(u.id); ui.bildir('Kullanıcı silindi.'); yukle(); }
  catch (e) { ui.bildir(e.message, 'hata'); }
}

onMounted(yukle);
</script>

<template>
  <section class="space-y-5 max-w-[1780px] mx-auto">
    <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
      <div>
        <h1 class="text-2xl font-extrabold text-t-1 tracking-tight">Kullanıcılar</h1>
        <p class="text-xs text-t-2 mt-1">{{ liste.length }} kullanıcı · {{ sayac.aktif }} aktif, {{ sayac.pasif }} pasif · roller ve birim üyelikleri buradan atanır.</p>
      </div>
      <button v-if="auth.can('users.create')" class="flex items-center gap-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/20" @click="yeni"><FaIcon icon="user-plus" class="h-3 w-3" />Yeni Kullanıcı</button>
    </div>

    <div class="rounded-xl border border-line bg-bg-card overflow-hidden">
      <div class="border-b border-line bg-bg-1/80 px-4 py-3 flex flex-col md:flex-row md:items-center gap-2">
        <input v-model="arama" placeholder="Ad veya e-posta ara…" class="girdi md:max-w-xs">
        <div class="md:w-52"><SearchableSelect v-model="rolFiltre" :options="roller.map((r) => ({ value: r.name, label: r.name }))" placeholder="Tüm roller" size="sm" /></div>
        <div class="md:w-60"><SearchableSelect v-model="birimFiltre" :options="birimler.map((b) => ({ value: String(b.id), label: b.name, count: b.user_count }))" placeholder="Tüm birimler" size="sm" /></div>
        <span class="text-[11px] text-t-3 md:ml-auto font-mono">{{ filtreli.length }} sonuç</span>
      </div>
      <DataTable :columns="SUTUNLAR" :rows="filtreli" row-key="id" :loading="yukleniyor" empty-text="Kayıt yok." min-width="min-w-[900px]" dense :page-size="25">
        <template #cell-name="{ row: u }">
          <div class="flex items-center gap-2.5">
            <span class="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/15 text-indigo-300 text-[11px] font-bold border border-indigo-500/20">{{ basHarf(u.name) }}</span>
            <div><p class="font-semibold text-t-1">{{ u.name }}<span v-if="u.id === auth.user?.id" class="ml-1.5 text-[9.5px] text-t-3">(siz)</span></p><p class="text-[11px] text-t-3">{{ u.email }}</p></div>
          </div>
        </template>
        <template #cell-roles="{ row: u }">
          <div class="flex flex-wrap gap-1">
            <span v-for="r in u.roles" :key="r" class="rounded px-1.5 py-0.5 text-[10px] font-semibold border" :class="bypassRolleri.includes(r) ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30' : 'bg-bg-3 text-t-2 border-line'">{{ r }}</span>
            <span v-if="!u.roles?.length" class="text-[10.5px] text-t-3">rol yok</span>
          </div>
        </template>
        <template #cell-departments="{ row: u }">
          <div class="flex flex-wrap gap-1">
            <span v-for="b in u.departments" :key="b" class="rounded px-1.5 py-0.5 text-[10px] bg-sky-500/10 text-sky-300 border border-sky-500/20">{{ b }}</span>
            <span v-if="!u.departments?.length" class="text-[10.5px] text-t-3">—</span>
          </div>
        </template>
        <template #cell-last_login_at="{ value }"><span class="font-mono text-[10.5px] text-t-3">{{ value ? tarih(value) : 'hiç' }}</span></template>
        <template #cell-is_active="{ row: u }"><Toggle :model-value="!!u.is_active" :disabled="!auth.can('users.update') || u.id === auth.user?.id" @update:model-value="aktifToggle(u)" /></template>
        <template #cell-islem="{ row: u }">
          <span class="whitespace-nowrap">
            <span class="inline-flex items-center gap-1.5">
              <button v-if="auth.can('users.update')" class="flex items-center gap-1 rounded-md border border-line bg-bg-2 px-2 py-1 text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 hover:border-indigo-500/40" title="Düzenle" @click="duzenle(u)"><FaIcon icon="pen-to-square" class="h-3 w-3" />Düzenle</button>
              <button v-if="auth.can('users.delete') && u.id !== auth.user?.id" class="flex h-7 w-7 items-center justify-center rounded-md border border-line bg-bg-2 text-t-3 hover:text-rose-400 hover:border-rose-500/40" title="Sil" @click="sil(u)"><FaIcon icon="trash" class="h-3 w-3" /></button>
            </span>
          </span>
        </template>
      </DataTable>
    </div>

    <Modal v-if="form" :baslik="form.id ? 'Kullanıcıyı Düzenle' : 'Yeni Kullanıcı'" alt-baslik="Rol izinleri ve birim üyelikleri kapsamı belirler" genislik="max-w-3xl" @kapat="form = null">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Ad Soyad</label>
          <input v-model="form.name" class="girdi"><p v-if="formHata.name" class="text-[11px] text-rose-400 mt-1">{{ formHata.name }}</p>
        </div>
        <div>
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">E-posta</label>
          <input v-model="form.email" type="email" class="girdi"><p v-if="formHata.email" class="text-[11px] text-rose-400 mt-1">{{ formHata.email }}</p>
        </div>
        <div>
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">{{ form.id ? 'Yeni şifre (boş: değişmez)' : 'Şifre' }}</label>
          <input v-model="form.password" type="password" autocomplete="new-password" class="girdi"><p v-if="formHata.password" class="text-[11px] text-rose-400 mt-1">{{ formHata.password }}</p>
        </div>
        <div class="flex items-center gap-3 pt-5">
          <Toggle v-model="form.is_active" :disabled="form.id === auth.user?.id" /><span class="text-xs text-t-2">Hesap aktif</span>
        </div>
        <div>
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Roller</label>
          <div class="rounded-lg border border-line bg-bg-inset p-2 space-y-1 max-h-48 overflow-y-auto custom-scroll">
            <label v-for="r in roller" :key="r.id" class="flex items-start gap-2 text-[11px] text-slate-300 cursor-pointer hover:text-white" :class="r.bypass && !auth.isSuper ? 'opacity-50 cursor-not-allowed' : ''">
              <input type="checkbox" :checked="form.roles.includes(r.name)" :disabled="r.bypass && !auth.isSuper" @change="rolToggle(r.name)" class="mt-0.5 rounded border-[var(--line-2)] bg-bg-2 text-indigo-600 focus:ring-0">
              <span><span class="font-semibold">{{ r.name }}</span><span v-if="r.bypass" class="ml-1 text-[9.5px] text-indigo-300">süper yetki</span><span class="block text-[10.5px] text-t-3">{{ r.description }}</span></span>
            </label>
          </div>
          <p v-if="formHata.roles" class="text-[11px] text-rose-400 mt-1">{{ formHata.roles }}</p>
        </div>
        <div>
          <label class="text-[10px] uppercase tracking-wider text-t-3 block mb-1">Birimler <span class="normal-case text-t-muted">(department kapsamı bu birimlerle çalışır)</span></label>
          <div class="rounded-lg border border-line bg-bg-inset p-2 space-y-1 max-h-48 overflow-y-auto custom-scroll">
            <label v-for="b in birimler" :key="b.id" class="flex items-center justify-between gap-2 text-[11px] text-slate-300 cursor-pointer hover:text-white">
              <span class="flex items-center gap-2"><input type="checkbox" :checked="form.departments.includes(b.id)" @change="birimToggle(b.id)" class="rounded border-[var(--line-2)] bg-bg-2 text-indigo-600 focus:ring-0"><span>{{ b.name }}</span></span>
              <button v-if="form.departments.includes(b.id)" type="button" class="text-[9.5px] rounded px-1.5 py-0.5 border" :class="form.department_id === b.id ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30' : 'text-t-3 border-line hover:text-t-1'" @click="form.department_id = form.department_id === b.id ? null : b.id">{{ form.department_id === b.id ? 'birincil' : 'birincil yap' }}</button>
            </label>
            <p v-if="!birimler.length" class="text-[10.5px] text-t-3">Birim tanımlı değil.</p>
          </div>
        </div>
      </div>
      <p v-if="formHata._" class="text-[11px] text-rose-400 mt-3">{{ formHata._ }}</p>
      <template #alt>
        <span class="text-[11px] text-t-3">{{ form.roles.length }} rol · {{ form.departments.length }} birim</span>
        <div class="flex gap-2">
          <button class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-bg-3 border border-line text-t-2 hover:text-t-1" @click="form = null"><FaIcon icon="xmark" class="h-3 w-3" />Vazgeç</button>
          <button :disabled="kaydediyor" class="px-5 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white" @click="kaydet"><FaIcon :icon="kaydediyor ? 'spinner' : 'floppy-disk'" class="h-3 w-3 mr-1.5" :class="kaydediyor ? 'animate-spin' : ''" />{{ kaydediyor ? 'Kaydediliyor…' : (form.id ? 'Güncelle' : 'Oluştur') }}</button>
        </div>
      </template>
    </Modal>
  </section>
</template>
