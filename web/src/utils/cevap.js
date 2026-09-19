// Asistan cevabinin sinirli markdown -> HTML donusumu. LLM ciktisi guvenilmez
// kabul edilir: once kacislanir, sonra sinirli bicimlendirme uygulanir.
import { esc } from './format';

// Dayanak kunyesini baglayiciligina gore siniflar: kanun/yonetmelik zorunlu,
// kurul karari ara, rehber ve karar ozeti tavsiye.
export function kunyeSinifi(m) {
  const t = m.toLocaleLowerCase('tr');
  if (/(kanun|yönetmelik|yonetmelik|tebliğ|teblig|ilke)/.test(t)) return 'k-kanun';
  if (/(rehber|özet|ozet)/.test(t)) return 'k-tavsiye';
  return 'k-kurul';
}

function satirIci(s) {
  return esc(s)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/`([^`]+)`/g, '<code class="font-mono text-[11px] px-1 rounded bg-[var(--bg-inset)]">$1</code>')
    // [Kanun m.5/2-ç] gibi dayanaklari tiklanabilir kunyeye cevir
    .replace(/\[([^\]]{2,80})\]/g, (_, ic) => ic.split(/\s*,\s*/)
      .map((p) => `<span class="kunye ${kunyeSinifi(p)}" data-kunye="${esc(p)}">${esc(p)}</span>`)
      .join(' '));
}

function blokIcerik(satirlar) {
  const out = [];
  let liste = [];
  const listeBitir = () => { if (liste.length) { out.push(`<ul>${liste.join('')}</ul>`); liste = []; } };
  satirlar.forEach((ham) => {
    const s = ham.trim();
    if (!s) { listeBitir(); return; }
    const md = s.match(/^[-*•]\s+(.*)$/);
    if (md) { liste.push(`<li>${satirIci(md[1])}</li>`); return; }
    listeBitir();
    out.push(`<p>${satirIci(s.replace(/^#{1,6}\s*/, ''))}</p>`);
  });
  listeBitir();
  return out.join('');
}

const BLOK_TIPI = [
  { re: /^\**\s*zorunlu\b/i, sinif: 'blok-zorunlu', rozet: 'Zorunlu', ad: 'Mevzuat gereği', not: 'bağlayıcı — uyulması zorunlu' },
  { re: /^\**\s*(iyi uygulama|tavsiye)/i, sinif: 'blok-tavsiye', rozet: 'Tavsiye', ad: 'İyi uygulama / Kurul yorumu', not: 'bağlayıcı değil — uygulamayı gösterir' },
];

export function cevapHtml(metin) {
  if (!metin) return '<span class="text-[var(--t2)]">Cevap üretilemedi.</span>';
  // Yatay cizgiden sonrasi genelde kapanis bilgilendirmesi
  const parcalar = metin.split(/\n\s*---+\s*\n/);
  const govde = parcalar[0];
  const kuyruk = parcalar.slice(1).join('\n');

  const bloklar = [];
  let acik = null, tampon = [];
  const kapat = () => {
    if (!tampon.length) return;
    const ic = blokIcerik(tampon);
    if (acik) {
      bloklar.push(`<div class="blok ${acik.sinif}"><div class="blok-bas">
        <span class="blok-rozet">${acik.rozet}</span>
        <span class="blok-ad">${acik.ad}</span>
        <span class="blok-not">· ${acik.not}</span></div>${ic}</div>`);
    } else { bloklar.push(ic); }
    tampon = [];
  };
  govde.split('\n').forEach((satir) => {
    const cip = satir.replace(/^#{1,6}\s*/, '').trim();
    const tip = BLOK_TIPI.find((t) => t.re.test(cip) && cip.length < 60);
    if (tip) { kapat(); acik = tip; return; }
    tampon.push(satir);
  });
  kapat();

  let html = bloklar.join('');
  if (kuyruk.trim()) html += `<div class="serh">${blokIcerik(kuyruk.split('\n'))}</div>`;
  return html;
}

// Kaynak kartinin arama anahtari: "m.6 2018/32 belge adi" (kucuk harf)
export function kaynakAnahtari(s) {
  return [s.madde_no ? 'm.' + s.madde_no : '', s.karar_no || '', s.belge_adi || '']
    .filter(Boolean).join(' ').toLocaleLowerCase('tr');
}

// Kunye ipucundan hangi kaynak kartinin eslestigini bulur
export function kunyeHedefi(ipucu, anahtarlar) {
  const t = (ipucu || '').toLocaleLowerCase('tr');
  const madde = (t.match(/m\.\s*(\d+)/) || [])[1];
  const karar = (t.match(/(\d{4}\/\d+)/) || [])[1];
  return anahtarlar.findIndex((a) => {
    if (karar) return a.includes(karar);
    if (madde) return a.includes('m.' + madde);
    return false;
  });
}
