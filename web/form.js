// Envanter kayit formu: elle giris + asistan onerisi. Seceneklerin kaynagi seeder
// taksonomisi; listede yoksa kullanici "Diğer(...)" yazar.
let TAX = null;

const ALANLAR = [
  // birim/faaliyet kurumsal alanlar: kanonik taksonomi yok, Diğer() kalıbı geçerli değil
  { k: 'birim',               ad: 'Birim / Başkanlık', tip: 'liste-serbest', kaynak: ['envanterden', 'birim'], serbest: true },
  { k: 'faaliyet',            ad: 'Faaliyet',          tip: 'liste-serbest', kaynak: ['envanterden', 'faaliyet'], serbest: true },
  { k: 'kisisel_veri',        ad: 'Kişisel Veri',      tip: 'metin' },
  { k: 'veri_kategorisi',     ad: 'Veri Kategorisi',   tip: 'liste-serbest', kaynak: ['kanonik', 'veri_kategorisi'], ozelIsaret: true },
  { k: 'ozel_nitelikli_veri', ad: 'Özel Nitelikli Veri', tip: 'metin' },
  { k: 'kisi_grubu',          ad: 'İlgili Kişi Grubu', tip: 'liste-serbest', kaynak: ['envanterden', 'kisi_grubu'] },
  { k: 'isleme_amaci',        ad: 'İşleme Amacı',      tip: 'liste-serbest', kaynak: ['kanonik', 'isleme_amaci'] },
  { k: 'hukuki_sebep',        ad: 'Hukuki Sebep',      tip: 'liste-serbest', kaynak: ['kanonik', 'hukuki_sebep'] },
  { k: 'alici_grubu',         ad: 'Alıcı Grubu',       tip: 'liste-serbest', kaynak: ['kanonik', 'alici_grubu'] },
  { k: 'yurt_disi_aktarim',   ad: 'Yurt Dışı Aktarım', tip: 'secim', secenek: ['Hayır', 'Evet'] },
  { k: 'saklama_suresi',      ad: 'Saklama Süresi',    tip: 'metin' },
  { k: 'imha_yontemi',        ad: 'İmha Yöntemi',      tip: 'metin' },
  { k: 'teknik_tedbir',       ad: 'Teknik Tedbirler',  tip: 'coklu', kaynak: ['kanonik', 'teknik_tedbir'] },
  { k: 'idari_tedbir',        ad: 'İdari Tedbirler',   tip: 'coklu', kaynak: ['kanonik', 'idari_tedbir'] },
];

async function taxYukle() {
  if (!TAX) TAX = await api('/api/taxonomy');
  return TAX;
}

function secenekler(a) {
  if (!a.kaynak) return a.secenek || [];
  const [grup, alan] = a.kaynak;
  return (TAX?.[grup]?.[alan]) || [];
}

function alanHtml(a, deger) {
  const id = 'form-' + a.k;
  const v = deger ?? '';
  const etiket = `<label class="text-[10px] uppercase tracking-wider text-[var(--t2)] block mb-1">${a.ad}</label>`;
  const ort = 'w-full bg-[var(--bg-inset)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-[var(--t2)] focus:outline-none focus:border-indigo-500';

  if (a.tip === 'coklu') {
    const liste = secenekler(a);
    const secili = String(v).split('\n').map((s) => s.replace(/^•\s*/, '').trim()).filter(Boolean);
    return `<div class="mb-3">${etiket}
      <div id="${id}" class="max-h-32 overflow-y-auto rounded-lg border border-[var(--line)] bg-[var(--bg-inset)] p-2 space-y-1">
        ${liste.map((x, i) => `<label class="flex items-start gap-2 text-[11px] text-slate-300 cursor-pointer hover:text-white">
          <input type="checkbox" value="${esc(x)}" ${secili.includes(x) ? 'checked' : ''}
            class="mt-0.5 rounded border-[var(--line-2)] bg-[var(--bg-2)] text-indigo-600 focus:ring-0">
          <span>${esc(x)}</span></label>`).join('')}
      </div></div>`;
  }

  if (a.tip === 'secim') {
    return `<div class="mb-3">${etiket}
      <select id="${id}" class="${ort}">${(a.secenek || []).map((x) =>
        `<option ${x === v ? 'selected' : ''}>${esc(x)}</option>`).join('')}</select></div>`;
  }

  if (a.tip === 'liste-serbest') {
    const liste = secenekler(a);
    const ozel = new Set(TAX?.ozel_nitelikli_kategoriler || []);
    const ipucu = a.serbest
      ? 'Seçin veya yeni bir değer yazın'
      : 'Seçin veya yazın — listede yoksa Diğer(açıklama)';
    // Ozel nitelikli kategoriler listede isaretlenir; secildiginde m.6 uyarisi cikar
    const ozelMi = a.ozelIsaret && ozel.has(v);
    let opsiyon = liste.map((x) => a.ozelIsaret && ozel.has(x)
      ? `<option value="${esc(x)}">özel nitelikli veri</option>`
      : `<option value="${esc(x)}">`).join('');
    if (a.k === 'veri_kategorisi') {
      opsiyon += `<option value="Diğer(açıklama)">Listede yoksa özel kategori</option>`;
    }
    return `<div class="mb-3">${etiket}
      <input id="${id}" list="${id}-list" value="${esc(v)}" placeholder="${ipucu}"
        class="${ort} ${ozelMi ? 'border-fuchsia-500/60' : ''}" ${a.ozelIsaret ? 'data-ozel-alan="1"' : ''}>
      <datalist id="${id}-list">${opsiyon}</datalist>
      <p id="${id}-uyari" class="text-[10px] text-fuchsia-400 mt-1" ${ozelMi ? '' : 'hidden'}>
        Özel nitelikli kişisel veri — hukuki sebep KVKK m.6'dan seçilmeli.</p></div>`;
  }

  return `<div class="mb-3">${etiket}<input id="${id}" value="${esc(v)}" class="${ort}"></div>`;
}

function formOku() {
  const out = {};
  ALANLAR.forEach((a) => {
    const el = $('form-' + a.k);
    if (!el) return;
    if (a.tip === 'coklu') {
      const secili = [...el.querySelectorAll('input:checked')].map((i) => i.value);
      out[a.k] = secili.join('\n');
    } else {
      out[a.k] = el.value.trim();
    }
  });
  // Eger veri_kategorisi Diğer(Biyometrik Veri) gibi kanonik bir kategoriyi Diğer() kalıbına sokmuşsa düzelt
  if (out.veri_kategorisi) {
    const m = out.veri_kategorisi.match(/^diğer\((.+)\)$/i);
    if (m) {
      const icerik = m[1].trim();
      const canonList = TAX?.kanonik?.veri_kategorisi || [];
      const match = canonList.find((c) => c.toLowerCase() === icerik.toLowerCase());
      if (match) out.veri_kategorisi = match;
    }
  }
  return out;
}

function bulguListesi(bulgular) {
  if (!bulgular || !bulgular.length)
    return '<p class="text-xs text-emerald-400">Bu kayıtta uyum bulgusu yok.</p>';
  return bulgular.map((b) => {
    const s = SEVIYE[b.seviye] || SEVIYE.dusuk;
    return `<div class="p-2.5 rounded-lg bg-[var(--bg-inset)] border border-${s.renk}-500/20 mb-1.5">
      <div class="flex items-center gap-2 mb-0.5">
        <span class="text-[9.5px] font-bold px-1.5 py-0.5 rounded bg-${s.renk}-500/15 text-${s.renk}-400">${s.etiket}</span>
        <span class="font-mono text-[9.5px] text-[var(--t2)]">${b.kod}</span>
        <span class="text-[11px] font-semibold text-white">${esc(b.baslik)}</span></div>
      <p class="text-[10.5px] font-mono text-indigo-400">${esc(b.dayanak)}</p></div>`;
  }).join('');
}

// onDoldur: {veri, birim, faaliyet} -> sohbetten gelen "envantere ekle" istegi;
// form acilir, alanlar yazilir ve oneri otomatik calisir.
async function formAc(mevcut, onDoldur) {
  await taxYukle();
  const duzenle = !!mevcut;
  const d = document.createElement('div');
  d.className = 'fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start justify-center p-6 overflow-y-auto';
  d.innerHTML = `<div class="bg-[var(--bg-2)] border border-[var(--line)] rounded-2xl max-w-5xl w-full my-4 shadow-2xl">
    <div class="sticky top-0 bg-[var(--bg-1)] border-b border-[var(--line)] px-5 py-3 flex items-center justify-between rounded-t-2xl">
      <h3 class="text-sm font-bold text-white">${duzenle ? `Kaydı Düzenle · Satır ${mevcut.satir_no}` : 'Yeni Envanter Kaydı'}</h3>
      <button class="kapat text-[var(--t2)] hover:text-white text-lg leading-none">✕</button>
    </div>

    <div class="p-5 border-b border-[var(--line)] bg-[var(--bg-inset)]/40">
      <div class="flex items-center gap-2 mb-2">
        <span class="w-2 h-2 rounded-full bg-indigo-500"></span>
        <h4 class="text-xs font-bold text-white">Asistan Önerisi</h4>
        <span class="text-[10.5px] text-[var(--t2)]">veriyi ve faaliyeti yazıp öneri isteyin; alanlar mevzuat dayanağıyla doldurulur</span>
      </div>
      <div class="flex gap-2">
        <input id="oneri-veri" placeholder="Eklenen kişisel veri — örn: Çocuk sayısı"
          class="flex-1 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-[var(--t2)] focus:outline-none focus:border-indigo-500">
        <button id="btn-oneri" class="px-4 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white whitespace-nowrap">Öneri Al</button>
      </div>
      <div id="oneri-sonuc" class="mt-3 text-xs" hidden></div>
    </div>

    <div class="p-5 grid grid-cols-1 lg:grid-cols-3 gap-x-5">
      <div>${ALANLAR.slice(0, 5).map((a) => alanHtml(a, mevcut?.[a.k])).join('')}</div>
      <div>${ALANLAR.slice(5, 10).map((a) => alanHtml(a, mevcut?.[a.k])).join('')}</div>
      <div>${ALANLAR.slice(10).map((a) => alanHtml(a, mevcut?.[a.k])).join('')}</div>
    </div>

    <div id="form-bulgular" class="px-5 pb-3" ${duzenle ? '' : 'hidden'}>
      <h4 class="text-xs font-bold text-white mb-2">Uyum Bulguları</h4>
      <div id="form-bulgu-liste">${bulguListesi(mevcut?.bulgular)}</div>
    </div>

    <div class="sticky bottom-0 bg-[var(--bg-1)] border-t border-[var(--line)] px-5 py-3 flex items-center justify-between rounded-b-2xl">
      <span id="form-durum" class="text-[11px] text-[var(--t2)]"></span>
      <div class="flex gap-2">
        ${duzenle ? `<button id="btn-sil" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-500/15 text-rose-400 border border-rose-500/30 hover:bg-rose-500/25">Sil</button>` : ''}
        <button class="kapat px-3 py-1.5 text-xs font-semibold rounded-lg bg-[var(--bg-3)] border border-[var(--line)] text-[var(--t1)] hover:text-white">Vazgeç</button>
        <button id="btn-kaydet" class="px-5 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/30">${duzenle ? 'Güncelle' : 'Kaydet'}</button>
      </div>
    </div></div>`;

  document.body.appendChild(d);
  d.onclick = (e) => { if (e.target === d || e.target.classList.contains('kapat')) d.remove(); };

  const durum = (msg, renk = 'var(--t2)') => { $('form-durum').style.color = renk; $('form-durum').textContent = msg; };

  // Ozel nitelikli kategori secilirse anlik uyari (kaydetmeden once gorunsun)
  const ozelSet = new Set(TAX?.ozel_nitelikli_kategoriler || []);
  const katEl = $('form-veri_kategorisi');
  const ozelKontrol = () => {
    const ozel = ozelSet.has(katEl.value.trim());
    $('form-veri_kategorisi-uyari').hidden = !ozel;
    katEl.classList.toggle('border-fuchsia-500/60', ozel);
  };
  katEl.addEventListener('input', ozelKontrol);
  katEl.addEventListener('change', ozelKontrol);

  $('btn-oneri').onclick = async () => {
    const veri = $('oneri-veri').value.trim() || $('form-kisisel_veri').value.trim();
    if (!veri) return durum('Önce eklenen kişisel veriyi yazın.', '#F59E0B');
    $('oneri-sonuc').hidden = false;
    $('oneri-sonuc').innerHTML = '<span class="text-[var(--t2)]">Mevzuat kaynakları taranıyor ve öneri üretiliyor…</span>';
    try {
      const o = await api('/api/inventory/suggest', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ veri, birim: $('form-birim').value, faaliyet: $('form-faaliyet').value }),
      });
      oneriUygula(o);
      ozelKontrol();
      const kaynak = (o.kaynaklar || []).map((k) => k.madde_no ? `m.${k.madde_no}` : k.karar_no).filter(Boolean);
      $('oneri-sonuc').innerHTML = `
        <div class="p-3 rounded-lg bg-[var(--bg-2)] border border-indigo-500/25">
          <p class="text-[11px] text-slate-200 leading-snug mb-2">${esc(o.gerekce || '')}</p>
          ${(o.uyarilar || []).map((u) => `<p class="text-[11px] text-amber-400 leading-snug mb-1">⚠ ${esc(u)}</p>`).join('')}
          <p class="text-[10.5px] text-[var(--t2)] mt-1">Dayanak: <span class="font-mono text-indigo-400">${kaynak.slice(0, 8).map(esc).join(' · ')}</span></p>
        </div>`;
      durum('Öneri forma uygulandı. Kaydetmeden önce gözden geçirin.', '#10B981');
    } catch (e) {
      $('oneri-sonuc').innerHTML = `<span class="text-rose-400">Öneri alınamadı: ${esc(e.message)}</span>`;
    }
  };

  function oneriUygula(o) {
    const ata = (k, v) => { const el = $('form-' + k); if (el && v) el.value = v; };
    // Kullanici tek cumle yazmis olabilir; asistan birim/faaliyet/veriyi ayristirir
    ata('kisisel_veri', o.kisisel_veri);
    ata('birim', o.birim);
    ata('faaliyet', o.faaliyet);
    ['veri_kategorisi', 'kisi_grubu', 'isleme_amaci', 'hukuki_sebep', 'alici_grubu',
     'saklama_suresi', 'imha_yontemi'].forEach((k) => ata(k, o[k]));
    if (o.ozel_nitelikli && o.veri_kategorisi) ata('ozel_nitelikli_veri', o.kisisel_veri);
    ['teknik_tedbir', 'idari_tedbir'].forEach((k) => {
      const kutu = $('form-' + k); if (!kutu) return;
      const sec = new Set(o[k] || []);
      kutu.querySelectorAll('input').forEach((i) => { if (sec.has(i.value)) i.checked = true; });
    });
  }

  $('btn-kaydet').onclick = async () => {
    durum('Kaydediliyor…');
    try {
      const veri = formOku();
      const d2 = duzenle
        ? await api('/api/inventory/' + mevcut.satir_no, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(veri) })
        : await api('/api/inventory', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(veri) });
      $('form-bulgular').hidden = false;
      $('form-bulgu-liste').innerHTML = bulguListesi(d2.bulgular);
      const n = (d2.bulgular || []).length;
      durum(n ? `Kaydedildi — ${n} uyum bulgusu oluştu, aşağıda.` : 'Kaydedildi — uyum bulgusu yok.', n ? '#F59E0B' : '#10B981');
      ozetYukle().then(tabloYukle);
    } catch (e) { durum('Hata: ' + e.message, '#EF4444'); }
  };

  if (duzenle) $('btn-sil').onclick = async () => {
    if (!confirm(`Satır ${mevcut.satir_no} silinecek. Onaylıyor musunuz?`)) return;
    try {
      await api('/api/inventory/' + mevcut.satir_no, { method: 'DELETE' });
      d.remove(); ozetYukle().then(tabloYukle);
    } catch (e) { durum('Silinemedi: ' + e.message, '#EF4444'); }
  };

  if (onDoldur && !duzenle) {
    const ata = (k, v) => { const el = $('form-' + k); if (el && v) el.value = v; };
    ata('kisisel_veri', onDoldur.veri); ata('birim', onDoldur.birim); ata('faaliyet', onDoldur.faaliyet);
    $('oneri-veri').value = onDoldur.veri || '';
    durum('Sohbetten geldi — öneri alınıyor…');
    $('btn-oneri').click();
  }
}
