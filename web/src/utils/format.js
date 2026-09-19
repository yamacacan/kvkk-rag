export const kisalt = (s, n) => { s = String(s ?? ''); return s.length > n ? s.slice(0, n) + '…' : s; };
export const sayi = (n) => (n ?? 0).toLocaleString('tr-TR');
export const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
export const tarih = (iso) => (iso ? new Date(iso).toLocaleString('tr-TR') : '');

// Bulgu seviyeleri: sinif adlari sabit yazilir ki Tailwind derlemede gorsun
export const SEVIYE = {
  kritik: { etiket: 'KRİTİK', renk: 'rose',   rozet: 'bg-rose-500/15 text-rose-400 border-rose-500/30',   kutu: 'border-rose-500/20',   metin: 'text-rose-400' },
  yuksek: { etiket: 'YÜKSEK', renk: 'amber',  rozet: 'bg-amber-500/15 text-amber-400 border-amber-500/30', kutu: 'border-amber-500/20',  metin: 'text-amber-400' },
  orta:   { etiket: 'ORTA',   renk: 'yellow', rozet: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30', kutu: 'border-yellow-500/20', metin: 'text-yellow-400' },
  dusuk:  { etiket: 'DÜŞÜK',  renk: 'blue',   rozet: 'bg-blue-500/15 text-blue-400 border-blue-500/30',   kutu: 'border-blue-500/20',   metin: 'text-blue-400' },
};
export const seviye = (k) => SEVIYE[k] || SEVIYE.dusuk;

let gecikmeZ;
export function gecikmeli(fn, ms = 320) { clearTimeout(gecikmeZ); gecikmeZ = setTimeout(fn, ms); }

export function debounce(fn, ms = 320) {
  let z;
  return (...a) => { clearTimeout(z); z = setTimeout(() => fn(...a), ms); };
}

// "3 dk önce" gibi goreli zaman; 7 gunden eskisi tarih olarak
export function goreliZaman(iso) {
  if (!iso) return '';
  const fark = (Date.now() - new Date(iso).getTime()) / 1000;
  if (fark < 45) return 'az önce';
  if (fark < 3600) return `${Math.round(fark / 60)} dk önce`;
  if (fark < 86400) return `${Math.round(fark / 3600)} sa önce`;
  if (fark < 7 * 86400) return `${Math.round(fark / 86400)} gün önce`;
  return new Date(iso).toLocaleDateString('tr-TR');
}
