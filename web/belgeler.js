// Uyum belgeleri: kurum profili + envanterden docx uretimi.
const PROFIL_ALANLARI = [
  { k: 'kurum',            ad: 'Kurum / Veri Sorumlusu', zorunlu: true, ipucu: 'Örn: ÖRNEK TEKNOLOJİ A.Ş.' },
  { k: 'adres',            ad: 'Adres',                  ipucu: 'Başvuruların yapılacağı açık adres' },
  { k: 'web_adres',        ad: 'Web Adresi',             ipucu: 'www.ornek.com.tr' },
  { k: 'faaliyet',         ad: 'Belge Başlığı (Faaliyet)', ipucu: 'Aydınlatma metni başlığında geçer' },
  { k: 'veri_isleyen',     ad: 'Veri İşleyen',           grup: 'protokol', ipucu: 'Protokolün karşı tarafı' },
  { k: 'sozlesme_adi',     ad: 'Sözleşme Adı',           grup: 'protokol' },
  { k: 'sozlesme_tarihi',  ad: 'Sözleşme Tarihi',        grup: 'protokol', ipucu: 'GG.AA.YYYY' },
  { k: 'protokol_tarihi',  ad: 'Protokol Tarihi',        grup: 'protokol', ipucu: 'boş bırakılırsa bugün' },
];

const belgeState = {
  profil: {}, sablonlar: [], faaliyetler: [], faaliyetBazli: [],
  // kapsam tum belgeler icin ortak; faaliyet secimi yalnizca kendi sablonunu
  // daraltir, digerlerinin kapsamini bozmamali
  kapsam: { birim: null, faaliyet_filtresi: null },
  faaliyetSecimi: {},
};

const URETIM_ETIKET = {
  hukuki_sebepler: 'Hukuki sebepler (Bölüm 4)',
  kayit_ortamlari: 'Toplama ortamları (Bölüm 4)',
  saklama_ozeti:   'Saklama süreleri (Bölüm 11)',
  politika_kapsam: 'Amaç ve kapsam (Bölüm 2)',
  risk_analizi:    'Risk analizi (Bölüm 15)',
};

function profilOku() {
  const out = {};
  PROFIL_ALANLARI.forEach((a) => {
    const el = $('prof-' + a.k);
    if (el) out[a.k] = el.value.trim();
  });
  return { ...out, ...belgeState.kapsam };
}

function profilFormCiz() {
  const ort = 'w-full bg-[var(--bg-inset)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-[var(--t2)] focus:outline-none focus:border-indigo-500';
  $('profil-form').innerHTML = PROFIL_ALANLARI.map((a) => `
    <div>
      <label class="text-[10px] uppercase tracking-wider text-[var(--t2)] block mb-1">
        ${a.ad}${a.zorunlu ? ' <span class="text-rose-400">*</span>' : ''}
        ${a.grup === 'protokol' ? '<span class="text-[9px] text-[var(--t2)] normal-case">· yalnızca protokol</span>' : ''}
      </label>
      <input id="prof-${a.k}" class="${ort}" placeholder="${a.ipucu || ''}"
        value="${esc(belgeState.profil[a.k] || '')}">
    </div>`).join('');

  PROFIL_ALANLARI.forEach((a) => {
    $('prof-' + a.k).oninput = () => {
      belgeState.profil[a.k] = $('prof-' + a.k).value;
      belgeState.kirli = true;
      profilDurum('Kaydedilmedi', '#F59E0B');
      gecikmeli(belgelerCiz);
    };
  });
}

function uretimRozetleri(onizleme) {
  // Sablonda sabit yazili olmayip envanterden/LLM'den uretilen bolumler
  const u = onizleme?.uretilen_bolumler || [];
  if (!u.length) return '';
  return `<p class="text-[11px] text-[var(--t2)] mt-1.5">Otomatik yazılan bölümler:
    ${u.map((b) => {
      const ai = b.kaynak === 'yapay_zeka';
      return `<span class="inline-block mr-1 mt-1 px-1.5 py-0.5 rounded text-[10px] border
        ${ai ? 'bg-violet-500/10 text-violet-300 border-violet-500/30'
             : 'bg-sky-500/10 text-sky-300 border-sky-500/30'}"
        title="${ai ? 'Yapay zeka ile yazılır — imzalamadan önce gözden geçirin'
                    : 'Veri envanterinden doldurulur'}">${ai ? '✨' : '🗄'} ${esc(URETIM_ETIKET[b.alan] || b.alan)}</span>`;
    }).join('')}</p>`;
}

function faaliyetSecici(s) {
  // Aydinlatma metni KVKK m.10 geregi faaliyet bazlidir; tek tek veya zip
  if (!belgeState.faaliyetBazli.includes(s.anahtar)) return '';
  const secili = belgeState.faaliyetSecimi[s.anahtar] || '';
  const ops = belgeState.faaliyetler.map((f) =>
    `<option value="${esc(f.ad)}" ${f.ad === secili ? 'selected' : ''}>${esc(f.ad)} · ${f.satir} kayıt</option>`).join('');
  return `<div class="mt-2 flex items-center gap-2">
    <select id="faal-${s.anahtar}" class="flex-1 min-w-0 bg-[var(--bg-inset)] border border-[var(--line)] rounded-lg px-2 py-1 text-[11px] text-white focus:outline-none focus:border-indigo-500">
      <option value="">Tüm faaliyetler (${belgeState.faaliyetler.length}) — ZIP</option>
      ${ops}
    </select>
  </div>`;
}

function belgeKarti(s, onizleme) {
  // Onizleme yoksa "hazir" denmez; kurum adi girilene kadar durum bilinmiyor.
  // Faaliyet bazli belgede baslik asagidaki listeden gelir, eksik sayilmaz.
  const faalBazli = belgeState.faaliyetBazli.includes(s.anahtar);
  const eksik = (onizleme?.eksik_alanlar || []).filter(
    (a) => !(faalBazli && a.toLocaleLowerCase('tr') === 'faaliyet'));
  const bilinmiyor = s.mevcut && !onizleme;
  const hazir = s.mevcut && onizleme && eksik.length === 0;
  const durum = !s.mevcut
    ? `<span class="text-[11px] font-bold px-2 py-0.5 rounded bg-rose-500/15 text-rose-400 border border-rose-500/30">ŞABLON YOK</span>`
    : bilinmiyor
      ? `<span class="text-[11px] font-bold px-2 py-0.5 rounded bg-[var(--bg-3)] text-[var(--t2)] border border-[var(--line)]">KURUM ADI BEKLENİYOR</span>`
      : hazir
        ? `<span class="text-[11px] font-bold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">HAZIR</span>`
        : `<span class="text-[11px] font-bold px-2 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30">${eksik.length} ALAN EKSİK</span>`;

  return `<div class="px-5 py-4 hover:bg-[var(--bg-3)]/30">
    <div class="flex items-start justify-between gap-4">
      <div class="min-w-0">
        <div class="flex items-center gap-2 mb-1">
          <h4 class="text-sm font-bold text-white">${esc(s.ad)}</h4>${durum}
        </div>
        <p class="text-[11px] text-[var(--t2)] font-mono mb-1">${esc(s.dosya)}</p>
        <p class="text-[11px] text-[var(--t1)]">Doldurulacak alanlar:
          <span class="text-slate-300">${(s.alanlar || []).map(esc).join(', ') || '—'}</span></p>
        ${eksik.length ? `<p class="text-[11px] text-amber-400 mt-1">Eksik: ${eksik.map(esc).join(', ')} — bu alanlar boş kalacak.</p>` : ''}
        ${uretimRozetleri(onizleme)}
        ${faaliyetSecici(s)}
      </div>
      <button class="uret-btn shrink-0 px-4 py-1.5 text-xs font-bold rounded-lg ${hazir ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30' : 'bg-[var(--bg-3)] border border-[var(--line)] text-[var(--t1)] hover:text-white'}"
        data-sablon="${s.anahtar}" ${s.mevcut ? '' : 'disabled'}>İndir</button>
    </div></div>`;
}

async function dosyaIndir(yol, govde, varsayilanAd) {
  const r = await fetch(API + yol, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(govde),
  });
  if (!r.ok) throw new Error(await r.text());
  const blob = await r.blob();
  const cd = r.headers.get('Content-Disposition') || '';
  const ad = decodeURIComponent((cd.match(/filename="?([^"]+)"?/) || [])[1] || varsayilanAd);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = ad; a.click();
  URL.revokeObjectURL(url);
  return r.headers;
}

let cizimSayaci = 0;

async function belgelerCiz() {
  // Es zamanli cagrilar birbirini ezmesin: yalnizca en son istek DOM'a yazar
  const benim = ++cizimSayaci;
  const p = profilOku();
  if (!belgeState.sablonlar.length) {
    const d = await api('/api/documents');
    belgeState.sablonlar = d.sablonlar;
    belgeState.faaliyetBazli = d.faaliyet_bazli || [];
  }
  if (!belgeState.faaliyetler.length) {
    try {
      const q = belgeState.kapsam.birim ? '?birim=' + encodeURIComponent(belgeState.kapsam.birim) : '';
      belgeState.faaliyetler = (await api('/api/documents/faaliyetler' + q)).faaliyetler || [];
    } catch { belgeState.faaliyetler = []; }
  }

  const kapsamMetni = belgeState.kapsam.birim
    ? `kapsam: ${belgeState.kapsam.birim}`
    : 'kapsam: tüm envanter';
  $('belge-kapsam').textContent = kapsamMetni;

  let onizlemeler = {};
  if (p.kurum) {
    const sonuc = await Promise.all(belgeState.sablonlar.filter((s) => s.mevcut).map((s) =>
      api('/api/documents/preview', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...p, sablon: s.anahtar }),
      }).then((r) => [s.anahtar, r]).catch(() => [s.anahtar, null])));
    onizlemeler = Object.fromEntries(sonuc);
  }
  if (benim !== cizimSayaci) return;

  $('belge-liste').innerHTML = belgeState.sablonlar.map((s) =>
    belgeKarti(s, onizlemeler[s.anahtar])).join('');

  const btnEtiketi = (anahtar) => {
    const sel = $('faal-' + anahtar);
    if (!sel) return 'İndir (.docx)';
    return sel.value ? 'İndir (.docx)' : `Tümü (.zip · ${belgeState.faaliyetler.length})`;
  };

  belgeState.faaliyetBazli.forEach((anahtar) => {
    const sel = $('faal-' + anahtar);
    if (!sel) return;
    sel.onchange = () => {
      belgeState.faaliyetSecimi[anahtar] = sel.value;
      const b = document.querySelector(`.uret-btn[data-sablon="${anahtar}"]`);
      if (b) b.textContent = btnEtiketi(anahtar);
    };
  });

  document.querySelectorAll('.uret-btn').forEach((b) => {
    b.textContent = btnEtiketi(b.dataset.sablon);
    b.onclick = async () => {
      const veri = profilOku();
      if (!veri.kurum) { alert('Kurum adı zorunludur.'); $('prof-kurum').focus(); return; }
      const anahtar = b.dataset.sablon;
      const sel = $('faal-' + anahtar);
      // Faaliyet secilmemisse tum faaliyetler tek zip halinde iner
      const zip = !!sel && !sel.value;
      const govde = { ...veri, sablon: anahtar };
      if (sel) {
        govde.faaliyet = sel.value || veri.faaliyet;
        govde.faaliyet_filtresi = sel.value || null;
      }
      const eski = b.textContent;
      b.textContent = zip ? 'ZIP hazırlanıyor…' : 'Üretiliyor…'; b.disabled = true;
      try {
        const h = await dosyaIndir(
          zip ? '/api/documents/generate-all' : '/api/documents/generate',
          govde, zip ? 'belgeler.zip' : 'belge.docx');
        const hata = parseInt(h.get('X-Hata-Sayisi') || '0', 10);
        if (hata) alert(`${h.get('X-Uretilen-Belge')} belge üretildi, ${hata} faaliyet atlandı.`);
      } catch (e) {
        alert('Belge üretilemedi: ' + e.message);
      } finally {
        b.textContent = eski; b.disabled = false;
      }
    };
  });
}

function profilDurum(metin, renk = 'var(--t2)') {
  const el = $('profil-durum');
  if (el) { el.textContent = metin; el.style.color = renk; }
}

async function profilKaydet() {
  const veri = profilOku();
  if (!veri.kurum) { alert('Kurum adı zorunludur.'); $('prof-kurum').focus(); return; }
  profilDurum('Kaydediliyor…');
  try {
    const d = await api('/api/profile', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(veri),
    });
    belgeState.kirli = false;
    const t = d.guncelleme ? new Date(d.guncelleme).toLocaleString('tr-TR') : '';
    profilDurum(`Kaydedildi · ${t}`, '#10B981');
  } catch (e) { profilDurum('Kaydedilemedi: ' + e.message, '#EF4444'); }
}

async function belgelerAc() {
  if (!Object.keys(belgeState.profil).length) {
    try {
      const d = await api('/api/profile');
      belgeState.profil = d;
      if (d.kurum) {
        const t = d.guncelleme ? new Date(d.guncelleme).toLocaleString('tr-TR') : '';
        setTimeout(() => profilDurum(`Kayıtlı profil yüklendi · ${t}`, '#10B981'), 50);
      }
    } catch {}
  }
  profilFormCiz();
  if ($('btn-profil-kaydet')) $('btn-profil-kaydet').onclick = profilKaydet;
  belgelerCiz().catch((e) => {
    $('belge-liste').innerHTML = `<div class="px-5 py-8 text-center text-xs text-rose-400">Yüklenemedi: ${esc(e.message)}</div>`;
  });
}
