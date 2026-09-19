<script setup>
// Aranabilir secim kutusu (combobox). Tekli / coklu; istege bagli serbest metin
// (allowCustom: listede yoksa yazilani deger olarak kabul eder). Acilir liste
// body'ye Teleport edilir (tablo/overflow kirpmasin), klavye ile gezilir.
//
//   <SearchableSelect v-model="deger" :options="['A','B']" placeholder="Seçin…" />
//   <SearchableSelect v-model="liste" :options="opts" multiple />
//   options: string | { value, label?, count?, alt?, badge?, badgeClass?, group? }
//   group: ayni gruptaki secenekler pes pese verilir; grup degisince baslik satiri cizilir.
//   Ayni value farkli gruplarda tekrar edebilir (ör. m.5 ve m.6'daki ayni hukuki sebep).
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

const props = defineProps({
  modelValue: { type: [String, Number, Array, null], default: null },
  options: { type: Array, default: () => [] },
  multiple: { type: Boolean, default: false },
  allowCustom: { type: Boolean, default: false },
  placeholder: { type: String, default: 'Seçin veya arayın…' },
  clearable: { type: Boolean, default: true },
  disabled: { type: Boolean, default: false },
  size: { type: String, default: 'md' },          // sm | md
  emptyText: { type: String, default: 'Eşleşen seçenek yok' },
  customText: { type: String, default: 'olarak kullan' },
  highlight: { type: Object, default: null },       // Set/Map: value -> rozet metni (ozel nitelikli gibi)
  maxHeight: { type: Number, default: 260 },
  inputClass: { type: String, default: '' },
});
const emit = defineEmits(['update:modelValue', 'change', 'open', 'close']);

const kutu = ref(null);
const girdi = ref(null);
const liste = ref(null);
const acik = ref(false);
const sorgu = ref('');
const vurgu = ref(0);
const konum = ref({ top: 0, alt: 0, left: 0, width: 0, yukari: false });

const norm = (s) => String(s ?? '').toLocaleLowerCase('tr').trim();
const secenekler = computed(() => props.options.map((o) =>
  (o !== null && typeof o === 'object') ? { ...o, label: o.label ?? String(o.value) } : { value: o, label: String(o) }));
const etiket = (v) => secenekler.value.find((o) => o.value === v)?.label ?? String(v ?? '');
const anahtar = (o, i) => (o.group ? o.group + '|' : '') + String(o.value) + '|' + i;
const grupBasi = (i) => !!filtreli.value[i]?.group && filtreli.value[i].group !== filtreli.value[i - 1]?.group;
const seciliSecenek = computed(() => (props.multiple || seciliTek.value === null ? null : secenekler.value.find((o) => o.value === seciliTek.value) || null));

const seciliDizi = computed(() => (props.multiple ? (Array.isArray(props.modelValue) ? props.modelValue : []) : []));
const seciliTek = computed(() => (props.multiple ? null : (props.modelValue ?? null)));
const seciliEtiket = computed(() => (seciliTek.value === null || seciliTek.value === '' ? '' : etiket(seciliTek.value)));

const filtreli = computed(() => {
  const q = norm(sorgu.value);
  // Tekli modda kullanici mevcut secimi silmeden listeyi actiysa hepsini goster
  if (!q || (!props.multiple && sorgu.value === seciliEtiket.value)) return secenekler.value;
  return secenekler.value.filter((o) => norm(o.label).includes(q) || norm(o.alt).includes(q));
});
const tamEslesme = computed(() => secenekler.value.some((o) => norm(o.label) === norm(sorgu.value)));
const ozelAday = computed(() => props.allowCustom && sorgu.value.trim() && !tamEslesme.value ? sorgu.value.trim() : '');
const satirSayisi = computed(() => filtreli.value.length + (ozelAday.value ? 1 : 0));
const secili = (v) => (props.multiple ? seciliDizi.value.includes(v) : seciliTek.value === v);
const gosterilenDeger = computed(() => (acik.value ? sorgu.value : (props.multiple ? sorgu.value : seciliEtiket.value)));
const dolu = computed(() => (props.multiple ? seciliDizi.value.length > 0 : !!seciliEtiket.value));

function yay(v) { emit('update:modelValue', v); emit('change', v); }

function konumla() {
  const r = kutu.value?.getBoundingClientRect();
  if (!r) return;
  const altBosluk = window.innerHeight - r.bottom;
  const yukari = altBosluk < Math.min(props.maxHeight, 200) && r.top > altBosluk;
  konum.value = { top: r.bottom + 4, alt: window.innerHeight - r.top + 4, left: r.left, width: r.width, yukari };
}
function ac() {
  if (props.disabled || acik.value) return;
  acik.value = true; vurgu.value = 0;
  if (!props.multiple) sorgu.value = seciliEtiket.value;
  konumla();
  emit('open');
  nextTick(() => {
    girdi.value?.focus();
    if (!props.multiple && girdi.value) girdi.value.select();
  });
}
function yazarakAc(e) {
  // kapaliyken yazilmaya baslandiysa secimi ezmeden ac
  if (!acik.value) { acik.value = true; vurgu.value = 0; konumla(); emit('open'); }
  sorgu.value = e.target.value;
}
function kapat() {
  if (!acik.value) return;
  // Tekli + serbest metin: yazilan listede yoksa deger olarak kabul edilir
  if (!props.multiple) {
    const t = sorgu.value.trim();
    if (props.allowCustom && t && t !== seciliEtiket.value) {
      const es = secenekler.value.find((o) => norm(o.label) === norm(t));
      yay(es ? es.value : t);
    } else if (!t && props.allowCustom && seciliEtiket.value && sorgu.value === '') {
      // kullanici alani bosaltmis
      yay('');
    }
  }
  acik.value = false; sorgu.value = ''; emit('close');
}
function sec(o) {
  if (props.multiple) {
    const yeni = secili(o.value) ? seciliDizi.value.filter((v) => v !== o.value) : [...seciliDizi.value, o.value];
    yay(yeni); sorgu.value = ''; vurgu.value = 0;
    nextTick(() => { girdi.value?.focus(); konumla(); });
  } else {
    yay(o.value); sorgu.value = etiket(o.value); acik.value = false; sorgu.value = ''; emit('close');
    girdi.value?.blur();
  }
}
function ozelSec() {
  if (!ozelAday.value) return;
  if (props.multiple) { yay([...seciliDizi.value, ozelAday.value]); sorgu.value = ''; nextTick(konumla); }
  else { yay(ozelAday.value); acik.value = false; sorgu.value = ''; emit('close'); girdi.value?.blur(); }
}
function kaldir(v) { yay(seciliDizi.value.filter((x) => x !== v)); nextTick(konumla); }
function temizle() { yay(props.multiple ? [] : ''); sorgu.value = ''; girdi.value?.focus(); }

function tus(e) {
  if (!acik.value && ['ArrowDown', 'ArrowUp', 'Enter'].includes(e.key)) { e.preventDefault(); ac(); return; }
  if (e.key === 'ArrowDown') { e.preventDefault(); vurgu.value = Math.min(vurgu.value + 1, satirSayisi.value - 1); kaydir(); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); vurgu.value = Math.max(vurgu.value - 1, 0); kaydir(); }
  else if (e.key === 'Enter') {
    e.preventDefault();
    if (vurgu.value < filtreli.value.length) sec(filtreli.value[vurgu.value]);
    else if (ozelAday.value) ozelSec();
  }
  else if (e.key === 'Escape') { e.preventDefault(); if (!props.multiple) sorgu.value = seciliEtiket.value; kapat(); girdi.value?.blur(); }
  else if (e.key === 'Backspace' && props.multiple && !sorgu.value && seciliDizi.value.length) kaldir(seciliDizi.value[seciliDizi.value.length - 1]);
  else if (e.key === 'Tab') kapat();
}
function kaydir() {
  nextTick(() => { liste.value?.querySelector('[data-vurgu="1"]')?.scrollIntoView({ block: 'nearest' }); });
}
function disTiklama(e) {
  if (!acik.value) return;
  if (kutu.value?.contains(e.target) || liste.value?.contains(e.target)) return;
  kapat();
}
function pencere() { if (acik.value) konumla(); }

watch(sorgu, () => { vurgu.value = 0; if (acik.value) nextTick(konumla); });
watch(acik, (a) => {
  const fn = a ? 'addEventListener' : 'removeEventListener';
  document[fn]('mousedown', disTiklama, true);
  window[fn]('scroll', pencere, true);
  window[fn]('resize', pencere);
});
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', disTiklama, true);
  window.removeEventListener('scroll', pencere, true);
  window.removeEventListener('resize', pencere);
});
</script>

<template>
  <div ref="kutu" class="relative min-w-0" :class="disabled ? 'opacity-60' : ''">
    <div class="flex flex-wrap items-center gap-1 rounded-lg border bg-[var(--bg-inset)] text-white cursor-text"
      :class="[size === 'sm' ? 'px-1.5 py-0.5 min-h-[28px] text-[11px]' : 'px-2 py-1 min-h-[34px] text-xs',
               acik ? 'border-indigo-500' : 'border-[var(--line)] hover:border-[var(--line-2)]', inputClass]"
      @click="ac">
      <template v-if="multiple">
        <span v-for="v in seciliDizi" :key="v" class="inline-flex items-center gap-1 max-w-full rounded bg-indigo-500/15 border border-indigo-500/30 text-indigo-200 px-1.5 py-0.5 text-[10.5px] leading-tight">
          <span class="truncate">{{ etiket(v) }}</span>
          <button v-if="!disabled" type="button" class="text-indigo-300 hover:text-white" tabindex="-1" @click.stop="kaldir(v)" aria-label="Kaldır">✕</button>
        </span>
      </template>
      <input ref="girdi" :value="gosterilenDeger" :placeholder="dolu && multiple ? '' : placeholder" :disabled="disabled"
        class="flex-1 min-w-[60px] bg-transparent border-0 p-0 focus:ring-0 focus:outline-none placeholder-[var(--t2)]"
        :class="size === 'sm' ? 'text-[11px] py-0.5' : 'text-xs py-0.5'"
        role="combobox" :aria-expanded="acik" autocomplete="off"
        @focus="ac" @input="yazarakAc" @keydown="tus">
      <span v-if="highlight && !multiple && seciliTek !== null && highlight.has(seciliTek)" class="shrink-0 text-[9.5px] font-semibold px-1 rounded bg-fuchsia-500/20 text-fuchsia-300">{{ highlight.get ? highlight.get(seciliTek) : 'özel' }}</span>
      <span v-else-if="seciliSecenek?.badge && !acik" class="shrink-0 text-[9.5px] font-semibold px-1 rounded" :class="seciliSecenek.badgeClass || 'bg-[var(--bg-3)] text-[var(--t2)]'">{{ seciliSecenek.badge }}</span>
      <button v-if="clearable && dolu && !disabled" type="button" class="shrink-0 text-[var(--t2)] hover:text-white px-0.5" tabindex="-1" title="Temizle" @click.stop="temizle">✕</button>
      <FaIcon icon="chevron-down" class="shrink-0 h-2.5 w-2.5 text-[var(--t2)] transition-transform mr-0.5" :class="acik ? 'rotate-180' : ''" />
    </div>

    <Teleport to="body">
      <div v-if="acik" ref="liste" class="fixed z-[70] rounded-lg border border-[var(--line)] bg-[var(--bg-1)] shadow-2xl overflow-y-auto custom-scroll py-1"
        :style="{ top: konum.yukari ? 'auto' : konum.top + 'px', bottom: konum.yukari ? konum.alt + 'px' : 'auto', left: konum.left + 'px', width: Math.max(konum.width, 220) + 'px', maxHeight: maxHeight + 'px' }"
        role="listbox">
        <template v-for="(o, i) in filtreli" :key="anahtar(o, i)">
        <div v-if="grupBasi(i)" class="sticky top-0 z-10 px-2.5 pt-2 pb-1 text-[9.5px] font-bold uppercase tracking-wider text-[var(--t2)] bg-[var(--bg-1)] border-b border-[var(--line)]" :class="i ? 'mt-1' : ''">{{ o.group }}</div>
        <div :data-vurgu="i === vurgu ? 1 : 0" role="option" :aria-selected="secili(o.value)"
          class="flex items-center justify-between gap-2 px-2.5 py-1.5 text-[11.5px] cursor-pointer"
          :class="[i === vurgu ? 'bg-indigo-500/15' : '', secili(o.value) ? 'text-indigo-200' : 'text-slate-200']"
          @mouseenter="vurgu = i" @click="sec(o)">
          <span class="flex items-center gap-2 min-w-0">
            <span v-if="multiple" class="h-3.5 w-3.5 shrink-0 rounded border flex items-center justify-center text-[9px]" :class="secili(o.value) ? 'bg-indigo-600 border-indigo-500 text-white' : 'border-[var(--line-2)]'">{{ secili(o.value) ? '✓' : '' }}</span>
            <span class="min-w-0">
              <span class="block truncate">{{ o.label }}</span>
              <span v-if="o.alt" class="block truncate text-[10px] text-[var(--t2)]">{{ o.alt }}</span>
            </span>
            <span v-if="highlight && highlight.has(o.value)" class="shrink-0 text-[9.5px] font-semibold px-1 rounded bg-fuchsia-500/20 text-fuchsia-300">{{ highlight.get ? highlight.get(o.value) : 'özel' }}</span>
            <span v-else-if="o.badge" class="shrink-0 text-[9.5px] font-semibold px-1 rounded" :class="o.badgeClass || 'bg-[var(--bg-3)] text-[var(--t2)]'">{{ o.badge }}</span>
          </span>
          <span v-if="o.count !== undefined" class="shrink-0 font-mono text-[10px] text-[var(--t2)]">{{ o.count }}</span>
          <span v-else-if="!multiple && secili(o.value)" class="shrink-0 text-[10px] text-indigo-400">✓</span>
        </div>
        </template>
        <div v-if="ozelAday" :data-vurgu="vurgu === filtreli.length ? 1 : 0" class="px-2.5 py-1.5 text-[11.5px] cursor-pointer border-t border-[var(--line)] text-amber-300"
          :class="vurgu === filtreli.length ? 'bg-indigo-500/15' : ''" @mouseenter="vurgu = filtreli.length" @click="ozelSec">
          <FaIcon icon="plus" class="h-2.5 w-2.5 mr-1" />“{{ ozelAday }}” {{ customText }}
        </div>
        <div v-if="!filtreli.length && !ozelAday" class="px-2.5 py-2 text-[11px] text-[var(--t2)]">{{ emptyText }}</div>
      </div>
    </Teleport>
  </div>
</template>
