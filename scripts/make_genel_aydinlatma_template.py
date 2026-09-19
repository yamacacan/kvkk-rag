"""Genel Aydınlatma Metni şablonunu (docx) üretir — tek sayfalık, QR kodlu genel bildirim.

Biçim mevcut şablonlardan alınır (make_veri_ihlali_template ile aynı prototipler).
Placeholder'lar: ${kurum}, ${web_adres}, ${adres}, ${cagri_merkezi}; ${qr_kod} satırına
üretimde web adresinin QR kodu (resim) yerleşir (kvkk_rag/compliance/generate._qr_yerlestir).

    python scripts/make_genel_aydinlatma_template.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_veri_ihlali_template import KAYNAK, _prototipler, _yeni_paragraf  # noqa: E402

HEDEF = Path(__file__).resolve().parents[1] / "data" / "templates" / "Genel_Aydinlatma_Metni_Sablon.docx"

# (tur, metin) — tur: orta_kalin | orta | h1_orta | p | bos
ICERIK: list[tuple[str, str]] = [
    ("orta_kalin", "T.C."),
    ("orta_kalin", "${kurum}"),
    ("h1_orta", "GENEL AYDINLATMA METNİ"),
    ("p", "Veri Sorumlusu ${kurum} olarak ilgili kişilerin kişisel verilerini azami hassasiyet göstererek korumaktayız. "
          "İşbu aydınlatma metni 6698 sayılı Kişisel Verilerin Korunması Kanunu'nun (\"KANUN\") 10. maddesi uyarınca, "
          "${kurum} tüzel kişiliğinde işlenen kişisel verilerin işlenmesine ilişkin ilgili kişilerin aydınlatılması amacı "
          "ile hazırlanmıştır."),
    ("p", "Kişisel verilerinizi KANUN'da belirtilen genel ilkeler çerçevesinde ve minimum ölçüde işlemeye gayret "
          "göstermekteyiz. Kişisel verilerinizin saklanması, muhafazası, hukuki olmayan yollarla üçüncü kişilerin eline "
          "geçmemesi için gerekli idari ve teknik tedbirleri almaktayız. Kişisel verileriniz ancak KANUN'da izin verilen "
          "hallerde işlenmekte ve aktarılmaktadır. Kişisel verileriniz KANUN'un 5. ve 6. maddesinde belirtilen şartlar "
          "çerçevesinde ve otomatik olan ve otomatik olmayan yöntemlerle işlenmektedir."),
    ("p", "KANUN'un 11. maddesinde belirtilen ilgili kişi haklarınızı ve bu kapsamdaki taleplerinizi web sitemizde yer alan "
          "başvuru formu aracılığı ile tarafımıza iletebilirsiniz. Bu kapsamda aydınlatma metinlerimizin detaylarına, "
          "kişisel verilerin korunması ve işlenmesi politikamıza ve ilgili kişi başvuru formuna ${web_adres} adresinden "
          "veya aşağıda bulunan QR kodu telefonunuzdan taratarak ulaşabilirsiniz."),
    ("orta_kalin", "QR KODU:"),
    ("orta", "${qr_kod}"),
    ("orta", "Detaylı bilgilendirme ve başvuru formu için web sitemizi ziyaret ediniz: ${web_adres}"),
    ("bos", ""),
    ("kalin", "${kurum}"),
    ("p", "${adres}"),
    ("p", "Çağrı Merkezi: ${cagri_merkezi}"),
]


def uret() -> Path:
    d = docx.Document(str(KAYNAK))
    proto = _prototipler(d)
    body = d.element.body
    sect = body.sectPr
    for el in list(body):
        body.remove(el)

    for tur, metin in ICERIK:
        if tur == "bos":
            _yeni_paragraf(body, proto["p"], "")
        elif tur == "h1_orta":
            p = _yeni_paragraf(body, proto["h1"], metin)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif tur in ("orta", "orta_kalin", "kalin"):
            p = _yeni_paragraf(body, proto["p"], metin)
            if tur != "kalin":
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if tur != "orta":
                for r in p.runs:
                    r.font.bold = True
        else:
            _yeni_paragraf(body, proto[tur], metin)

    if sect is not None:
        body.append(sect)
    d.core_properties.title = "Genel Aydınlatma Metni"
    d.save(str(HEDEF))
    return HEDEF


if __name__ == "__main__":
    print(f"Şablon yazıldı: {uret()}")
