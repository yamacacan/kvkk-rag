# Envanter uyum denetimi. Her bulgu bir mevzuat dayanagi tasir.
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Callable, Iterable

from . import normalize, taxonomy
from .loader import InventoryRow

KRITIK, YUKSEK, ORTA, DUSUK = "kritik", "yuksek", "orta", "dusuk"


@dataclass
class Finding:
    kod: str
    satir_no: int
    seviye: str
    baslik: str
    aciklama: str
    dayanak: str          # KVKK maddesi / yonetmelik
    alan: str | None = None
    mevcut_deger: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


Rule = Callable[[InventoryRow], Iterable[Finding]]
RULES: list[tuple[str, Rule]] = []


def rule(kod: str):
    def deco(fn: Rule) -> Rule:
        RULES.append((kod, fn))
        return fn
    return deco


@rule("ENV-001")
def saklama_suresi_yok(row: InventoryRow):
    # Saklama suresi belirtilmeyen kayit, "ilgili mevzuatta ongorulen sure kadar
    # muhafaza" ilkesini denetlenebilir kilmaz.
    if not row.saklama_suresi:
        yield Finding(
            "ENV-001", row.satir_no, KRITIK,
            "Saklama süresi belirtilmemiş",
            "Kişisel verinin ne kadar süreyle saklanacağı tanımlanmamış. "
            "Saklama ve İmha Politikası bu alan olmadan üretilemez.",
            "KVKK m.4/2-d, m.7/1 · Silinmesi Yönetmeliği m.5",
            "saklama_suresi", row.saklama_suresi)


@rule("ENV-002")
def imha_yontemi_yok(row: InventoryRow):
    if not row.imha_yontemi:
        yield Finding(
            "ENV-002", row.satir_no, YUKSEK,
            "İmha yöntemi tanımlanmamış",
            "Saklama süresi dolduğunda verinin silinme, yok edilme veya anonim "
            "hale getirilme yöntemi belirtilmemiş.",
            "KVKK m.7 · Silinmesi Yönetmeliği m.8-10",
            "imha_yontemi", row.imha_yontemi)


@rule("ENV-003")
def tedbir_yok(row: InventoryRow):
    if not row.teknik_tedbir:
        yield Finding(
            "ENV-003", row.satir_no, KRITIK,
            "Teknik tedbir belirtilmemiş",
            "Veri güvenliğini sağlamaya yönelik teknik tedbir kaydedilmemiş.",
            "KVKK m.12/1", "teknik_tedbir", row.teknik_tedbir)
    if not row.idari_tedbir:
        yield Finding(
            "ENV-003", row.satir_no, KRITIK,
            "İdari tedbir belirtilmemiş",
            "Veri güvenliğini sağlamaya yönelik idari tedbir kaydedilmemiş.",
            "KVKK m.12/1", "idari_tedbir", row.idari_tedbir)


@rule("ENV-004")
def ozel_nitelikli_sebep_uyumsuz(row: InventoryRow):
    # En riskli bulgu: ozel nitelikli veri, m.6 disinda bir sebebe dayandirilmis.
    kategori_ozel = row.veri_kategorisi and taxonomy.is_ozel_nitelikli_kategori(row.veri_kategorisi)
    if not (kategori_ozel or row.ozel_nitelikli_veri):
        return
    if not row.hukuki_sebep:
        yield Finding(
            "ENV-004", row.satir_no, KRITIK,
            "Özel nitelikli veri için hukuki sebep yok",
            f"'{row.veri_kategorisi}' özel nitelikli kişisel veridir; "
            "işleme şartı belirtilmemiş.",
            "KVKK m.6", "hukuki_sebep", None)
        return
    # Ad birden fazla maddede gecebilir (m.5 ve m.6'da ayni sart); m.6'da varsa uyumlu sayilir
    maddeler = taxonomy.maddeler_for_sebep(row.hukuki_sebep)
    if maddeler and "6" not in maddeler:
        madde = "/".join(sorted(maddeler, key=int))
        yield Finding(
            "ENV-004", row.satir_no, KRITIK,
            "Özel nitelikli veri genel işleme şartına dayandırılmış",
            f"'{row.veri_kategorisi}' özel nitelikli veridir ancak hukuki sebep "
            f"KVKK m.{madde} kapsamında. Özel nitelikli veriler yalnızca m.6'daki "
            "şartlarla işlenebilir.",
            "KVKK m.6/2-3", "hukuki_sebep", row.hukuki_sebep)


@rule("ENV-005")
def yurt_disi_aktarim_dayanaksiz(row: InventoryRow):
    if (row.yurt_disi_aktarim or "").strip().lower() in ("evet", "var", "true", "1"):
        yield Finding(
            "ENV-005", row.satir_no, YUKSEK,
            "Yurt dışı aktarım için ek güvence doğrulanmalı",
            "Yurt dışına aktarım yapılıyor. Yeterlilik kararı, standart sözleşme, "
            "bağlayıcı şirket kuralları veya taahhütname dayanağı kayıtlı değil.",
            "KVKK m.9 · Yurt Dışına Aktarım Yönetmeliği",
            "yurt_disi_aktarim", row.yurt_disi_aktarim)


@rule("ENV-006")
def acik_riza_tek_dayanak(row: InventoryRow):
    # Acik riza geri alinabilir; tek dayanak olmasi sureci kirilgan kilar.
    if row.hukuki_sebep and "açık rıza" in row.hukuki_sebep.lower():
        yield Finding(
            "ENV-006", row.satir_no, ORTA,
            "Tek dayanak açık rıza",
            "İşleme yalnızca açık rızaya dayandırılmış. Açık rıza her zaman geri "
            "alınabilir; mümkünse diğer işleme şartları değerlendirilmelidir.",
            "KVKK m.5/1 · m.11/1-e", "hukuki_sebep", row.hukuki_sebep)


def audit_row(row: InventoryRow) -> list[Finding]:
    out: list[Finding] = []
    for _, fn in RULES:
        out.extend(fn(row))
    return out


def audit(rows: list[InventoryRow]) -> dict[str, Any]:
    findings: list[Finding] = []
    for row in rows:
        row_findings = audit_row(row)
        row.bulgular = [f.to_dict() for f in row_findings]
        findings.extend(row_findings)

    by_level: dict[str, int] = {}
    by_code: dict[str, int] = {}
    for f in findings:
        by_level[f.seviye] = by_level.get(f.seviye, 0) + 1
        by_code[f.kod] = by_code.get(f.kod, 0) + 1

    temiz = sum(1 for r in rows if not r.bulgular)
    return {
        "satir": len(rows),
        "bulgu": len(findings),
        "temiz_satir": temiz,
        "uyum_orani": round(temiz / len(rows), 4) if rows else 0.0,
        "seviye": by_level,
        "kod": by_code,
        "findings": findings,
    }


def normalization_report(rows: list[InventoryRow]) -> dict[str, Any]:
    from .loader import unique_values
    alanlar = {
        "hukuki_sebep": "hukuki_sebep",
        "alici_grubu": "alici_grubu",
        "isleme_amaci": "isleme_amaci",
        "teknik_tedbir": "teknik_tedbir",
        "idari_tedbir": "idari_tedbir",
    }
    out: dict[str, Any] = {}
    for alan, kind in alanlar.items():
        vals = unique_values(rows, alan)
        if not vals:
            out[alan] = {"benzersiz": 0, "ozet": {}, "sorunlu": []}
            continue
        matches = normalize.match_column(vals, kind)
        sorunlu = [
            {"ham": m.ham, "kanonik": m.kanonik, "yontem": m.yontem, "guven": m.guven}
            for m in matches.values() if not m.kesin
        ]
        out[alan] = {
            "benzersiz": len(vals),
            "ozet": normalize.report(matches),
            "sorunlu": sorunlu,
        }
    return out
