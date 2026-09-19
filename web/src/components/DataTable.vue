<script setup>
// Genel veri tablosu: sutun tanimi, hucre/filtre slotlari, secim (Set), istemci tarafi
// siralama, istege bagli istemci tarafi sayfalama, yukleniyor/hata/bos durumlari.
//
//   <DataTable :columns="[{ key: 'ad', label: 'Ad', sortable: true }]" :rows="liste" row-key="id"
//              selectable v-model:selected="secili" :page-size="25">
//     <template #filter-ad><SearchableSelect ... /></template>
//     <template #cell-ad="{ row, value }">{{ value }}</template>
//     <template #footer> ...sunucu sayfalamasi... </template>
//   </DataTable>
import { computed, ref, useSlots, watch } from 'vue';
import Sayfalama from './Sayfalama.vue';
import Iskelet from './Iskelet.vue';
import { sayi } from '../utils/format';

const props = defineProps({
  columns: { type: Array, required: true },   // {key,label,width,align,sortable,class,headerClass,hint}
  rows: { type: Array, default: () => [] },
  rowKey: { type: [String, Function], default: 'id' },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  emptyText: { type: String, default: 'Kayıt yok.' },
  selectable: { type: Boolean, default: false },
  selected: { type: Set, default: () => new Set() },
  minWidth: { type: String, default: '' },      // ornek: 'min-w-[1360px]'
  rowClass: { type: Function, default: null },
  pageSize: { type: Number, default: 0 },       // >0: istemci tarafi sayfalama
  dense: { type: Boolean, default: false },
  hoverable: { type: Boolean, default: true },
  showCount: { type: Boolean, default: true },
  clickable: { type: Boolean, default: false },  // satir tiklanabilir (row-click)
  skeletonRows: { type: Number, default: 6 },    // ilk yuklemede iskelet satir sayisi
});
// iskelet hucre genislikleri deterministik ama "rastgele" gorunsun
const iskeletGenislik = (r, c) => ['w-3/4', 'w-1/2', 'w-2/3', 'w-5/6', 'w-1/3'][(r * 3 + c) % 5];
const emit = defineEmits(['update:selected', 'row-click', 'sort']);
const slots = useSlots();

const anahtar = (row) => (typeof props.rowKey === 'function' ? props.rowKey(row) : row[props.rowKey]);
const filtreSatiriVar = computed(() => props.columns.some((c) => slots['filter-' + c.key]) || !!slots['filter-actions']);
const sutunSayisi = computed(() => props.columns.length + (props.selectable ? 1 : 0));

// ---- siralama (istemci) ----
const sirala = ref({ key: null, dir: 'asc' });
function siralaToggle(c) {
  if (!c.sortable) return;
  if (sirala.value.key === c.key) sirala.value = sirala.value.dir === 'asc' ? { key: c.key, dir: 'desc' } : { key: null, dir: 'asc' };
  else sirala.value = { key: c.key, dir: 'asc' };
  emit('sort', sirala.value);
}
const siraliSatirlar = computed(() => {
  const { key, dir } = sirala.value;
  if (!key) return props.rows;
  const col = props.columns.find((c) => c.key === key);
  const deger = (r) => (col?.sortValue ? col.sortValue(r) : r[key]);
  return [...props.rows].sort((a, b) => {
    const x = deger(a), y = deger(b);
    if (x === y) return 0;
    if (x === null || x === undefined || x === '') return 1;
    if (y === null || y === undefined || y === '') return -1;
    const s = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), 'tr');
    return dir === 'asc' ? s : -s;
  });
});

// ---- sayfalama (istemci) ----
const offset = ref(0);
watch(() => [props.rows.length, props.pageSize], () => { offset.value = 0; });
const gorunen = computed(() => (props.pageSize > 0 ? siraliSatirlar.value.slice(offset.value, offset.value + props.pageSize) : siraliSatirlar.value));

// ---- secim ----
const sayfaAnahtarlari = computed(() => gorunen.value.map(anahtar));
const hepsiSecili = computed(() => sayfaAnahtarlari.value.length > 0 && sayfaAnahtarlari.value.every((k) => props.selected.has(k)));
const kismiSecili = computed(() => !hepsiSecili.value && sayfaAnahtarlari.value.some((k) => props.selected.has(k)));
function secimYay(yeni) { emit('update:selected', yeni); }
function satirToggle(row, sec) {
  const yeni = new Set(props.selected);
  sec ? yeni.add(anahtar(row)) : yeni.delete(anahtar(row));
  secimYay(yeni);
}
function hepsiniToggle(e) {
  const yeni = new Set(props.selected);
  sayfaAnahtarlari.value.forEach((k) => (e.target.checked ? yeni.add(k) : yeni.delete(k)));
  secimYay(yeni);
}

const hizalama = (c) => (c.align === 'right' ? 'text-right' : c.align === 'center' ? 'text-center' : 'text-left');
const hucreDolgu = computed(() => (props.dense ? 'py-2 px-3' : 'py-3 px-3'));
</script>

<template>
  <div class="overflow-x-auto">
    <table class="w-full text-left text-xs border-collapse" :class="minWidth">
      <thead>
        <tr class="bg-[var(--bg-1)] border-b border-[var(--line)] text-[11px] font-extrabold uppercase tracking-wider text-[var(--t1)]">
          <th v-if="selectable" class="py-3 px-2 w-10 text-center">
            <input type="checkbox" :checked="hepsiSecili" :indeterminate.prop="kismiSecili" @change="hepsiniToggle"
              class="rounded border-[var(--line-2)] bg-[var(--bg-inset)] text-indigo-600 focus:ring-0 cursor-pointer" aria-label="Sayfadakileri seç">
          </th>
          <th v-for="c in columns" :key="c.key" class="py-3 px-3" :class="[c.width, hizalama(c), c.headerClass, c.sortable ? 'cursor-pointer select-none hover:text-white' : '']"
            :title="c.hint" @click="siralaToggle(c)">
            <span class="inline-flex items-center gap-1">
              <slot :name="'head-' + c.key" :column="c">{{ c.label }}</slot>
              <FaIcon v-if="c.sortable" icon="chevron-down" class="h-2 w-2 transition-transform"
                :class="sirala.key === c.key ? (sirala.dir === 'asc' ? 'text-indigo-400 rotate-180' : 'text-indigo-400') : 'text-[var(--t2)] opacity-40'" />
            </span>
          </th>
        </tr>
        <tr v-if="filtreSatiriVar" class="bg-[var(--bg-inset)]/95 border-b border-[var(--line-2)]">
          <td v-if="selectable" class="p-1.5"></td>
          <td v-for="c in columns" :key="'f-' + c.key" class="p-1.5 align-middle" :class="hizalama(c)">
            <slot :name="'filter-' + c.key" :column="c"></slot>
          </td>
        </tr>
      </thead>
      <tbody class="divide-y divide-[var(--line)] font-medium transition-opacity duration-200" :class="loading && rows.length ? 'opacity-50 pointer-events-none' : ''">
        <template v-if="loading && !rows.length">
          <slot name="loading">
            <tr v-for="r in skeletonRows" :key="'isk-' + r" aria-hidden="true">
              <td v-if="selectable" :class="dense ? 'py-2 px-2' : 'py-3 px-2'" class="text-center"><Iskelet class="h-3.5 w-3.5 mx-auto" /></td>
              <td v-for="(c, ci) in columns" :key="c.key" :class="[hucreDolgu, c.class]">
                <Iskelet class="h-3" :class="iskeletGenislik(r, ci)" />
                <Iskelet v-if="ci === 1 || ci === columns.length - 2" class="h-2.5 w-1/3 mt-1.5" />
              </td>
            </tr>
          </slot>
        </template>
        <tr v-else-if="error"><td :colspan="sutunSayisi" class="py-16 text-center text-rose-400 text-xs">Hata: {{ error }}</td></tr>
        <tr v-else-if="!gorunen.length"><td :colspan="sutunSayisi" class="py-16 text-center text-[var(--t2)] text-xs"><slot name="empty">{{ emptyText }}</slot></td></tr>
        <tr v-for="(row, i) in gorunen" :key="anahtar(row)" class="transition-colors group"
          :class="[hoverable ? 'hover:bg-[var(--bg-3)]/60' : '', rowClass ? rowClass(row) : '', clickable ? 'cursor-pointer' : '']"
          @click="emit('row-click', row)">
          <td v-if="selectable" :class="dense ? 'py-2 px-2' : 'py-3 px-2'" class="text-center" @click.stop>
            <input type="checkbox" :checked="selected.has(anahtar(row))" @change="satirToggle(row, $event.target.checked)"
              class="rounded border-[var(--line-2)] bg-[var(--bg-inset)] text-indigo-600 focus:ring-0 cursor-pointer">
          </td>
          <td v-for="c in columns" :key="c.key" :class="[hucreDolgu, hizalama(c), c.class]">
            <slot :name="'cell-' + c.key" :row="row" :value="row[c.key]" :index="offset + i">{{ row[c.key] ?? '—' }}</slot>
          </td>
        </tr>
      </tbody>
    </table>

    <slot name="footer">
      <div v-if="pageSize > 0 && rows.length > pageSize" class="p-3 bg-[var(--bg-1)]/80 border-t border-[var(--line)] flex items-center justify-between gap-3">
        <span v-if="showCount" class="text-[11px] text-[var(--t2)]">{{ sayi(offset + 1) }}–{{ sayi(Math.min(offset + pageSize, rows.length)) }} / {{ sayi(rows.length) }}</span>
        <Sayfalama :toplam="rows.length" :limit="pageSize" :offset="offset" @git="(o) => (offset = o)" />
      </div>
    </slot>
  </div>
</template>
