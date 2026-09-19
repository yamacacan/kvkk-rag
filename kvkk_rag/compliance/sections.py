# Politika sablonunun sabit yazilmis bolumlerini envanterden ve LLM'den uretir.
# Iki sinif deger var: VERITABANI (deterministik, envanterden) ve YAPAY_ZEKA
# (LLM, yalnizca burada verilen olgulara dayanarak yazar). LLM yoksa her AI
# bolumu ayni olgulardan kurulan deterministik metne duser; belge asla
# ${...} kalintisi veya uydurma bilgi icermez.
from __future__ import annotations

from typing import Any

from ..inventory import normalize, taxonomy
from ..inventory.loader import InventoryRow

# Politika sablonu
VERITABANI = ("hukuki_sebepler", "kayit_ortamlari", "saklama_ozeti",
              # Veri ihlali mudahale proseduru
              "ihlal_birimleri", "ihlal_veri_kategorileri")
YAPAY_ZEKA = ("politika_kapsam", "risk_analizi",
              "ihlal_senaryolari", "ihlal_risk_degerlendirmesi")

SISTEM = (
    "Sen bir KVKK (6698 sayılı Kanun) uyum uzmanısın. Türkçe, resmî ve kurumsal "
    "bir üslupla yazarsın. KESİN KURALLAR: (1) Yalnızca sana verilen olgulara "
    "dayan; kurum hakkında verilmeyen hiçbir bilgiyi uydurma. (2) Madde numarası "
    "ancak sana verildiyse yaz. (3) Başlık, madde imi, numaralandırma veya "
    "Markdown kullanma; yalnızca düz paragraf yaz. (4) Kuruma 'VERİ SORUMLUSU' "
    "diye atıfta bulun. (5) Hukuki tavsiye verme, mevcut durumu tarif et. "
    "(6) Sayıları rakamla yaz; mevzuat atıflarını sana verildiği yazımla "
    "(örn. KVKK m.12/1) aynen aktar, kelimeyle yazma."
)


def _cok_degerli(rows: list[InventoryRow], alan: str) -> dict[str, int]:
    # Envanter hucreleri satir sonuyla ayrilmis birden cok deger tasiyabilir
    sayac: dict[str, int] = {}
    for r in rows:
        ham = getattr(r, alan, "") or ""
        for parca in normalize.split_values(ham):
            parca = parca.strip(" .;")
            if len(parca) > 2:
                sayac[parca] = sayac.get(parca, 0) + 1
    return sayac


# --- Veritabani kaynakli bolumler ------------------------------------------

def hukuki_sebepler(rows: list[InventoryRow]) -> list[str]:
    # Bolum 4: sablondaki 8 maddelik sabit liste yerine kurumun fiilen dayandigi
    # sebepler. Kanonik yazima hizalanir (envanterdeki "temek/doğudan" yazim
    # hatalari normalize.TYPO ile duzelir).
    canon = taxonomy.values("hukuki_sebep")
    gorulen: dict[str, int] = {}
    for ham, n in _cok_degerli(rows, "hukuki_sebep").items():
        m = normalize.match_one(ham, canon)
        ad = m.kanonik or ham
        gorulen[ad] = gorulen.get(ad, 0) + n
    return [k for k, _ in sorted(gorulen.items(), key=lambda kv: (-kv[1], kv[0]))]


def kayit_ortamlari(rows: list[InventoryRow]) -> str:
    # Bolum 4: "her türlü sözlü, yazılı ve elektronik ortamda" yerine gercek ortamlar
    ortamlar = sorted(_cok_degerli(rows, "kayit_ortami"), key=str.casefold)
    if not ortamlar:
        return "her türlü sözlü, yazılı ve elektronik ortamda"
    if len(ortamlar) == 1:
        return f"{ortamlar[0]} ortamında"
    return f"{', '.join(ortamlar[:-1])} ve {ortamlar[-1]} ortamlarında"


def saklama_ozeti(rows: list[InventoryRow]) -> str:
    # Bolum 11: genel ifade yerine kategori bazinda gercek sure ve imha yontemi
    gruplar: dict[str, dict[str, set[str]]] = {}
    for r in rows:
        kat = (r.veri_kategorisi or "").strip()
        if not kat:
            continue
        g = gruplar.setdefault(kat, {"sure": set(), "imha": set()})
        if r.saklama_suresi:
            g["sure"].add(r.saklama_suresi.strip())
        if r.imha_yontemi:
            g["imha"].add(r.imha_yontemi.strip())

    if not gruplar:
        return "Veri kategorisi bazında saklama süreleri veri envanterinde tanımlanmamıştır."

    satirlar = []
    for kat in sorted(gruplar, key=str.casefold):
        g = gruplar[kat]
        sure = " / ".join(sorted(g["sure"])) or "BELİRLENMEDİ"
        imha = " / ".join(sorted(g["imha"])) or "BELİRLENMEDİ"
        satirlar.append(f"• {kat} — Saklama süresi: {sure}; İmha yöntemi: {imha}")
    return "\n".join(satirlar)


# --- Yapay zeka destekli bolumler ------------------------------------------

def _kapsam_olgulari(profile, rows: list[InventoryRow]) -> dict[str, Any]:
    birimler = sorted({(r.birim or "").strip() for r in rows if (r.birim or "").strip()})
    faaliyetler = sorted({(r.faaliyet or "").strip() for r in rows if (r.faaliyet or "").strip()})
    kategoriler = sorted(_cok_degerli(rows, "veri_kategorisi"), key=str.casefold)
    ozel = sorted({k for k in kategoriler if taxonomy.is_ozel_nitelikli_kategori(k)})
    yurt_disi = sorted({(r.yurt_disi_ulke or "").strip() for r in rows
                        if (r.yurt_disi_ulke or "").strip()})
    return {
        "kurum": profile.kurum or "VERİ SORUMLUSU",
        "birimler": birimler,
        "faaliyetler": faaliyetler,
        "kisi_gruplari": profile.kisi_gruplari,
        "kategoriler": kategoriler,
        "ozel_nitelikli": ozel,
        "yurt_disi_ulkeler": yurt_disi,
        "satir": len(rows),
    }


def _kapsam_yedek(o: dict[str, Any]) -> str:
    p = (f"İşbu POLİTİKA, VERİ SORUMLUSU bünyesinde yer alan {len(o['birimler'])} birimin "
         f"yürüttüğü {len(o['faaliyetler'])} kişisel veri işleme faaliyetini ve bu "
         f"faaliyetlerde işlenen {len(o['kategoriler'])} veri kategorisini kapsamaktadır. "
         f"Kapsam, VERİ SORUMLUSU'nun kişisel veri işleme envanterinde kayıtlı "
         f"{o['satir']} işleme faaliyeti ile sınırlıdır.")
    if o["ozel_nitelikli"]:
        p += (" Bu kapsamda " + ", ".join(o["ozel_nitelikli"]) + " kategorilerinde özel "
              "nitelikli kişisel veri işlenmekte olup, bu veriler bakımından KANUN'un 6 ncı "
              "maddesindeki ek şartlar ve Kurul'ca belirlenen yeterli önlemler uygulanır.")
    if o["yurt_disi_ulkeler"]:
        p += (" Envanterde " + ", ".join(o["yurt_disi_ulkeler"]) + " ülkelerine yurt dışı "
              "aktarım kaydı bulunmaktadır.")
    return p


def _risk_olgulari(kurum: str, ozet: dict[str, Any]) -> dict[str, Any]:
    bulgular = ozet.get("findings") or []
    tipler: dict[str, dict[str, Any]] = {}
    for f in bulgular:
        d = f.to_dict() if hasattr(f, "to_dict") else f
        t = tipler.setdefault(d["kod"], {"kod": d["kod"], "baslik": d["baslik"],
                                         "seviye": d["seviye"], "dayanak": d["dayanak"],
                                         "adet": 0})
        t["adet"] += 1
    # Anahtar adlari modelin uslubuna siziyor; belgeye yakisan adlandirma
    return {
        "kurum": kurum or "VERİ SORUMLUSU",
        "incelenen_faaliyet": ozet.get("satir", 0),
        "eksiksiz_faaliyet": ozet.get("temiz_satir", 0),
        "bulgu_sayisi": ozet.get("bulgu", 0),
        "uyum_orani_yuzde": round(ozet.get("uyum_orani", 0.0) * 100, 1),
        "seviyeye_gore": ozet.get("seviye", {}),
        "bulgu_tipleri": sorted(tipler.values(), key=lambda x: -x["adet"]),
    }


def _risk_yedek(o: dict[str, Any]) -> str:
    if not o["bulgu_sayisi"]:
        return ("VERİ SORUMLUSU'nun kişisel veri işleme envanteri üzerinde yürütülen son "
                f"denetimde {o['incelenen_faaliyet']} işleme faaliyetinin tamamı, saklama "
                "süresi, imha yöntemi ile teknik ve idari tedbir alanları bakımından "
                "eksiksiz bulunmuştur. Denetim, Kişisel Verilerin Korunması Komitesi "
                "tarafından düzenli olarak tekrarlanır.")
    p = (f"VERİ SORUMLUSU'nun kişisel veri işleme envanteri üzerinde yürütülen son "
         f"denetimde {o['incelenen_faaliyet']} işleme faaliyeti incelenmiş, "
         f"{o['eksiksiz_faaliyet']} faaliyet eksiksiz bulunmuş (uyum oranı "
         f"%{o['uyum_orani_yuzde']}) ve toplam {o['bulgu_sayisi']} risk bulgusu tespit "
         f"edilmiştir. Tespit edilen bulgular şunlardır: ")
    p += "; ".join(f"{t['baslik']} ({t['adet']} faaliyet, dayanak: {t['dayanak']})"
                   for t in o["bulgu_tipleri"])
    p += (". Bu bulgular için yapılması gerekenler Kişisel Verilerin Korunması Komitesi "
          "tarafından karara bağlanır ve giderilme durumu bir sonraki denetimde takip edilir.")
    return p


def _llm_yaz(llm, gorev: str, olgular: dict[str, Any], yedek: str) -> tuple[str, str]:
    # Donus: (metin, kaynak). Kaynak "yapay_zeka" veya "yedek".
    if llm is None:
        return yedek, "yedek"
    import json
    try:
        metin = llm.complete(
            [{"role": "system", "content": SISTEM},
             {"role": "user", "content": f"{gorev}\n\nOLGULAR (JSON):\n"
                                         f"{json.dumps(olgular, ensure_ascii=False, indent=1)}"}],
            temperature=0.3, max_tokens=900)
        metin = (metin or "").strip()
        # Modelin kacirdigi Markdown isaretlerini temizle
        for im in ("**", "##", "#"):
            metin = metin.replace(im, "")
        return (metin, "yapay_zeka") if len(metin) > 120 else (yedek, "yedek")
    except Exception:
        return yedek, "yedek"


# --- Toplayici --------------------------------------------------------------

def hesapla(profile, rows: list[InventoryRow], llm=None) -> tuple[dict[str, str], dict[str, str]]:
    # Donus: (placeholder -> metin, placeholder -> kaynak etiketi)
    from ..inventory.audit import audit

    sebepler = hukuki_sebepler(rows)
    degerler: dict[str, str] = {
        "hukuki_sebepler": "\n".join(f"• {s}" for s in sebepler),
        "kayit_ortamlari": kayit_ortamlari(rows),
        "saklama_ozeti": saklama_ozeti(rows),
    }
    kaynak = {k: "veritabani" for k in VERITABANI}

    ko = _kapsam_olgulari(profile, rows)
    degerler["politika_kapsam"], kaynak["politika_kapsam"] = _llm_yaz(
        llm,
        "Bir Kişisel Veri İşleme ve Koruma Politikası'nın 'Politikanın Amacı ve Kapsamı' "
        "bölümüne eklenecek, bu kuruma özgü kapsam paragrafını yaz. Hangi birimlerin, "
        "hangi faaliyetlerin ve hangi veri kategorilerinin kapsama girdiğini somut olarak "
        "belirt. Özel nitelikli veri veya yurt dışı aktarım varsa ayrıca değin. "
        "En fazla iki paragraf.",
        ko, _kapsam_yedek(ko))

    ro = _risk_olgulari(profile.kurum, audit(list(rows)))
    degerler["risk_analizi"], kaynak["risk_analizi"] = _llm_yaz(
        llm,
        "Bir Kişisel Veri İşleme ve Koruma Politikası'nın 'Risk Analizi' bölümüne "
        "eklenecek, envanter denetiminin somut sonuçlarını aktaran paragrafı yaz. "
        "Bulgu sayılarını ve dayanakları belirt, giderilme sorumluluğunun Kişisel "
        "Verilerin Korunması Komitesi'nde olduğunu yaz. Bulguları küçümseme veya "
        "abartma. En fazla iki paragraf.",
        ro, _risk_yedek(ro))

    return degerler, kaynak


# --- Veri ihlali mudahale proseduru --------------------------------------------

def ihlal_birimleri(rows: list[InventoryRow]) -> str:
    # Bolum 3: ihlal halinde departman yetkilisi ekibe katilacak birimler (envanterden)
    birimler = sorted({(r.birim or "").strip() for r in rows if (r.birim or "").strip()}, key=str.casefold)
    if not birimler:
        return "VERİ SORUMLUSU'nun kişisel veri işleyen tüm birimleri"
    return "\n".join(f"• {b}" for b in birimler)


def ihlal_veri_kategorileri(rows: list[InventoryRow]) -> str:
    # Bolum 4.4: ilgili kisiye bildirimde kullanilacak kisisel / ozel nitelikli ayrimi
    kategoriler = sorted(_cok_degerli(rows, "veri_kategorisi"), key=str.casefold)
    if not kategoriler:
        return "Veri kategorileri kişisel veri işleme envanterinde tanımlanmamıştır."
    ozel = [k for k in kategoriler if taxonomy.is_ozel_nitelikli_kategori(k)]
    genel = [k for k in kategoriler if k not in ozel]
    satirlar = [f"• {k} — özel nitelikli kişisel veri (KANUN m.6)" for k in ozel]
    satirlar += [f"• {k} — kişisel veri" for k in genel]
    return "\n".join(satirlar)


def _ihlal_olgulari(profile, rows: list[InventoryRow]) -> dict[str, Any]:
    o = _kapsam_olgulari(profile, rows)
    ortamlar = sorted(_cok_degerli(rows, "kayit_ortami"), key=str.casefold)
    alicilar = sorted(_cok_degerli(rows, "alici_grubu"), key=str.casefold)
    teknik = sorted(_cok_degerli(rows, "teknik_tedbir"), key=str.casefold)
    return {
        "kurum": o["kurum"], "birimler": o["birimler"], "faaliyet_sayisi": len(o["faaliyetler"]),
        "kategoriler": o["kategoriler"], "ozel_nitelikli": o["ozel_nitelikli"],
        "kayit_ortamlari": ortamlar, "alici_gruplari": alicilar[:15],
        "yurt_disi_ulkeler": o["yurt_disi_ulkeler"], "teknik_tedbirler": teknik[:15], "satir": o["satir"],
    }


def _ihlal_senaryo_yedek(o: dict[str, Any]) -> str:
    p = (f"VERİ SORUMLUSU bünyesinde {len(o['birimler'])} birim tarafından yürütülen {o['faaliyet_sayisi']} "
         f"işleme faaliyetinde {len(o['kategoriler'])} veri kategorisi işlenmektedir")
    p += (f"; kişisel veriler {', '.join(o['kayit_ortamlari'])} ortamlarında tutulmaktadır." if o["kayit_ortamlari"]
          else ".")
    if o["ozel_nitelikli"]:
        p += (f" {', '.join(o['ozel_nitelikli'])} kategorilerindeki özel nitelikli kişisel verilere yetkisiz erişim, "
              "ilgili kişiler bakımından en ağır sonuçları doğurabilecek ihlal senaryosudur.")
    if o["alici_gruplari"]:
        p += (f" Verilerin {', '.join(o['alici_gruplari'][:6])} gibi alıcı gruplarına aktarımı sırasında yanlış "
              "alıcıya iletim veya aktarım kanalının ele geçirilmesi de olası ihlal senaryoları arasındadır.")
    if o["yurt_disi_ulkeler"]:
        p += (f" {', '.join(o['yurt_disi_ulkeler'])} ülkelerine yapılan yurt dışı aktarımlarda aktarım güvenliğinin "
              "sağlanamaması ayrıca değerlendirilir.")
    return p


def _ihlal_risk_yedek(o: dict[str, Any], r: dict[str, Any]) -> str:
    p = (f"Kişisel veri işleme envanteri üzerinde yürütülen son denetimde {r['incelenen_faaliyet']} işleme faaliyeti "
         f"incelenmiş, toplam {r['bulgu_sayisi']} bulgu tespit edilmiştir (uyum oranı %{r['uyum_orani_yuzde']}).")
    if r["bulgu_tipleri"]:
        p += (" Bir ihlal halinde ilgili kişiler üzerindeki etkiyi artıran başlıca eksiklikler: "
              + "; ".join(f"{t['baslik']} ({t['adet']} faaliyet)" for t in r["bulgu_tipleri"][:5]) + ".")
    if o["ozel_nitelikli"]:
        p += (f" {', '.join(o['ozel_nitelikli'])} kategorilerini içeren faaliyetler, özel nitelikli kişisel veri "
              "işlendiğinden ihlal halinde yüksek riskli olarak değerlendirilir ve KURUL'a bildirimde öncelikle ele alınır.")
    p += " Risk düzeyi belirlenirken bu bulgular, ihlalin niteliği ve etkilenen kişi kategorileriyle birlikte değerlendirilir."
    return p


def ihlal_hesapla(profile, rows: list[InventoryRow], llm=None) -> tuple[dict[str, str], dict[str, str]]:
    # Veri İhlali Müdahale Prosedürü: (placeholder -> metin, placeholder -> kaynak etiketi)
    from ..inventory.audit import audit

    degerler: dict[str, str] = {
        "ihlal_birimleri": ihlal_birimleri(rows),
        "ihlal_veri_kategorileri": ihlal_veri_kategorileri(rows),
    }
    kaynak = {"ihlal_birimleri": "veritabani", "ihlal_veri_kategorileri": "veritabani"}

    o = _ihlal_olgulari(profile, rows)
    degerler["ihlal_senaryolari"], kaynak["ihlal_senaryolari"] = _llm_yaz(
        llm,
        "Bir Veri İhlali Müdahale Prosedürü'nün 'Kişisel Veri İhlali' bölümüne eklenecek, bu kuruma özgü olası ihlal "
        "senaryolarını anlatan paragrafı yaz. Hangi kayıt ortamlarında tutulan hangi veri kategorilerinin, hangi alıcı "
        "gruplarına aktarım ve yurt dışı aktarım sırasında ne tür ihlallere (kayıp, yetkisiz erişim, yanlış alıcıya "
        "iletim, siber saldırı) açık olduğunu somut belirt; özel nitelikli veriler varsa ayrıca vurgula. "
        "En fazla iki paragraf.",
        o, _ihlal_senaryo_yedek(o))

    r = _risk_olgulari(profile.kurum, audit(list(rows)))
    degerler["ihlal_risk_degerlendirmesi"], kaynak["ihlal_risk_degerlendirmesi"] = _llm_yaz(
        llm,
        "Bir Veri İhlali Müdahale Prosedürü'nün 'Risklerin Tespit Edilmesi' bölümüne eklenecek, envanter denetimi "
        "sonuçlarına dayanan kuruma özgü ihlal risk değerlendirmesi paragrafını yaz. Hangi bulguların (tedbir "
        "eksikliği, saklama süresi belirsizliği, özel nitelikli veri) bir ihlal halinde ilgili kişiler üzerindeki "
        "etkiyi artırdığını ve hangi faaliyetlerin yüksek riskli sayılacağını belirt. Bulguları küçümseme veya "
        "abartma. En fazla iki paragraf.",
        {"denetim": r, "ozel_nitelikli": o["ozel_nitelikli"], "kayit_ortamlari": o["kayit_ortamlari"]},
        _ihlal_risk_yedek(o, r))
    return degerler, kaynak
