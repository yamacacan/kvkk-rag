# Cok turlu sohbet motoru. Her tur: (1) gecmise gore bagimsiz soru + envanter/veritabani niyeti
# tek kucuk LLM cagrisiyla cikarilir, (2) mevzuat + veritabani (kapsamli) aranir, (3) cevap uretilir.
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
  "bagimsiz_soru": "<son mesajı, geçmişe atıf yapmadan tek başına anlaşılır bir soru olarak yeniden yaz; mesaj zaten bağımsızsa aynen koru>",
  "envanter_ilgili": true|false,
  "kisisel_veri": "<kullanıcının kendi kurumunda işlediği/işlemeyi planladığı somut kişisel veri, yoksa null>",
  "birim": "<varsa birim/departman, yoksa null>",
  "faaliyet": "<varsa iş süreci/faaliyet, yoksa null>",
  "veritabani_sorgusu": true|false,
  "satir_no": <mesajda geçen, sorulan veya güncellenmesi istenen satır numarası (tam sayı, örn: 5), yoksa null>,
  "guncelleme_istegi": true|false,
  "guncellenecek_alanlar": {"<alan_adi>": "<yeni_deger>"}
}
KURALLAR:
- "envanter_ilgili": kullanıcı KENDİ kurumunun veri işleme faaliyetinden söz ediyorsa ("parmak izi alacağız", "müşteri telefonu saklıyoruz") veya envanterle ilgili soruyorsa true.
- "veritabani_sorgusu": kullanıcı veritabanındaki/envanterdeki mevcut durumu, kayıtları, listeyi ("veritabanında ne var?", "İK biriminde hangi veriler var?") veya belirli bir satırın içeriğini soruyorsa true.
- "guncelleme_istegi": kullanıcı veritabanındaki bir kaydı/satırı değiştirmek, güncellemek veya düzeltmek istiyorsa true ("5 numaralı satırın saklama süresini 10 yıl yap", "faaliyetini değiştir", "hukuki sebebini açık rıza olarak güncelle").
- "guncellenecek_alanlar": değiştirilmek istenen alanlar (örn: saklama_suresi, hukuki_sebep, faaliyet, isleme_amaci, alici_grubu, imha_yontemi, birim, kisisel_veri) ve yeni değerleri.
- "kisisel_veri" alanına cümlenin tamamını değil yalnızca verinin adını yaz ("Parmak izi")."""

CHAT_EK = """
SOHBET KURALLARI:
- Bu çok turlu bir sohbettir; önceki mesajlara tutarlı kal, kullanıcı "o", "bu durumda" derse geçmişe bak.
- Kullanıcı veritabanındaki kayıtları soruyorsa ve aşağıda GÜNCEL VERİTABANI DURUMU verilmişse, doğrudan bu kayıtları referans vererek açıkla.
- Kullanıcı bir satırı değiştirmek/güncellemek istiyorsa ve aşağıda ENVANTER GÜNCELLEME DURUMU verilmişse:
  * Eğer YETKİSİZ ise: Kullanıcıya bu kaydı güncelleme yetkisinin veya kapsamının olmadığını açık ve nazikçe belirt ("Yetki kapsamınız dışındadır" veya "inventory.update izniniz bulunmamaktadır").
  * Eğer YETKİLİ ise: Yapılacak güncellemeyi (eski değer -> yeni değer) açıkça özetle ve kullanıcının mesajın altındaki onay kartından değişikliği doğrudan uygulayabileceğini belirt.
- Kullanıcı yeni bir faaliyetten söz ediyorsa ve envantere eklenmesi gerekiyorsa, cevabın sonunda bunu belirt.
- Kısa ve doğrudan yaz; kullanıcı devam sorusu sorabilir, her şeyi tek seferde anlatmak zorunda değilsin."""


@dataclass
class Analiz:
    bagimsiz_soru: str
    envanter_ilgili: bool = False
    kisisel_veri: str | None = None
    birim: str | None = None
    faaliyet: str | None = None
    veritabani_sorgusu: bool = False
    satir_no: int | None = None
    guncelleme_istegi: bool = False
    guncellenecek_alanlar: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResult:
    answer: str
    sources: list[dict[str, Any]]
    analiz: Analiz
    envanter_eslesen: list[dict[str, Any]] = field(default_factory=list)
    oneri: dict[str, Any] | None = None
    provider: str = ""
    veritabani: dict[str, Any] | None = None


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
    try:
        ham = llm.complete([
            {"role": "system", "content": ANALIZ_SYSTEM},
            {"role": "user", "content": f"SOHBET GEÇMİŞİ:\n{gecmis or '(yok)'}\n\nSON MESAJ: {soru}"},
        ], temperature=0.0, max_tokens=500)
        d = _parse_json(ham)
    except Exception:  # noqa: BLE001 - analiz basarisizsa ham soruyla devam
        d = {}
    temiz = lambda v: (v.strip() if isinstance(v, str) and v.strip() and v.strip().lower() != "null" else None)

    satir_no_raw = d.get("satir_no")
    satir_no = None
    if isinstance(satir_no_raw, int):
        satir_no = satir_no_raw
    elif isinstance(satir_no_raw, str) and satir_no_raw.isdigit():
        satir_no = int(satir_no_raw)
    else:
        m_satir = re.search(r"(?:satır|kayıt|no|#)\s*:?\s*#?(\d+)|(\d+)\s*(?:numaralı|no'lu|\.|\s*nolu)\s*satır", soru, re.I)
        if m_satir:
            satir_no = int(m_satir.group(1) or m_satir.group(2))

    guncelleme = bool(d.get("guncelleme_istegi"))
    alanlar = d.get("guncellenecek_alanlar") if isinstance(d.get("guncellenecek_alanlar"), dict) else {}
    if not guncelleme and satir_no and any(w in soru.lower() for w in ("güncelle", "değiştir", "yap", "ata", "düzelt", "yaz")):
        guncelleme = True

    return Analiz(
        bagimsiz_soru=temiz(d.get("bagimsiz_soru")) or soru,
        envanter_ilgili=bool(d.get("envanter_ilgili")) or bool(d.get("veritabani_sorgusu")) or guncelleme,
        kisisel_veri=temiz(d.get("kisisel_veri")),
        birim=temiz(d.get("birim")),
        faaliyet=temiz(d.get("faaliyet")),
        veritabani_sorgusu=bool(d.get("veritabani_sorgusu")),
        satir_no=satir_no,
        guncelleme_istegi=guncelleme,
        guncellenecek_alanlar=alanlar,
    )


def _envanter_durumu(a: Analiz) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not a.envanter_ilgili or not a.kisisel_veri or hybrid.LOW_MEMORY_MODE:
        return [], None
    try:
        birebir, benzer = inv_vector.benzer_kayitlar(a.kisisel_veri, a.birim or "", a.faaliyet or "")
    except Exception:
        return [], None
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


def _db_baglami(can_view: bool, scope_view: str, eslesen_satirlar: list[dict[str, Any]],
                guncelleme: dict[str, Any] | None) -> str:
    parcalar = []
    if can_view and eslesen_satirlar:
        parcalar.append(f"\nGÜNCEL VERİTABANI DURUMU (Kullanıcının Görme Kapsamı: {scope_view}):")
        for s in eslesen_satirlar[:10]:
            parcalar.append(
                f"  - Satır #{s['satir_no']}: Veri: {s.get('kisisel_veri')}, Birim: {s.get('birim')}, "
                f"Faaliyet: {s.get('faaliyet')}, Hukuki Sebep: {s.get('hukuki_sebep')}, "
                f"Saklama Süresi: {s.get('saklama_suresi')}"
            )
    elif not can_view:
        parcalar.append("\nGÜNCEL VERİTABANI DURUMU: Kullanıcının veritabanını görme yetkisi ('inventory.view') yoktur.")

    if guncelleme:
        parcalar.append("\nENVANTER GÜNCELLEME DURUMU:")
        if guncelleme.get("yetkili"):
            parcalar.append(f"  - Kullanıcı Satır #{guncelleme['satir_no']} kaydını güncellemeye YETKİLİDİR (Kapsam: {guncelleme.get('kapsam')}).")
            if guncelleme.get("yeni_degerler"):
                degisiklik = ", ".join(f"{k}: '{guncelleme.get('eski_degerler', {}).get(k, '')}' -> '{v}'"
                                       for k, v in guncelleme["yeni_degerler"].items())
                parcalar.append(f"  - Önerilen Güncelleme: {degisiklik}")
        else:
            parcalar.append(f"  - Kullanıcı Satır #{guncelleme.get('satir_no')} kaydını güncellemeye YETKİSİZDİR. Neden: {guncelleme.get('sebep')}")

    return "\n".join(parcalar)


def chat(messages: list[Message], provider: str | None = None,
         limit: int = hybrid.PARENT_LIMIT,
         user: Any | None = None,
         conn: Any | None = None) -> ChatResult:
    llm = get_llm(provider)
    a = analiz_et(messages, llm)

    close_conn = False
    if conn is None:
        conn = lexical_store.connect()
        close_conn = True

    try:
        try:
            rows = hybrid.search(a.bagimsiz_soru, conn=conn, limit=limit)
        except Exception:
            rows = []

        # 1. Klasik vektor benzerlik (envantere ekle/envanterde var tespiti icin)
        eslesen, oneri = _envanter_durumu(a)

        # 2. Yetki ve kapsam denetimli canli SQLite veritabani sorgulama
        can_view = user.can(conn, "inventory.view") if user else False
        can_update = user.can(conn, "inventory.update") if user else False
        scope_view = user.scope_for(conn, "inventory", "view") if user else "none"
        scope_update = user.scope_for(conn, "inventory", "update") if user else "none"

        db_satirlar: list[dict[str, Any]] = []
        guncelleme_info: dict[str, Any] | None = None

        if user and can_view:
            from ..api.app.Services.inventory_service import InventoryService
            tum_satirlar = InventoryService.rows(conn, user, "inventory", "view")

            # Istenen satir_no varsa dogrudan o satiri bul
            if a.satir_no:
                bulunan = [r for r in tum_satirlar if r.satir_no == a.satir_no]
                db_satirlar.extend([r.to_dict() for r in bulunan])

            # Arama / filtreleme: kisisel veri, birim veya faaliyet eslesmesi
            if a.kisisel_veri or a.birim or a.faaliyet:
                kv = (a.kisisel_veri or "").lower()
                br = (a.birim or "").lower()
                fa = (a.faaliyet or "").lower()
                for r in tum_satirlar:
                    if r.satir_no == a.satir_no:
                        continue
                    if (kv and kv in (r.kisisel_veri or "").lower()) or \
                       (br and br in (r.birim or "").lower()) or \
                       (fa and fa in (r.faaliyet or "").lower()):
                        db_satirlar.append(r.to_dict())

            # Genel veritabani sorgusu varsa ilk satirlari da ekle
            if a.veritabani_sorgusu and not db_satirlar:
                db_satirlar.extend([r.to_dict() for r in tum_satirlar[:10]])

        # 3. Satir guncelleme talebi ve Spatie + Kapsam denetimi
        if user and a.guncelleme_istegi:
            from ..api.app.Services.inventory_service import InventoryService
            target_satir_no = a.satir_no
            if not target_satir_no and db_satirlar:
                target_satir_no = db_satirlar[0]["satir_no"]

            if not target_satir_no:
                guncelleme_info = {
                    "istendi": True,
                    "yetkili": False,
                    "sebep": "Hangi satırın güncellenmek istendiği belirlenemedi. Lütfen satır numarasını belirtin (örn: 'Satır 5').",
                    "satir_no": None,
                }
            else:
                kayit = InventoryService.find(conn, target_satir_no)
                if not kayit:
                    guncelleme_info = {
                        "istendi": True,
                        "yetkili": False,
                        "sebep": f"Satır #{target_satir_no} veritabanında bulunamadı.",
                        "satir_no": target_satir_no,
                    }
                elif not can_update:
                    guncelleme_info = {
                        "istendi": True,
                        "yetkili": False,
                        "sebep": "Envanter satırı güncelleme yetkiniz ('inventory.update') bulunmamaktadır.",
                        "satir_no": target_satir_no,
                        "kapsam": scope_update,
                    }
                elif not user.has_scoped_permission(conn, "inventory", "update", kayit):
                    guncelleme_info = {
                        "istendi": True,
                        "yetkili": False,
                        "sebep": f"Satır #{target_satir_no} ({kayit.get('birim') or 'Birim belirtilmemiş'}) yetki kapsamınızın ({scope_update}) dışındadır. Yalnızca kendi kapsamınızdaki satırları güncelleyebilirsiniz.",
                        "satir_no": target_satir_no,
                        "kapsam": scope_update,
                    }
                else:
                    # Yetkili: Eski ve yeni degerleri cikar
                    cur_dict = kayit.to_inventory_row().to_dict()
                    eski = {}
                    yeni = {}
                    for k, v in a.guncellenecek_alanlar.items():
                        if k in cur_dict and v:
                            eski[k] = cur_dict.get(k, "")
                            yeni[k] = v
                    if not yeni and a.guncellenecek_alanlar:
                        yeni = dict(a.guncellenecek_alanlar)

                    guncelleme_info = {
                        "istendi": True,
                        "yetkili": True,
                        "satir_no": target_satir_no,
                        "eski_degerler": eski,
                        "yeni_degerler": yeni,
                        "kapsam": scope_update,
                        "satir": cur_dict,
                    }

        veritabani_sonuc = {
            "goruntuleme_yetkisi": can_view,
            "guncelleme_yetkisi": can_update,
            "kapsam_view": scope_view,
            "kapsam_update": scope_update,
            "satirlar": db_satirlar[:10],
            "guncelleme": guncelleme_info,
        }

        system = prompts.SYSTEM + CHAT_EK
        kaynaklar = "\n\n".join(prompts.format_source(i, r) for i, r in enumerate(rows, start=1))
        if not kaynaklar:
            kaynaklar = "Doğrudan mevzuat maddesi eşleşmesi bulunamadı. Lütfen 6698 sayılı KVKK Kanunu genel hükümleri, temel ilkeler ve Kurul kararları çerçevesinde soruyu kapsamlı ve maddelere atıfta bulunarak yanıtla."
        son_soru = _son_kullanici(messages)
        gecmis = [m for m in messages if m["role"] in ("user", "assistant")][-GECMIS_TUR:-1]

        llm_messages: list[Message] = [{"role": "system", "content": system}]
        llm_messages += [{"role": m["role"], "content": m["content"]} for m in gecmis]
        llm_messages.append({"role": "user", "content":
            prompts.USER_TEMPLATE.format(soru=son_soru, kaynaklar=kaynaklar)
            + _envanter_baglami(eslesen, oneri)
            + _db_baglami(can_view, scope_view, db_satirlar, guncelleme_info)})

        answer = llm.complete(llm_messages)
        return ChatResult(
            answer=answer, sources=rows, analiz=a, envanter_eslesen=eslesen,
            oneri=oneri, provider=getattr(llm, "name", provider or ""),
            veritabani=veritabani_sonuc,
        )
    finally:
        if close_conn:
            conn.close()
