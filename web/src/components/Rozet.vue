<script setup>
// Rozet / pill: durum, risk, sayac. tur: kritik|yuksek|orta|dusuk|ok|uyari|hata|bilgi|notr|mor
// nokta: sol renkli nokta (nabiz: animasyonlu), ikon: Font Awesome adi, mono: monospace metin
defineProps({
  tur: { type: String, default: 'notr' }, nokta: Boolean, nabiz: Boolean, ikon: String,
  mono: Boolean, dolu: Boolean, sekil: { type: String, default: 'pill' }, boyut: { type: String, default: 'sm' },
});
const TUR = {
  kritik: { yumusak: 'bg-rose-500/15 text-rose-400 border-rose-500/30', dolu: 'bg-rose-600 text-white border-rose-600', nokta: 'bg-rose-500' },
  hata: { yumusak: 'bg-rose-500/15 text-rose-400 border-rose-500/30', dolu: 'bg-rose-600 text-white border-rose-600', nokta: 'bg-rose-500' },
  yuksek: { yumusak: 'bg-amber-500/15 text-amber-400 border-amber-500/30', dolu: 'bg-amber-500 text-black border-amber-500', nokta: 'bg-amber-500' },
  uyari: { yumusak: 'bg-amber-500/15 text-amber-400 border-amber-500/30', dolu: 'bg-amber-500 text-black border-amber-500', nokta: 'bg-amber-500' },
  orta: { yumusak: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30', dolu: 'bg-yellow-500 text-black border-yellow-500', nokta: 'bg-yellow-500' },
  dusuk: { yumusak: 'bg-blue-500/15 text-blue-400 border-blue-500/30', dolu: 'bg-blue-600 text-white border-blue-600', nokta: 'bg-blue-500' },
  ok: { yumusak: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30', dolu: 'bg-emerald-600 text-white border-emerald-600', nokta: 'bg-emerald-500' },
  bilgi: { yumusak: 'bg-sky-500/15 text-sky-300 border-sky-500/30', dolu: 'bg-sky-600 text-white border-sky-600', nokta: 'bg-sky-500' },
  mor: { yumusak: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30', dolu: 'bg-indigo-600 text-white border-indigo-600', nokta: 'bg-indigo-500' },
  notr: { yumusak: 'bg-bg-3 text-t-2 border-line', dolu: 'bg-bg-3 text-t-1 border-line-bright', nokta: 'bg-slate-500' },
};
</script>

<template>
  <span class="inline-flex items-center gap-1.5 border font-semibold whitespace-nowrap"
    :class="[(TUR[tur] || TUR.notr)[dolu ? 'dolu' : 'yumusak'], sekil === 'pill' ? 'rounded-full' : 'rounded-md',
             boyut === 'xs' ? 'px-1.5 py-0.5 text-[10px]' : boyut === 'md' ? 'px-3 py-1 text-xs' : 'px-2.5 py-0.5 text-[11px]', mono ? 'font-mono' : '']">
    <span v-if="nokta" class="relative flex h-2 w-2 shrink-0">
      <span v-if="nabiz" class="absolute inline-flex h-full w-full rounded-full opacity-60 animate-ping" :class="(TUR[tur] || TUR.notr).nokta"></span>
      <span class="relative inline-flex h-2 w-2 rounded-full" :class="(TUR[tur] || TUR.notr).nokta"></span>
    </span>
    <FaIcon v-if="ikon" :icon="ikon" class="h-3 w-3" />
    <slot />
  </span>
</template>
