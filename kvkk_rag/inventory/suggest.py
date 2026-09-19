# Yeni envanter kaydi icin KVKK siniflandirma onerisi. Secenekler kanonik
# taksonomiyle sinirlidir; LLM serbest metin uyduramaz.
from __future__ import annotations

import json
import re
from typing import Any

from ..index import lexical_store
from ..llm.factory import get_llm
from ..retrieval import hybrid
from . import normalize, taxonomy

# Kanonik listesi olmayan alanlar envanterdeki mevcut degerlerden beslenir
TURETILEN = ("veri_kategorisi", "kisi_grubu")

SYSTEM = """Sen KVKK veri envanteri uzmanısın. Sana bir kişisel veri, onu işleyen birim ve \
faaliyet verilecek. Görevin bu kaydı KVKK'ya uygun şekilde sınıflandırmak.

KURALLAR:
1. Yalnızca SANA VERİLEN SEÇENEK LİSTELERİNDEN seç. Veri kategorisi için MUTLAKA sana verilen \
25 resmi kategoriden birini seç ('Biyometrik Veri', 'Genetik Veri', 'Sağlık Bilgileri' vb. zaten listededir; \
bunları ASLA 'Diğer(Biyometrik Veri)' şeklinde yazma). Listede uygun bir karşılık gerçekten yoksa \
istisnai olarak "Diğer(kısa açıklama)" biçiminde yaz — başka türlü serbest metin UYDURMA. Mevzuatta \
"Diğer" diye bir kategori yoktur; bu yalnızca envanter teamülüdür ve istisnai kullanılır.
2. Her alan için seçimini SANA VERİLEN MEVZUAT KAYNAKLARINA dayandır.
3. Veri özel nitelikliyse (sağlık, biyometrik, ceza mahkûmiyeti, din, sendika, cinsel hayat) \
hukuki sebebi MUTLAKA "Özel Nitelikli Kişisel Veri İşleme Şartları" grubundan seç ve bunu gerekçende belirt.
4. Emin olmadığın alanı boş bırak ve gerekçesinde nedenini yaz. Tahmin etme.
5. Yalnızca geçerli JSON döndür, başka hiçbir şey yazma.

6. Kullanıcı serbest bir cümle yazmış olabilir (örn. "idari işler başkanlığınca sosyal medya \
faaliyetlerinde telefon numarası alma"). Bu cümleden BİRİMİ, FAALİYETİ ve asıl KİŞİSEL VERİYİ \
ayrıştır. Birim ve faaliyet zaten ayrıca verilmişse onları koru, ayrıştırma. Kişisel veri \
alanına yalnızca verinin kendi adını yaz ("Telefon numarası"), cümlenin tamamını değil.

JSON şeması:
{
  "kisisel_veri": "<yalnızca verinin adı>",
  "birim": "<ayrıştırılan birim veya verilen birim>",
  "faaliyet": "<ayrıştırılan faaliyet veya verilen faaliyet>",
  "veri_kategorisi": "<seçenek>",
  "kisi_grubu": "<seçenek>",
  "isleme_amaci": "<seçenek>",
  "hukuki_sebep": "<seçenek>",
  "alici_grubu": "<seçenek>",
  "ozel_nitelikli": true|false,
  "teknik_tedbir": ["<seçenek>", ...],
  "idari_tedbir": ["<seçenek>", ...],
  "saklama_suresi": "<serbest metin öneri>",
  "imha_yontemi": "<serbest metin öneri>",
  "gerekce": "<2-4 cümle, hangi maddeye dayandığını belirt>",
  "uyarilar": ["<varsa risk/eksik uyarısı>"]
}"""

USER = """YENİ KAYIT
Kişisel veri : {veri}
Birim        : {birim}
Faaliyet     : {faaliyet}
{ek}

SEÇENEK LİSTELERİ (yalnızca bunlardan seç)
{secenekler}

MEVZUAT KAYNAKLARI
{kaynaklar}

Bu kaydı sınıflandır ve JSON döndür."""


def _secenek_listeleri(conn_store) -> dict[str, list[str]]:
    from . import store
    kategoriler = taxonomy.values("veri_kategorisi") or sorted(taxonomy.OZEL_NITELIKLI_KATEGORILER)
    out = {
        "veri_kategorisi": kategoriler,
        "kisi_grubu": store.distinct(conn_store, "kisi_grubu"),
        "isleme_amaci": taxonomy.values("isleme_amaci"),
        "hukuki_sebep": taxonomy.values("hukuki_sebep"),
        "alici_grubu": taxonomy.values("alici_grubu"),
        "teknik_tedbir": taxonomy.values("teknik_tedbir"),
        "idari_tedbir": taxonomy.values("idari_tedbir"),
    }
    return {k: v for k, v in out.items() if v}


def _kaynak_sorgusu(veri: str, faaliyet: str) -> str:
    return f"{veri} verisinin işlenmesi {faaliyet} hangi şartlarda mümkün, hangi tedbirler gerekir"


def _mevcuda_hizala(deger: str, mevcut: list[str], esik: float = 0.55) -> str:
    # Ayristirilan birim/faaliyet envanterdeki mevcut bir degere yakinsa onu kullan;
    # boylece "idari isler baskanligi" yeni bir birim acmak yerine mevcutla eslesir.
    if not deger or not mevcut:
        return deger
    if deger in mevcut:
        return deger
    hedef = set(normalize.fold(deger).split())
    en_iyi, en_skor = deger, 0.0
    for m in mevcut:
        t = set(normalize.fold(m).split())
        if not t:
            continue
        skor = len(hedef & t) / len(hedef | t)
        if skor > en_skor:
            en_iyi, en_skor = m, skor
    return en_iyi if en_skor >= esik else deger


def _parse_json(text: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("LLM geçerli JSON döndürmedi")
    return json.loads(m.group(0))


def _gecerli(v: str, liste: list[str]) -> bool:
    # Kanonik listede olmayan deger yalnizca "Diğer(...)" kalibiyla kabul edilir;
    # envanterin mevcut teamulu budur, mevzuatta "Diğer" diye bir kategori yoktur.
    return v in liste or v.strip().lower().startswith(taxonomy.DIGER_PREFIX)


def _dogrula(oneri: dict[str, Any], secenekler: dict[str, list[str]]) -> dict[str, Any]:
    # Eger veri_kategorisi Diğer(Biyometrik Veri) gibi kanonik bir kategoriyi sarmalayarak
    # gelmisse, bunu dogrudan resmi kanonik kategoriye donustur
    kat = oneri.get("veri_kategorisi")
    if kat and isinstance(kat, str):
        kat_clean = kat.strip()
        if kat_clean.lower().startswith(taxonomy.DIGER_PREFIX) and kat_clean.endswith(")"):
            icerik = kat_clean[len(taxonomy.DIGER_PREFIX):-1].strip()
            canon_kat = secenekler.get("veri_kategorisi", [])
            canon_map = {normalize.fold(c): c for c in canon_kat}
            if normalize.fold(icerik) in canon_map:
                oneri["veri_kategorisi"] = canon_map[normalize.fold(icerik)]

    sapma: list[str] = []
    for alan, liste in secenekler.items():
        v = oneri.get(alan)
        if v is None:
            continue
        if isinstance(v, list):
            oneri[alan] = [x for x in v if _gecerli(x, liste)]
            sapma += [f"{alan}: {x}" for x in v if not _gecerli(x, liste)]
        elif v and not _gecerli(v, liste):
            sapma.append(f"{alan}: {v}")
            oneri[alan] = None
    if sapma:
        oneri.setdefault("uyarilar", []).append(
            "Liste dışı öneriler düşürüldü (listede yoksa Diğer(...) kullanılmalı): "
            + "; ".join(sapma[:5]))
    return oneri


def suggest(veri: str, birim: str, faaliyet: str, ek_bilgi: str = "",
            conn_store=None, provider: str | None = None) -> dict[str, Any]:
    from . import store

    kapat = conn_store is None
    conn_store = conn_store or store.connect()
    try:
        secenekler = _secenek_listeleri(conn_store)
        secenekler_serbest = {
            "birim": store.distinct(conn_store, "birim"),
            "faaliyet": store.distinct(conn_store, "faaliyet"),
        }
    finally:
        if kapat:
            conn_store.close()

    lex = lexical_store.connect()
    try:
        rows = hybrid.search(_kaynak_sorgusu(veri, faaliyet), conn=lex, limit=8)
    finally:
        lex.close()

    kaynak_metni = "\n\n".join(
        f"[{i}] ({'ZORUNLU' if r['baglayicilik'].startswith('zorunlu') else 'TAVSİYE'}) "
        f"{r['belge_adi'][:70]}"
        + (f" m.{r['madde_no']}" if r["madde_no"] else "")
        + (f" · Karar {r['karar_no']}" if r["karar_no"] else "")
        + f"\n{(r['text_raw'] or '')[:900]}"
        for i, r in enumerate(rows, 1))

    secenek_metni = "\n\n".join(
        f"{alan}:\n" + "\n".join(f"  - {x}" for x in liste[:60])
        for alan, liste in secenekler.items())

    llm = get_llm(provider)
    ham = llm.complete([
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER.format(
            veri=veri, birim=birim or "—", faaliyet=faaliyet or "—",
            ek=f"Ek bilgi    : {ek_bilgi}" if ek_bilgi else "",
            secenekler=secenek_metni, kaynaklar=kaynak_metni)},
    ], temperature=0.1, max_tokens=1600)

    oneri = _dogrula(_parse_json(ham), secenekler)

    # Ozel nitelikli tutarlilik kontrolu deterministik yapilir, LLM'e birakilmaz
    kat = oneri.get("veri_kategorisi")
    if kat and taxonomy.is_ozel_nitelikli_kategori(kat):
        oneri["ozel_nitelikli"] = True
        sebep = oneri.get("hukuki_sebep")
        if sebep and not taxonomy.is_ozel_nitelikli_sebep(sebep):
            oneri.setdefault("uyarilar", []).append(
                f"'{kat}' özel nitelikli kişisel veridir; seçilen hukuki sebep "
                f"KVKK m.6 kapsamında değil. Bu haliyle kaydedilirse ENV-004 bulgusu oluşur.")

    # Kullanici tek cumle yazmis olabilir; LLM ayristirdiysa onu kullan, yoksa girdiye don.
    oneri["kisisel_veri"] = (oneri.get("kisisel_veri") or "").strip() or veri
    oneri["birim"] = birim or _mevcuda_hizala(
        (oneri.get("birim") or "").strip(), secenekler_serbest.get("birim", []))
    oneri["faaliyet"] = faaliyet or _mevcuda_hizala(
        (oneri.get("faaliyet") or "").strip(), secenekler_serbest.get("faaliyet", []))
    oneri["kaynaklar"] = [{
        "belge_adi": r["belge_adi"], "madde_no": r["madde_no"],
        "karar_no": r["karar_no"], "baglayicilik": r["baglayicilik"],
    } for r in rows]
    return oneri
