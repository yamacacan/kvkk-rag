const API = location.origin;
const $ = (id) => document.getElementById(id);

const state = {
  view: 'envanter', offset: 0, limit: 50, tab: 'tum',
  filtre: { birim: '', faaliyet: '', veri_kategorisi: '', hukuki_sebep: '', seviye: '', arama: '' },
  ozet: null,
  secili: new Set(),
};

const SEVIYE = {
  kritik: { renk: 'rose', etiket: 'KRİTİK' },
  yuksek: { renk: 'amber', etiket: 'YÜKSEK' },
  orta:   { renk: 'yellow', etiket: 'ORTA' },
  dusuk:  { renk: 'blue', etiket: 'DÜŞÜK' },
};

const TABS = [
  { id: 'tum',    ad: 'Tüm Kayıtlar',       nokta: 'bg-indigo-400', filtre: {} },
  { id: 'kritik', ad: 'Kritik',             nokta: 'bg-rose-500',   filtre: { seviye: 'kritik' } },
  { id: 'yuksek', ad: 'Yüksek',             nokta: 'bg-amber-400',  filtre: { seviye: 'yuksek' } },
  { id: 'ozel',   ad: 'Özel Nitelikli Risk', nokta: 'bg-fuchsia-400', filtre: { seviye: 'kritik', arama: 'Ceza Mahkumiyeti' } },
];

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const kisalt = (s, n) => { s = String(s ?? ''); return s.length > n ? s.slice(0, n) + '…' : s; };
const sayi = (n) => (n ?? 0).toLocaleString('tr-TR');

async function api(path, opts) {
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

// ---------- sağlık ----------
async function saglik() {
  try {
    const h = await api('/api/health');
    $('health-dot').className = 'w-2 h-2 rounded-full bg-emerald-500';
    $('health-text').textContent = `${h.default_llm} · w=${h.authority_weight}`;
  } catch {
    $('health-dot').className = 'w-2 h-2 rounded-full bg-rose-500';
    $('health-text').textContent = 'API bağlantısı yok';
  }
}

// ---------- KPI ----------
function kpiKart(baslik, deger, alt, renk, rozet) {
  return `<div class="p-4 rounded-xl border border-[var(--line)] bg-[var(--bg-2)]">
    <div class="flex items-center justify-between mb-2">
      <span class="text-xs font-semibold uppercase tracking-wider text-[var(--t2)]">${baslik}</span>
      ${rozet ? `<span class="text-xs font-bold px-2 py-0.5 rounded bg-${renk}-500/20 text-${renk}-300">${rozet}</span>` : ''}
    </div>
    <p class="text-2xl font-mono font-extrabold text-${renk}-400">${deger}</p>
    <p class="text-[11px] text-[var(--t2)] mt-0.5">${alt}</p>
  </div>`;
}

async function ozetYukle() {
  const o = await api('/api/inventory/summary');
  state.ozet = o;
  const uyum = (o.uyum_orani * 100).toFixed(1);
  $('kpi').innerHTML =
    kpiKart('Envanter Kaydı', sayi(o.satir), `${o.birim.length}+ birim, ${o.faaliyet.length}+ faaliyet`, 'indigo', 'VERBİS') +
    kpiKart('Kritik Bulgu', sayi(o.seviye.kritik || 0), 'mevzuata aykırılık riski', 'rose', 'acil') +
    kpiKart('Yüksek Bulgu', sayi(o.seviye.yuksek || 0), 'tamamlanması gereken alanlar', 'amber', null) +
    kpiKart('Uyum Oranı', `%${uyum}`, `${sayi(o.temiz_satir)} kayıt bulgusuz`, uyum > 50 ? 'emerald' : 'rose', null);

  $('kayit-rozet').textContent = `${sayi(o.satir)} kayıt`;
  doldurSecenek('f-birim', o.birim, 'Tüm birimler');
  doldurSecenek('f-faaliyet', o.faaliyet, 'Tüm faaliyetler');
  doldurSecenek('f-kategori', o.veri_kategorisi, 'Tüm kategoriler');
  tabCiz();
}

function doldurSecenek(id, liste, bos) {
  const el = $(id);
  el.innerHTML = `<option value="">${bos}</option>` +
    liste.map((x) => `<option value="${esc(x.deger)}">${esc(kisalt(x.deger, 38))} (${x.adet})</option>`).join('');
}

function tabCiz() {
  const o = state.ozet;
  const say = { tum: o.satir, kritik: o.seviye.kritik || 0, yuksek: o.seviye.yuksek || 0, ozel: o.kod['ENV-004'] || 0 };
  $('tabs').innerHTML = TABS.map((t) => {
    const aktif = state.tab === t.id;
    return `<button data-tab="${t.id}" class="tab-btn flex items-center gap-2 px-3 py-2 text-xs whitespace-nowrap border-b-2 ${aktif ? 'border-indigo-500 text-white font-bold' : 'border-transparent text-[var(--t1)] hover:text-white font-semibold'}">
      <span class="w-1.5 h-1.5 rounded-full ${t.nokta}"></span>${t.ad}
      <span class="rounded-full bg-[var(--bg-3)] px-1.5 text-[10.5px] font-mono">${sayi(say[t.id])}</span></button>`;
  }).join('');
  document.querySelectorAll('.tab-btn').forEach((b) => b.onclick = () => {
    state.tab = b.dataset.tab;
    const t = TABS.find((x) => x.id === state.tab);
    state.filtre = { birim: '', faaliyet: '', veri_kategorisi: '', hukuki_sebep: '', seviye: '', arama: '', ...t.filtre };
    $('f-seviye').value = state.filtre.seviye || '';
    $('q-genel').value = state.filtre.arama || '';
    state.offset = 0; tabCiz(); tabloYukle();
  });
}

// ---------- tablo ----------
function rozetSeviye(sev, adet) {
  const s = SEVIYE[sev] || SEVIYE.dusuk;
  return `<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-${s.renk}-500/15 text-${s.renk}-400 border border-${s.renk}-500/30">${s.etiket} ${adet}</span>`;
}

function satirCiz(r) {
  const sev = {};
  (r.bulgular || []).forEach((b) => sev[b.seviye] = (sev[b.seviye] || 0) + 1);
  const kritikVar = sev.kritik > 0;
  const bulguOzet = (r.bulgular || []).slice(0, 3).map((b) =>
    `<div class="text-[10.5px] leading-snug"><span class="text-slate-300">${esc(b.baslik)}</span>
      <span class="text-[var(--t2)] font-mono"> · ${esc(kisalt(b.dayanak, 42))}</span></div>`).join('');
  const kalan = (r.bulgular || []).length - 3;

  return `<tr class="hover:bg-[var(--bg-3)]/60 transition-colors group ${kritikVar ? 'bg-rose-500/5 border-l-2 border-l-rose-500' : 'bg-[var(--bg-2)]/30'}">
    <td class="py-3 px-2 text-center"><input type="checkbox" class="sec-satir rounded border-[var(--line-2)] bg-[var(--bg-inset)] text-indigo-600 focus:ring-0 cursor-pointer" data-satir="${r.satir_no}" ${state.secili.has(r.satir_no) ? 'checked' : ''}></td>
    <td class="py-3 px-3 font-mono text-[11px] text-indigo-400 font-bold">${r.satir_no}</td>
    <td class="py-3 px-3"><span class="text-[11px] font-semibold text-white block leading-tight">${esc(kisalt(r.birim, 34))}</span></td>
    <td class="py-3 px-3"><span class="text-[11px] text-slate-300 block leading-tight">${esc(kisalt(r.faaliyet, 38))}</span></td>
    <td class="py-3 px-3"><span class="inline-block px-1.5 py-0.5 rounded text-[10.5px] font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">${esc(kisalt(r.veri_kategorisi, 22))}</span></td>
    <td class="py-3 px-3"><span class="text-[10.5px] text-[var(--t1)] leading-snug block">${esc(kisalt(r.hukuki_sebep, 76))}</span></td>
    <td class="py-3 px-3">${r.saklama_suresi
      ? `<span class="text-[10.5px] font-mono text-slate-300">${esc(kisalt(r.saklama_suresi, 18))}</span>`
      : `<span class="text-[10.5px] text-rose-400 font-semibold">— yok —</span>`}</td>
    <td class="py-3 px-3"><span class="font-mono text-xs font-extrabold ${kritikVar ? 'text-rose-400' : 'text-amber-400'}">${r.risk_skoru}</span></td>
    <td class="py-3 px-3">
      <div class="flex flex-wrap gap-1 mb-1">${Object.entries(sev).map(([k, v]) => rozetSeviye(k, v)).join('')}</div>
      ${bulguOzet}${kalan > 0 ? `<div class="text-[10px] text-[var(--t2)] mt-0.5">+${kalan} bulgu daha</div>` : ''}
    </td>
    <td class="py-3 px-3 text-right">
      <button class="detay-btn p-1 rounded text-[var(--t2)] hover:text-white hover:bg-[var(--bg-3)]" data-satir="${r.satir_no}" title="Detay">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
      </button>
    </td></tr>`;
}

async function tabloYukle() {
  const p = new URLSearchParams({ limit: state.limit, offset: state.offset });
  Object.entries(state.filtre).forEach(([k, v]) => { if (v) p.set(k, v); });
  $('tbody').innerHTML = `<tr><td colspan="10" class="py-16 text-center text-[var(--t2)] text-xs">Yükleniyor…</td></tr>`;
  try {
    const d = await api('/api/inventory?' + p);
    $('sonuc-say').textContent = sayi(d.filtrelenmis);
    $('tbody').innerHTML = d.satirlar.length
      ? d.satirlar.map(satirCiz).join('')
      : `<tr><td colspan="10" class="py-16 text-center text-[var(--t2)] text-xs">Filtreye uyan kayıt yok.</td></tr>`;
    const son = Math.min(state.offset + state.limit, d.filtrelenmis);
    $('sayfa-bilgi').innerHTML = `Toplam <span class="font-mono font-bold text-white">${sayi(d.toplam)}</span> kayıttan
      <span class="font-mono text-white">${sayi(state.offset + 1)} - ${sayi(son)}</span> arası
      (<span class="text-indigo-400 font-semibold font-mono">${sayi(d.filtrelenmis)} filtrelenmiş</span>)`;
    sayfalamaCiz(d.filtrelenmis);
    rozetleriCiz();
    document.querySelectorAll('.detay-btn').forEach((b) => b.onclick = () => formAc(d.satirlar.find((x) => x.satir_no == b.dataset.satir)));
    document.querySelectorAll('.sec-satir').forEach((c) => c.onchange = () => {
      const n = +c.dataset.satir;
      c.checked ? state.secili.add(n) : state.secili.delete(n);
      secimGuncelle();
    });
    state.sonSayfa = d.satirlar.map((x) => x.satir_no);
    secimGuncelle();
  } catch (e) {
    $('tbody').innerHTML = `<tr><td colspan="10" class="py-16 text-center text-rose-400 text-xs">Hata: ${esc(e.message)}</td></tr>`;
  }
}

function sayfalamaCiz(toplam) {
  const sayfa = Math.floor(state.offset / state.limit) + 1;
  const son = Math.max(1, Math.ceil(toplam / state.limit));
  const btn = (etiket, hedef, aktif, pasif) =>
    `<button ${pasif ? 'disabled' : ''} data-offset="${hedef}" class="sayfa-btn h-8 ${etiket.length > 2 ? 'px-2.5' : 'w-8'} rounded-md text-xs font-semibold
      ${aktif ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30' : 'border border-[var(--line)] bg-[var(--bg-3)] text-[var(--t1)] hover:text-white'}
      ${pasif ? 'opacity-40 cursor-not-allowed' : ''}">${etiket}</button>`;

  let h = btn('Önceki', (sayfa - 2) * state.limit, false, sayfa === 1);
  const bas = Math.max(1, Math.min(sayfa - 1, son - 2));
  for (let i = bas; i <= Math.min(bas + 2, son); i++) h += btn(String(i), (i - 1) * state.limit, i === sayfa, false);
  if (son > bas + 2) h += `<span class="px-1 text-[var(--t2)] text-xs font-mono">…</span>` + btn(String(son), (son - 1) * state.limit, false, false);
  h += btn('Sonraki', sayfa * state.limit, false, sayfa >= son);

  $('sayfalama').innerHTML = h;
  document.querySelectorAll('.sayfa-btn').forEach((b) => b.onclick = () => {
    if (b.disabled) return;
    state.offset = Math.max(0, +b.dataset.offset); tabloYukle();
  });
}

function rozetleriCiz() {
  const etiket = { birim: 'Birim', faaliyet: 'Faaliyet', veri_kategorisi: 'Kategori', hukuki_sebep: 'Sebep', seviye: 'Risk', arama: 'Arama' };
  const aktif = Object.entries(state.filtre).filter(([, v]) => v);
  $('rozetler').innerHTML = aktif.length
    ? `<span class="text-[11px] font-bold uppercase tracking-wider text-[var(--t2)] mr-1">Filtreler:</span>` +
      aktif.map(([k, v]) => `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] bg-indigo-500/15 border border-indigo-500/30 text-indigo-300">
        <span>${etiket[k]}:</span><strong class="text-white">${esc(kisalt(v, 26))}</strong>
        <button class="kaldir hover:text-white ml-0.5" data-k="${k}">✕</button></span>`).join('') +
      `<button id="temizle" class="text-[11px] font-semibold text-rose-400 hover:text-rose-300 hover:underline px-1.5">Tümünü temizle</button>`
    : '';
  document.querySelectorAll('.kaldir').forEach((b) => b.onclick = () => { filtreAta(b.dataset.k, ''); });
  if ($('temizle')) $('temizle').onclick = sifirla;
}

function detayGoster(r) {
  if (!r) return;
  const alan = (ad, v) => `<div class="py-1.5 border-b border-[var(--line)]"><span class="text-[10px] uppercase tracking-wider text-[var(--t2)] block">${ad}</span>
    <span class="text-xs ${v ? 'text-white' : 'text-rose-400'}">${esc(v || '— boş —')}</span></div>`;
  const bulgular = (r.bulgular || []).map((b) => {
    const s = SEVIYE[b.seviye] || SEVIYE.dusuk;
    return `<div class="p-3 rounded-lg bg-[var(--bg-inset)] border border-${s.renk}-500/20 mb-2">
      <div class="flex items-center gap-2 mb-1">
        <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-${s.renk}-500/15 text-${s.renk}-400">${s.etiket}</span>
        <span class="font-mono text-[10px] text-[var(--t2)]">${b.kod}</span>
        <span class="text-xs font-semibold text-white">${esc(b.baslik)}</span></div>
      <p class="text-[11px] text-[var(--t1)] leading-snug mb-1">${esc(b.aciklama)}</p>
      <p class="text-[10.5px] font-mono text-indigo-400">Dayanak: ${esc(b.dayanak)}</p></div>`;
  }).join('');

  const d = document.createElement('div');
  d.className = 'fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-6';
  d.innerHTML = `<div class="bg-[var(--bg-2)] border border-[var(--line)] rounded-2xl max-w-4xl w-full max-h-[85vh] overflow-y-auto shadow-2xl">
    <div class="sticky top-0 bg-[var(--bg-1)] border-b border-[var(--line)] px-5 py-3 flex items-center justify-between">
      <h3 class="text-sm font-bold text-white">Envanter Satırı ${r.satir_no} · Risk ${r.risk_skoru}</h3>
      <button class="kapat text-[var(--t2)] hover:text-white text-lg leading-none">✕</button></div>
    <div class="p-5 grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div>${alan('Birim', r.birim)}${alan('Faaliyet', r.faaliyet)}${alan('Veri Kategorisi', r.veri_kategorisi)}
        ${alan('Kişisel Veri', r.kisisel_veri)}${alan('Özel Nitelikli Veri', r.ozel_nitelikli_veri)}
        ${alan('Veri Konusu Kişi Grubu', r.kisi_grubu)}${alan('İşleme Amacı', r.isleme_amaci)}</div>
      <div>${alan('Hukuki Sebep', r.hukuki_sebep)}${alan('Saklama Süresi', r.saklama_suresi)}
        ${alan('İmha Yöntemi', r.imha_yontemi)}${alan('Alıcı Grupları', r.alici_grubu)}
        ${alan('Yurt Dışı Aktarım', r.yurt_disi_aktarim)}${alan('Teknik Tedbirler', r.teknik_tedbir)}
        ${alan('İdari Tedbirler', r.idari_tedbir)}</div>
    </div>
    <div class="px-5 pb-5"><h4 class="text-xs font-bold text-white mb-2">Uyum Bulguları (${(r.bulgular || []).length})</h4>${bulgular || '<p class="text-xs text-emerald-400">Bulgu yok.</p>'}</div>
  </div>`;
  document.body.appendChild(d);
  d.onclick = (e) => { if (e.target === d || e.target.classList.contains('kapat')) d.remove(); };
}

// ---------- filtreler ----------
function filtreAta(k, v) {
  state.filtre[k] = v; state.offset = 0;
  const map = { birim: 'f-birim', faaliyet: 'f-faaliyet', veri_kategorisi: 'f-kategori', hukuki_sebep: 'f-sebep', seviye: 'f-seviye', arama: 'q-genel' };
  if ($(map[k])) $(map[k]).value = v;
  tabloYukle();
}

function sifirla() {
  state.filtre = { birim: '', faaliyet: '', veri_kategorisi: '', hukuki_sebep: '', seviye: '', arama: '' };
  state.offset = 0; state.tab = 'tum';
  ['f-birim', 'f-faaliyet', 'f-kategori', 'f-sebep', 'f-seviye', 'q-genel'].forEach((id) => $(id).value = '');
  tabCiz(); tabloYukle();
}

let gecikme;
function gecikmeli(fn) { clearTimeout(gecikme); gecikme = setTimeout(fn, 320); }

// ---------- toplu seçim ----------
function secimGuncelle() {
  const n = state.secili.size;
  $('toplu-cubuk').hidden = n === 0;
  $('secim-say').textContent = sayi(n);
  const sayfa = state.sonSayfa || [];
  const hepsi = sayfa.length > 0 && sayfa.every((x) => state.secili.has(x));
  $('sec-hepsi').checked = hepsi;
  $('sec-hepsi').indeterminate = !hepsi && sayfa.some((x) => state.secili.has(x));
}

function filtreQS(ek = {}) {
  const p = new URLSearchParams();
  Object.entries({ ...state.filtre, ...ek }).forEach(([k, v]) => { if (v) p.set(k, v); });
  return p;
}

async function topluSil() {
  const n = state.secili.size;
  if (!n) return;
  if (!confirm(`${n} kayıt kalıcı olarak silinecek. Onaylıyor musunuz?`)) return;
  try {
    const d = await api('/api/inventory/bulk-delete', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ satir_no: [...state.secili] }),
    });
    state.secili.clear();
    await ozetYukle(); await tabloYukle();
    alert(`${d.adet} kayıt silindi.`);
  } catch (e) { alert('Silinemedi: ' + e.message); }
}

async function tumunuSec() {
  // Filtreye uyan tüm satırları seçer (sayfadakiler değil)
  const p = filtreQS({ limit: 10000, offset: 0 });
  const d = await api('/api/inventory?' + p);
  d.satirlar.forEach((r) => state.secili.add(r.satir_no));
  document.querySelectorAll('.sec-satir').forEach((c) => c.checked = true);
  secimGuncelle();
}

function excelIndir(sadeceSecili = false) {
  const p = filtreQS({ kurum: 'ÖRNEK TEKNOLOJİ A.Ş.' });
  if (sadeceSecili && state.secili.size) p.set('arama', '');
  window.open(API + '/api/inventory/export?' + p, '_blank');
}

// ---------- asistan ----------
const ORNEKLER = [
  'Çalışanların parmak izi ile mesai takibi yapabilir miyim?',
  'Bana gelen başvuruyu kaç gün içinde cevaplamalıyım?',
  'İK olarak adayların referans kişilerinin telefon numarasını almayı planlıyoruz',
  'Pazarlama birimimiz müşterilerin doğum tarihini kampanya için kaydediyor, uygun mu?',
];

// Dayanak künyesini bağlayıcılığına göre sınıflar: kanun/yönetmelik zorunlu,
// kurul kararı ara, rehber ve karar özeti tavsiye.
function kunyeSinifi(m) {
  const t = m.toLocaleLowerCase('tr');
  if (/(kanun|yönetmelik|yonetmelik|tebliğ|teblig|ilke)/.test(t)) return 'k-kanun';
  if (/(rehber|özet|ozet)/.test(t)) return 'k-tavsiye';
  if (/karar/.test(t)) return 'k-kurul';
  return 'k-kurul';
}

// LLM çıktısı güvenilmez kabul edilir: önce kaçışlanır, sonra sınırlı markdown uygulanır.
function satirIci(s) {
  return esc(s)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/`([^`]+)`/g, '<code class="font-mono text-[11px] px-1 rounded bg-[var(--bg-inset)]">$1</code>')
    // [Kanun m.5/2-ç] gibi dayanakları tıklanabilir künyeye çevir
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
  { re: /^\**\s*zorunlu\b/i, sinif: 'blok-zorunlu', rozet: 'Zorunlu',
    ad: 'Mevzuat gereği', not: 'bağlayıcı — uyulması zorunlu' },
  { re: /^\**\s*(iyi uygulama|tavsiye)/i, sinif: 'blok-tavsiye', rozet: 'Tavsiye',
    ad: 'İyi uygulama / Kurul yorumu', not: 'bağlayıcı değil — uygulamayı gösterir' },
];

function cevapCiz(metin) {
  if (!metin) return '<span class="text-[var(--t2)]">Cevap üretilemedi.</span>';
  // Yatay çizgiden sonrası genelde kapanış bilgilendirmesi
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

// ---------- sohbet ----------
// Gecmis tarayicida tutulur; sunucu her turda tam gecmisi alir (durumsuz API).
const chat = { mesajlar: [], bekliyor: false };

function kaynakKarti(s, i) {
  const zorunlu = (s.baglayicilik || '').startsWith('zorunlu');
  const et = s.madde_no ? `m.${s.madde_no}` : (s.karar_no || '');
  const anahtar = [s.madde_no ? 'm.' + s.madde_no : '', s.karar_no || '', s.belge_adi || '']
    .filter(Boolean).join(' ').toLocaleLowerCase('tr');
  return `<div class="px-3 py-2 hover:bg-[var(--bg-3)]/40 transition-colors" data-kaynak="${esc(anahtar)}">
    <div class="flex items-center gap-2 mb-0.5">
      <span class="font-mono text-[10px] text-[var(--t2)]">[${i + 1}]</span>
      <span class="text-[10px] font-bold px-1.5 py-0.5 rounded ${zorunlu ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/15 text-amber-400 border border-amber-500/30'}">${zorunlu ? 'ZORUNLU' : 'TAVSİYE'}</span>
      <span class="text-[11px] font-semibold text-white">${esc(kisalt(s.belge_adi, 58))}</span>
      ${et ? `<span class="font-mono text-[10.5px] text-indigo-400">${esc(et)}</span>` : ''}
    </div>
    <p class="text-[11px] text-[var(--t1)] leading-snug">${esc(kisalt(s.eslesen_parca || s.text, 220))}</p></div>`;
}

function envanterKarti(env) {
  const o = env?.oneri;
  if (!o) return '';
  const satir = (r) => `<div class="text-[11px] text-slate-300 leading-snug">
      <span class="font-mono text-indigo-400">#${r.satir_no}</span> ${esc(kisalt(r.kisisel_veri, 40))}
      <span class="text-[var(--t2)]">· ${esc(kisalt(r.faaliyet, 40))} · ${esc(kisalt(r.birim, 28))}</span></div>`;
  if (o.tip === 'envanterde_var') {
    return `<div class="mt-3 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/25">
      <div class="flex items-center gap-2 mb-1.5">
        <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">ENVANTER</span>
        <span class="text-[11px] font-semibold text-white">"${esc(o.kisisel_veri)}" envanterde kayıtlı</span></div>
      <div class="space-y-0.5">${(env.eslesen || []).map(satir).join('')}</div>
      <button class="env-ac mt-2 text-[11px] font-semibold text-emerald-300 hover:text-white" data-satir="${env.eslesen?.[0]?.satir_no || ''}">Kaydı aç →</button>
    </div>`;
  }
  return `<div class="mt-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/25">
    <div class="flex items-center gap-2 mb-1.5">
      <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">ENVANTER</span>
      <span class="text-[11px] font-semibold text-white">"${esc(o.kisisel_veri)}" envanterde birebir kayıtlı değil</span></div>
    ${(env.eslesen || []).length ? `<p class="text-[10.5px] text-[var(--t2)] mb-1">Yakın kayıtlar (aynı değil):</p><div class="space-y-0.5 mb-2">${env.eslesen.map(satir).join('')}</div>` : ''}
    <p class="text-[11px] text-slate-200 mb-2">Bu veriyi envantere eklemek ister misiniz? Alanlar mevzuat dayanağıyla önerilir, kaydetmeden önce gözden geçirirsiniz.</p>
    <button class="env-ekle px-3 py-1.5 text-xs font-bold rounded-lg bg-amber-500 hover:bg-amber-400 text-black"
      data-veri="${esc(o.kisisel_veri || '')}" data-birim="${esc(o.birim || '')}" data-faaliyet="${esc(o.faaliyet || '')}">Envantere ekle</button>
  </div>`;
}

function baloncuk(rol, icHtml, ek = '') {
  const kullanici = rol === 'user';
  return `<div class="flex ${kullanici ? 'justify-end' : 'justify-start'}">
    <div class="${kullanici ? 'bg-indigo-600 text-white rounded-2xl rounded-br-sm max-w-[75%]' : 'bg-[var(--bg-inset)] border border-[var(--line)] rounded-2xl rounded-bl-sm max-w-[92%]'} px-4 py-3 text-sm leading-relaxed">
      ${icHtml}${ek}</div></div>`;
}

function chatCiz() {
  const kutu = $('chat-mesajlar');
  if (!chat.mesajlar.length) { $('chat-bos').hidden = false; kutu.querySelectorAll('.msg').forEach((e) => e.remove()); return; }
  $('chat-bos').hidden = true;
  kutu.querySelectorAll('.msg').forEach((e) => e.remove());
  chat.mesajlar.forEach((m, idx) => {
    const w = document.createElement('div'); w.className = 'msg';
    if (m.role === 'user') { w.innerHTML = baloncuk('user', esc(m.content).replace(/\n/g, '<br>')); }
    else if (m.bekliyor) { w.innerHTML = baloncuk('assistant', '<span class="text-[var(--t2)]">Kaynaklar taranıyor ve cevap üretiliyor…</span>'); }
    else if (m.hata) { w.innerHTML = baloncuk('assistant', `<span class="text-rose-400">Hata: ${esc(m.hata)}</span>`); }
    else {
      const zor = (m.sources || []).filter((s) => (s.baglayicilik || '').startsWith('zorunlu')).length;
      const kaynaklar = (m.sources || []).length ? `
        <details class="mt-3 group">
          <summary class="cursor-pointer text-[10.5px] font-semibold text-[var(--t2)] hover:text-white select-none">
            ${m.sources.length} kaynak · ${zor} zorunlu, ${m.sources.length - zor} tavsiye</summary>
          <div class="mt-2 rounded-lg border border-[var(--line)] divide-y divide-[var(--line)] bg-[var(--bg-2)]" data-kaynaklar="${idx}">
            ${m.sources.map(kaynakKarti).join('')}</div></details>` : '';
      w.innerHTML = baloncuk('assistant',
        `<div class="cevap-govde text-slate-200" data-cevap="${idx}">${cevapCiz(m.content)}</div>`,
        envanterKarti(m.envanter) + kaynaklar);
    }
    kutu.appendChild(w);
  });
  kutu.querySelectorAll('.env-ekle').forEach((b) => b.onclick = () =>
    formAc(null, { veri: b.dataset.veri, birim: b.dataset.birim, faaliyet: b.dataset.faaliyet }));
  kutu.querySelectorAll('.env-ac').forEach((b) => b.onclick = async () => {
    if (!b.dataset.satir) return;
    try { formAc((await api('/api/inventory/' + b.dataset.satir)).satir); }
    catch (e) { alert('Kayıt açılamadı: ' + e.message); }
  });
  kunyeleriBagla();
  kutu.scrollTop = kutu.scrollHeight;
}

async function chatGonder(metin) {
  metin = (metin || '').trim();
  if (!metin || chat.bekliyor) return;
  chat.bekliyor = true; $('btn-gonder').disabled = true;
  chat.mesajlar.push({ role: 'user', content: metin });
  chat.mesajlar.push({ role: 'assistant', content: '', bekliyor: true });
  $('chat-girdi').value = ''; girdiBoyut();
  chatCiz();
  try {
    const gecmis = chat.mesajlar.filter((m) => !m.bekliyor && !m.hata).map((m) => ({ role: m.role, content: m.content }));
    const d = await api('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: gecmis, limit: 10 }),
    });
    chat.mesajlar[chat.mesajlar.length - 1] = { role: 'assistant', content: d.answer, sources: d.sources, envanter: d.envanter };
  } catch (e) {
    chat.mesajlar[chat.mesajlar.length - 1] = { role: 'assistant', content: '', hata: e.message };
  } finally {
    chat.bekliyor = false; $('btn-gonder').disabled = false; chatCiz(); $('chat-girdi').focus();
  }
}

function girdiBoyut() {
  const t = $('chat-girdi'); t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 160) + 'px';
}

// Cevaptaki dayanak künyesine tıklayınca ilgili kaynak kartına götürür.
function kunyeleriBagla() {
  document.querySelectorAll('#chat-mesajlar [data-cevap]').forEach((cevapEl) => {
  const idx = cevapEl.dataset.cevap;
  const kartlar = [...document.querySelectorAll(`#chat-mesajlar [data-kaynaklar="${idx}"] [data-kaynak]`)];
  cevapEl.querySelectorAll('.kunye').forEach((el) => {
    const ipucu = (el.dataset.kunye || '').toLocaleLowerCase('tr');
    // "Kanun m.6/1" -> "m.6"; "Karar 2018/32" -> "2018/32"
    const madde = (ipucu.match(/m\.\s*(\d+)/) || [])[1];
    const karar = (ipucu.match(/(\d{4}\/\d+)/) || [])[1];
    const hedef = kartlar.find((k) => {
      const a = k.dataset.kaynak;
      if (karar) return a.includes(karar);
      if (madde) return a.includes('m.' + madde + ' ') || a.endsWith('m.' + madde) || a.includes('m.' + madde);
      return false;
    });
    if (!hedef) { el.style.cursor = 'default'; el.title = 'Bu dayanak kaynak listesinde eşleşmedi'; return; }
    el.title = 'Kaynağa git';
    el.onclick = () => {
      // Kaynak listesi kapaliysa once ac
      const details = hedef.closest('details'); if (details) details.open = true;
      hedef.scrollIntoView({ behavior: 'smooth', block: 'center' });
      kartlar.forEach((k) => k.classList.remove('kaynak-vurgu'));
      hedef.classList.add('kaynak-vurgu');
      setTimeout(() => hedef.classList.remove('kaynak-vurgu'), 2200);
    };
  });
  });
}

// ---------- graf ----------
async function grafYukle() {
  const d = await api('/api/graph/risk?limit=10');
  $('graf-risk').innerHTML = d.faaliyetler.map((f) => `
    <div class="px-5 py-3 flex items-center justify-between hover:bg-[var(--bg-3)]/40">
      <div class="min-w-0"><p class="text-xs font-semibold text-white truncate">${esc(f.faaliyet)}</p>
        <p class="text-[10.5px] text-[var(--t2)] font-mono">${f.satir} envanter satırı</p></div>
      <div class="flex items-center gap-2 shrink-0 ml-3">
        <span class="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-500/15 text-rose-400">${sayi(f.kritik)} kritik</span>
        <span class="font-mono text-xs text-[var(--t1)]">${sayi(f.bulgu)}</span></div></div>`).join('');

  const st = d.graf;
  $('graf-dugum').textContent = sayi(st.toplam_dugum);
  $('graf-stats').innerHTML =
    Object.entries(st.nodes).sort((a, b) => b[1] - a[1]).map(([t, n]) =>
      `<div class="p-3 rounded-lg bg-[var(--bg-inset)] border border-[var(--line)]">
        <p class="text-[10px] uppercase tracking-wider text-[var(--t2)]">${esc(t)}</p>
        <p class="font-mono text-lg font-bold text-white">${sayi(n)}</p></div>`).join('');
}

async function maddeGetir() {
  const no = $('madde-no').value.trim();
  $('graf-madde').innerHTML = 'Yükleniyor…';
  try {
    const d = await api('/api/graph/madde/' + encodeURIComponent(no));
    $('graf-madde').innerHTML = `
      <p class="text-sm font-bold text-white mb-1">KVKK m.${esc(no)} — ${esc(d.madde.props.baslik || '')}</p>
      <p class="mb-3">Bu maddeye <strong class="text-indigo-400 font-mono">${d.atif_yapan_karar}</strong> Kurul kararı atıf yapıyor.</p>
      <p class="text-[11px] font-bold uppercase tracking-wider text-[var(--t2)] mb-1">Bağlı hukuki sebepler</p>
      <ul class="space-y-1 mb-3">${d.hukuki_sebepler.map((s) => `<li class="text-[11px] text-slate-300">• ${esc(kisalt(s, 80))}</li>`).join('') || '<li class="text-[11px] text-[var(--t2)]">—</li>'}</ul>
      <p class="text-[11px] font-bold uppercase tracking-wider text-[var(--t2)] mb-1">Atıf yapan kararlar (ilk 10)</p>
      <div class="flex flex-wrap gap-1">${d.kararlar.slice(0, 10).map((k) => `<span class="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-3)] border border-[var(--line)] text-indigo-300">${esc(k.label)}</span>`).join('')}</div>`;
  } catch (e) {
    $('graf-madde').innerHTML = `<span class="text-rose-400">Bulunamadı: ${esc(e.message)}</span>`;
  }
}

// ---------- görünüm ----------
function gorunum(v) {
  state.view = v;
  ['envanter', 'asistan', 'graf', 'belgeler'].forEach((x) => { const el = $('view-' + x); if (el) el.hidden = (x !== v && !(v === 'bulgular' && x === 'envanter')); });
  document.querySelectorAll('.nav-btn').forEach((b) => {
    const aktif = b.dataset.view === v;
    b.className = `nav-btn w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] ${aktif ? 'font-bold text-white bg-indigo-500/20 border border-indigo-500/30' : 'font-medium text-[var(--t1)] hover:text-white hover:bg-[var(--bg-2)]'}`;
  });
  if (v === 'bulgular') {
    $('crumb').textContent = 'Uyum Bulguları'; $('baslik').textContent = 'Uyum Bulguları';
    state.tab = 'kritik'; state.filtre.seviye = 'kritik'; state.offset = 0;
    $('f-seviye').value = 'kritik'; tabCiz(); tabloYukle();
  } else if (v === 'envanter') {
    $('crumb').textContent = 'Veri Envanteri'; $('baslik').textContent = 'Kişisel Veri İşleme Envanteri';
  } else if (v === 'graf') grafYukle();
  else if (v === 'belgeler') belgelerAc();
}

// ---------- başlangıç ----------
document.querySelectorAll('.nav-btn').forEach((b) => b.onclick = () => gorunum(b.dataset.view));
$('f-birim').onchange = (e) => filtreAta('birim', e.target.value);
$('f-faaliyet').onchange = (e) => filtreAta('faaliyet', e.target.value);
$('f-kategori').onchange = (e) => filtreAta('veri_kategorisi', e.target.value);
$('f-seviye').onchange = (e) => filtreAta('seviye', e.target.value);
$('f-sebep').oninput = (e) => gecikmeli(() => filtreAta('hukuki_sebep', e.target.value));
$('q-genel').oninput = (e) => gecikmeli(() => filtreAta('arama', e.target.value));
$('btn-sifirla').onclick = sifirla;
$('btn-yenile').onclick = () => { ozetYukle(); tabloYukle(); };
$('btn-yeni').onclick = () => formAc(null);
$('btn-excel').onclick = () => excelIndir(false);
$('btn-toplu-excel').onclick = () => excelIndir(true);
$('btn-toplu-sil').onclick = topluSil;
$('btn-secim-temizle').onclick = () => { state.secili.clear(); document.querySelectorAll('.sec-satir').forEach((c) => c.checked = false); secimGuncelle(); };
$('btn-tumunu-sec').onclick = tumunuSec;
$('sec-hepsi').onchange = (e) => {
  (state.sonSayfa || []).forEach((n) => e.target.checked ? state.secili.add(n) : state.secili.delete(n));
  document.querySelectorAll('.sec-satir').forEach((c) => c.checked = e.target.checked);
  secimGuncelle();
};
$('sayfa-boyut').onchange = (e) => { state.limit = +e.target.value; state.offset = 0; tabloYukle(); };
$('btn-gonder').onclick = () => chatGonder($('chat-girdi').value);
$('chat-girdi').onkeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); chatGonder($('chat-girdi').value); }
};
$('chat-girdi').oninput = girdiBoyut;
$('btn-yeni-sohbet').onclick = () => { chat.mesajlar = []; chatCiz(); $('chat-girdi').focus(); };
$('btn-madde').onclick = maddeGetir;
$('ornek-sorular').innerHTML = ORNEKLER.map((s) =>
  `<button class="ornek px-2.5 py-1 rounded-md text-[11px] bg-[var(--bg-3)] border border-[var(--line)] text-[var(--t1)] hover:text-white hover:border-indigo-500">${esc(s)}</button>`).join('');
document.querySelectorAll('.ornek').forEach((b) => b.onclick = () => chatGonder(b.textContent));

saglik();
grafYukle().catch(() => { $('graf-dugum').textContent = '—'; });
ozetYukle().then(tabloYukle).catch((e) => {
  $('tbody').innerHTML = `<tr><td colspan="10" class="py-16 text-center text-rose-400 text-xs">API'ye ulaşılamadı: ${esc(e.message)}</td></tr>`;
});
