# Cok turlu sohbet motoru. Her tur: (1) gecmise gore bagimsiz soru + envanter niyeti
# tek kucuk LLM cagrisiyla cikarilir, (2) mevzuat + envanter aranir, (3) cevap uretilir.
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ..index import lexical_store
from ..inventory import vector as inv_vector
from ..llm import prompts
from ..llm.base import Message
from ..llm.factory import get_llm
from ..retrieval import hybrid

GECMIS_TUR = 6          # LLM'e verilen son mesaj sayisi
ENVANTER_TOPK = 5

ANALIZ_SYSTEM = """Sen bir KVKK asistanının ön işleyicisisin. Sohbet geçmişi ve kullanıcının son mesajı verilecek.
Yalnızca geçerli JSON döndür:
{
  "bagimsiz_soru": "<son mesajı, geçmişe atıf yapmadan tek başına anlaşılır bir soru olarak yeniden yaz; \
mesaj zaten bağımsızsa aynen koru>",
  "envanter_ilgili": true|false,
  "kisisel_veri": "<kullanıcının kendi kurumunda işlediği/işlemeyi planladığı somut kişisel veri, yoksa null>",
  "birim": "<varsa birim/departman, yoksa null>",
  "faaliyet": "<varsa iş süreci/faaliyet, yoksa null>"
}
"envanter_ilgili" yalnızca kullanıcı KENDİ kurumunun somut bir veri işleme faaliyetinden söz ediyorsa true olur \
("çalışanlarımızın parmak izini alacağız", "müşterilerimizin TC kimlik numarasını saklıyoruz"). \
Genel hukuk sorusu ("açık rıza nedir", "m.11 ne diyor") için false. \
"kisisel_veri" alanına cümlenin tamamını değil yalnızca verinin adını yaz ("Parmak izi")."""

CHAT_EK = """
SOHBET KURALLARI:
- Bu çok turlu bir sohbettir; önceki mesajlara tutarlı kal, kullanıcı "o", "bu durumda" derse geçmişe bak.
- Kullanıcı kendi kurumunun bir veri işleme faaliyetinden söz ediyorsa ve aşağıda ENVANTER DURUMU verilmişse, \
cevabın SONUNDA tek cümleyle envanter durumunu belirt (kayıt varsa hangi satırlar; yoksa envantere eklenmesi \
gerektiğini). Bunu ayrı bir "Envanter" başlığı altında yaz. Kaydetme işlemini sen yapamazsın; kullanıcı arayüzden onaylar.
- Kısa ve doğrudan yaz; kullanıcı devam sorusu sorabilir, her şeyi tek seferde anlatmak zorunda değilsin."""


@dataclass
class Analiz:
    bagimsiz_soru: str
    envanter_ilgili: bool = False
    kisisel_veri: str | None = None
    birim: str | None = None
    faaliyet: str | None = None


@dataclass
class ChatResult:
    answer: str
    sources: list[dict[str, Any]]
    analiz: Analiz
    envanter_eslesen: list[dict[str, Any]] = field(default_factory=list)
    oneri: dict[str, Any] | None = None
    provider: str = ""


def _son_kullanici(messages: list[Message]) -> str:
    for m in reversed(messages):
        if m["role"] == "user":
            return m["content"].strip()
    return ""


def _gecmis_metni(messages: list[Message]) -> str:
    son = [m for m in messages if m["role"] in ("user", "assistant")][-GECMIS_TUR:]
    return "\n".join(f"{'KULLANICI' if m['role'] == 'user' else 'ASİSTAN'}: {m['content'][:600]}"
                     for m in son[:-1])


def _parse_json(text: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def analiz_et(messages: list[Message], llm) -> Analiz:
    soru = _son_kullanici(messages)
    gecmis = _gecmis_metni(messages)
    # Ilk mesajda gecmis yok; yine de envanter niyeti icin cagri gerekir.
    try:
        ham = llm.complete([
            {"role": "system", "content": ANALIZ_SYSTEM},
            {"role": "user", "content": f"SOHBET GEÇMİŞİ:\n{gecmis or '(yok)'}\n\nSON MESAJ: {soru}"},
        ], temperature=0.0, max_tokens=400)
        d = _parse_json(ham)
    except Exception:  # noqa: BLE001 - analiz basarisizsa ham soruyla devam
        d = {}
    temiz = lambda v: (v.strip() if isinstance(v, str) and v.strip() and v.strip().lower() != "null" else None)
    return Analiz(
        bagimsiz_soru=temiz(d.get("bagimsiz_soru")) or soru,
        envanter_ilgili=bool(d.get("envanter_ilgili")),
        kisisel_veri=temiz(d.get("kisisel_veri")),
        birim=temiz(d.get("birim")),
        faaliyet=temiz(d.get("faaliyet")),
    )


def _envanter_durumu(a: Analiz) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    # Donus: (kullaniciya gosterilecek satirlar, oneri)
    if not a.envanter_ilgili or not a.kisisel_veri:
        return [], None
    birebir, benzer = inv_vector.benzer_kayitlar(a.kisisel_veri, a.birim or "", a.faaliyet or "")
    if birebir:
        return birebir, {"tip": "envanterde_var", "kisisel_veri": a.kisisel_veri,
                         "satirlar": [b["satir_no"] for b in birebir]}
    return benzer, {"tip": "envantere_ekle", "kisisel_veri": a.kisisel_veri,
                    "birim": a.birim, "faaliyet": a.faaliyet,
                    "benzer_satirlar": [b["satir_no"] for b in benzer]}


def _envanter_baglami(eslesen: list[dict[str, Any]], oneri: dict[str, Any] | None) -> str:
    if not oneri:
        return ""
    satirlar = []
    if oneri["tip"] == "envanterde_var":
        satirlar.append(f"'{oneri['kisisel_veri']}' için envanterde birebir kayıt VAR:")
        satirlar += [f"  - Satır {r['satir_no']}: {r['text'][:160]}" for r in eslesen]
    else:
        satirlar.append(f"'{oneri['kisisel_veri']}' için envanterde birebir kayıt YOK — envantere eklenmesi gerekir.")
        if eslesen:
            satirlar.append("Yakın ama farklı mevcut kayıtlar (karıştırma, bunlar aynı kayıt değil):")
            satirlar += [f"  - Satır {r['satir_no']}: {r['text'][:160]}" for r in eslesen]
    return "\n\nENVANTER DURUMU:\n" + "\n".join(satirlar)


def chat(messages: list[Message], provider: str | None = None,
         limit: int = hybrid.PARENT_LIMIT) -> ChatResult:
    llm = get_llm(provider)
    a = analiz_et(messages, llm)

    conn = lexical_store.connect()
    try:
        rows = hybrid.search(a.bagimsiz_soru, conn=conn, limit=limit)
    finally:
        conn.close()

    eslesen, oneri = _envanter_durumu(a)

    system = prompts.SYSTEM + CHAT_EK
    kaynaklar = "\n\n".join(prompts.format_source(i, r) for i, r in enumerate(rows, start=1))
    son_soru = _son_kullanici(messages)
    gecmis = [m for m in messages if m["role"] in ("user", "assistant")][-GECMIS_TUR:-1]

    llm_messages: list[Message] = [{"role": "system", "content": system}]
    llm_messages += [{"role": m["role"], "content": m["content"]} for m in gecmis]
    llm_messages.append({"role": "user", "content":
        prompts.USER_TEMPLATE.format(soru=son_soru, kaynaklar=kaynaklar)
        + _envanter_baglami(eslesen, oneri)})

    answer = llm.complete(llm_messages)
    return ChatResult(answer=answer, sources=rows, analiz=a, envanter_eslesen=eslesen,
                      oneri=oneri, provider=getattr(llm, "name", provider or ""))
