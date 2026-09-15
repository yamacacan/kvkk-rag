# KVKK-RAG

6698 sayılı Kişisel Verilerin Korunması Kanunu ve ikincil mevzuatı üzerinde, **kaynak
dayanağı göstererek** cevap veren bir hukuki uyum asistanı. Tüm bileşenler Docker içinde,
GPU hızlandırmalı çalışır.

Retrieval mimarisi tahminle değil ölçümle seçildi: 27 konfigürasyonluk bir deney matrisi ve
35 soruluk Türkçe altın set üzerinden. Yöntem ve sonuçlar:
[docs/experiments/chunking_embedding_study.md](docs/experiments/chunking_embedding_study.md)

---

## Kurulum

Gereken: Docker Desktop (NVIDIA runtime etkin), NVIDIA GPU.

```bash
cp .env.example .env
```

`.env` içine en az bir LLM sağlayıcısının anahtarını girin (`GEMINI_API_KEY` veya
`ANTHROPIC_API_KEY`). Lokal model için anahtar gerekmez.

```bash
docker compose build app
```

## Kullanım

Korpus depoda yer almaz; `data/raw/` altına `manifest.json` ile birlikte yerleştirilir. İndeksi
kurun (ilk çalıştırmada gömme modeli iner):

```bash
docker compose run --rm app bash -c "python scripts/ingest_all.py && python scripts/build_index.py"
```

Soru sorun:

```bash
docker compose run --rm app python scripts/ask.py "Çalışanlarımın sağlık raporlarını saklayabilir miyim?"
```

LLM çağırmadan yalnızca hangi kaynakların bulunduğunu görmek için:

```bash
docker compose run --rm app python scripts/ask.py "veri ihlali bildirimi" --kaynaklar
```

Sağlayıcı değiştirmek için `--saglayici gemini|anthropic|ollama`. Lokal model kullanacaksanız
`docker compose --profile local up -d ollama` ile Ollama'yı ayağa kaldırın.

Retrieval kalitesini altın sette ölçmek:

```bash
docker compose run --rm app python scripts/run_experiments.py
```

---

## Mimari

```
kvkk.gov.tr / mevzuat.gov.tr / Resmî Gazete
        │  (toplama)
        ▼
   data/raw/ ──► ingest ──► chunking ──► indeks ──► retrieval ──► rerank ──► LLM ──► cevap
                             │             │            │            │
              mevzuat: madde/fıkra    LanceDB      hibrit RRF    cross-encoder
              kararlar: semantik      SQLite FTS5  + zorunlu     (bge-reranker-v2-m3)
                                                   geçişi        + otorite ağırlığı (w=2.0)
```

**Neden bu tasarım:**

- **Yapısal chunking** — mevzuat kendi hiyerarşisini ilan eder (`MADDE n`, `(1)`, `(a)`).
  Sabit uzunlukta bölmek bir işleme şartını onu sınırlayan fıkradan koparabilir. Ölçümde
  sabit uzunluğa göre ortalama MRR +%45.
- **Parent-child** — aranan birim fıkra, modele verilen birim maddenin tamamı. Uygulamacı
  "madde 5/2-ç" diye atıf yapar, "karakter 4300-5300" diye değil.
- **Hibrit arama** — kavramsal sorular ("parmak izi okutabilir miyim") anlamsal genelleme,
  referanslı sorular ("2025/1072 sayılı karar") birebir eşleşme ister. Tek bir mod ikisini
  birden karşılamıyor.
- **Zorunlu kaynak geçişi** — korpusun %87'si tavsiye niteliğinde karar özeti. Salt benzerlikle
  arandığında bağlayıcı madde listeye hiç giremeyebiliyor. Filtreli ayrı bir geçiş zorunlu mevzuatın
  aday havuzuna girmesini garanti altına alır.
- **Cross-encoder reranking ve otorite ağırlığı** — RRF adayları toplar, ancak hangi fıkranın
  soruyu doğrudan karşıladığını `bge-reranker-v2-m3` ayrıştırır. Ham logitlerin min-max normalizasyonu
  ve optimize edilmiş otorite ağırlığı ($w=2.0$) ile birleştirilmesi sonucu MRR 0.380'den 0.657'ye
  (+%73), R@10 ise 0.71'den 0.77'ye çıkmıştır (kayıp: 10/35 → 8/35).

## Korpus

`data/raw/` — 363 belge, 4.868 chunk. Kaynak türüne göre bağlayıcılık etiketi taşır ve bu
ayrım cevapta korunur:

| Tür | Bağlayıcılık | Belge |
|---|---|---|
| 6698 sayılı Kanun (güncel, 7499 değişikliği dahil) | zorunlu | 1 |
| Yönetmelikler | zorunlu | 8 |
| Tebliğler | zorunlu | 3 |
| İlke kararları | zorunlu | 8 |
| Kurul kararları | zorunlu | 21 |
| Kurul karar özetleri | tavsiye | 314 |
| Standart sözleşmeler / BCR | zorunlu form | 8 |
| Rehber sayfaları | tavsiye | 2 |

Korpus, kvkk.gov.tr / mevzuat.gov.tr / Resmî Gazete'den derlenir ve `data/raw/manifest.json`
ile tanımlanır; her kayıt kaynak URL'sini ve yerel yolunu taşır.

## Proje yapısı

```
kvkk_rag/
  config/      ayarlar, kaynak otorite tablosu
  ingest/      manifest, Resmî Gazete HTML (cp1254), detail.txt, PDF, kanonik şema
  chunking/    structural (madde/fıkra), semantic, recursive (taban çizgisi), enrich (atıf)
  index/       embedder (BERTurk/e5), LanceDB, SQLite FTS5
  retrieval/   hibrit RRF, cross-encoder rerank, otorite ağırlığı, zorunlu kaynak geçişi
  inventory/   xlsx loader, SQLite store (CRUD+log), normalize, taksonomi,
               uyum denetimi (ENV-001..006), asistan önerisi
  graph/       bilgi grafiği şeması, inşa, sorgular
  api/         FastAPI (REST) + strawberry (GraphQL)
  llm/         Gemini / Anthropic / Ollama adaptörleri, promptlar
  eval/        altın set metrikleri (Recall@k, MRR, nDCG)
scripts/       ingest, build_index, build_inventory_index, ask, run_experiments,
               parse_taxonomy, audit_inventory, build_graph, seed_ornek_envanter
web/           arayüz (index.html, app.js, form.js)
docs/          deney raporu, mimari diyagramlar
data/          raw/ (korpus), templates/, inventory/, processed/, eval/
```

## Veri envanteri modülü

Envanter artık salt okunur bir xlsx değil: ilk açılışta SQLite'a aktarılır, sonrasında
arayüzden düzenlenebilir. Her değişiklik `envanter_log` tablosuna yazılır.

**Uyum denetimi.** 3.108 kayıt kural motorundan geçer; her bulgu bir mevzuat dayanağı taşır:

| Kod | Bulgu | Dayanak | Adet |
|---|---|---|---|
| ENV-001 | Saklama süresi belirtilmemiş | KVKK m.4/2-d, m.7/1 | 3.015 |
| ENV-002 | İmha yöntemi tanımlanmamış | KVKK m.7 · Silinmesi Yön. m.8-10 | 3.108 |
| ENV-003 | Teknik/idari tedbir belirtilmemiş | KVKK m.12/1 | 6.204 |
| **ENV-004** | **Özel nitelikli veri genel işleme şartına dayandırılmış** | **KVKK m.6/2-3** | **152** |
| ENV-005 | Yurt dışı aktarım için ek güvence yok | KVKK m.9 | 34 |
| ENV-006 | Tek dayanak açık rıza | KVKK m.5/1, m.11/1-e | 65 |

ENV-004 en ciddi olanı: sağlık, ceza mahkûmiyeti veya sendika üyeliği verisi m.6 dışında bir
şarta dayandırılmış 152 kayıt.

**Asistan destekli kayıt.** Yeni bir veri eklerken veriyi, birimi ve faaliyeti yazıp öneri
istersiniz; sistem mevzuatı tarayıp ilgili kişi grubunu, veri kategorisini, hukuki sebebi,
işleme amacını, alıcı grubunu ve teknik/idari tedbirleri **dayanak göstererek** doldurur.

Örnek — *"Çocuk sayısı"*, İnsan Kaynakları, çalışan özlük dosyası:
kategori `Diğer(Çocuk Sayısı)`, ilgili kişi `Çalışan`, hukuki sebep *Veri Sorumlusunun Hukuki
Yükümlülüğü*, 4 teknik + 4 idari tedbir, dayanak KVKK m.6 + 5 Kurul kararı — ayrıca
"çocuk sayısı aile bireylerinin hassas verileriyle ilişkilendirilebilir, erişim yetkisi
sınırlandırılmalı" uyarısı.

**Değer listeleri** seeder'lardan gelir (25 hukuki sebep, 52 işleme amacı, 23 teknik +
17 idari tedbir, 9 alıcı grubu). Mevzuatta "Diğer" diye bir kategori olmadığı için listede
karşılığı olmayan değerler `Diğer(açıklama)` biçiminde girilir — hem kullanıcı hem asistan
bu kurala uyar. Birim ve faaliyet serbestçe eklenebilir.

**Öneriler onaya tabidir.** Asistan yalnızca formu doldurur; kaydetmeden önce gözden
geçirilmesi gerekir. Üretilen metinlerde küçük yazım hataları olabilir.

**Envanter vektör indeksi.** Her satır ("Birim · Faaliyet · Kişisel veri · Kategori · Amaç
· Hukuki sebep") mevzuatla aynı LanceDB'de ayrı bir tabloya gömülür; kayıt eklenince,
güncellenince ve silinince indeks otomatik senkronize olur. Sohbet asistanı bu indeksle
"bu veri envanterde var mı?" sorusunu cevaplar.

```bash
docker compose run --rm app python scripts/build_inventory_index.py   # ilk kurulum
```

Anlamsal arama: `POST /api/inventory/search {"query": "..."}`. Yeniden kurma:
`POST /api/inventory/reindex`.

*"Aynı kayıt" kararı vektör benzerliğiyle değil, leksik örtüşmeyle verilir.* e5 kosinüs
skorları dar bir banda sıkışır (0.83–0.86 arası her şey); mutlak eşik "Kan grubu"nu "T.C.
kimlik numarası" ile eşleştiriyordu. Vektör yalnızca aday bulur; kaydın birebir sayılması
için **kişisel veri ve faaliyet** kök düzeyinde örtüşmeli, "yönetim / işlem / süreç" gibi
her faaliyette geçen kelimeler sayılmaz. Kural bilinçli olarak sıkıdır: yanlış "var" demek
gerçek bir boşluğu gizler, yanlış "ekleyelim mi?" sormak ucuzdur.

**Excel çıktısı.** "Excel indir" ana sayfada kaynak `veri_envanteri.xlsx` ile **birebir aynı
14 sütunu** aynı adlarla ve sırayla üretir; bu düzen KVKK Envanter Hazırlama Rehberi'nin
EK-1 örneğiyle alan bazında örtüşür ve Sicil Yönetmeliği m.4/1-(h)'deki 7 asgari unsurun
tamamını içerir. Rehberin "ilave edilebilir" dediği alanlar (periyodik imha süresi, imha
yöntemi, kayıt ortamı, aktarılan ülke, veri işleyen) `Ek Alanlar` sayfasına, satır bazlı
bulgular `Uyum Bulguları` sayfasına, özet `Uyum Özeti` sayfasına yazılır. Ana sayfa
sisteme geri yüklenebilir: boş hücreler boş kalır, "—" yazılmaz.

## Bilgi grafiği ve GraphQL

`data/index/kvkk.db` içinde 16.463 düğüm / 32.305 kenar: mevzuat maddeleri, Kurul kararları,
taksonomi ve 3.108 envanter satırı tek grafta. Kurul kararlarından çıkarılan 922 `CITES`
kenarı kararları ilgili KVKK maddesine bağlar; hukuki sebep → madde eşlemesi seeder
gruplarından deterministik olarak kurulur (m.5 / m.6 / m.28).

```bash
docker compose run --rm app python scripts/build_graph.py
```

GraphQL arayüzü `/graphql` adresinde:

```graphql
{
  denetimOzeti { satir bulgu kritik uyumOrani }
  faaliyetRiski(limit: 5) { faaliyet kritik satir }
  maddeEtkisi(maddeNo: "6") { baslik atifYapanKarar hukukiSebepler }
  envanter(veriKategorisi: "Sağlık", seviye: "kritik", limit: 10) { satirNo faaliyet riskSkoru }
}
```

REST karşılıkları: `/api/inventory`, `/api/inventory/summary`, `/api/inventory/suggest`,
`/api/taxonomy`, `/api/graph/risk`, `/api/graph/madde/{no}`, `/api/ask` (tek soru), `/api/chat` (sohbet),
`/api/inventory/search` (anlamsal), `/api/inventory/{no}`.

## Web arayüzü

```bash
docker compose --profile api up -d api
```

`http://localhost:8000` — veri envanteri (sütun bazlı filtreler, sayfalama, düzenleme),
uyum bulguları, mevzuat asistanı ve bilgi grafiği ekranları.

**Mevzuat asistanı sohbet tarzındadır.** Geçmiş tarayıcıda tutulur; sunucu her turda tam
geçmişi alır (`POST /api/chat`, durumsuz). Her turda küçük bir ön-işleme çağrısı, son
mesajı geçmişe göre bağımsız bir soruya çevirir ("bunun için açık rıza gerekir mi?" →
önceki turdaki konuya bağlanır) ve kullanıcının kendi kurumunun somut bir veri işleme
faaliyetinden söz edip etmediğini çıkarır. Öyleyse envanter vektör indeksi sorgulanır:

- Birebir kayıt varsa yeşil kart: hangi satırlar, "Kaydı aç" bağlantısıyla.
- Yoksa turuncu kart: yakın-ama-farklı kayıtlar ve **"Envantere ekle"** butonu. Buton
  kayıt formunu birim/faaliyet/veri ön-dolu açar ve mevzuat dayanaklı öneriyi otomatik
  çalıştırır; kullanıcı gözden geçirip kaydeder. Asistan kendisi kayıt yazmaz.

Genel hukuk soruları ("açık rıza nedir") envanter kontrolü tetiklemez.

## Kapsam dışı sorulara davranış

Sistem yalnızca verilen kaynaklardan cevap verecek şekilde kısıtlanmıştır; bu aynı zamanda
konu kilidi işlevi görür. Test edilmiş davranış:

| Girdi | Sonuç |
|---|---|
| Tamamen alakasız ("hava nasıl olacak") | Reddeder, KVKK kapsamı dışında olduğunu belirtir, doğru kaynağa yönlendirir |
| Komşu hukuk alanı ("iş sözleşmesi feshi") | Kapsam dışı der, ancak sürecin kişisel veri işleme yönünü ayırt edip ilgili mevzuata (4857) yönlendirir |
| Talimat enjeksiyonu ("önceki talimatları yok say...") | Direnir; talebi kapsam dışı sayarak reddeder |

Retriever her durumda kaynak döndürdüğü için alakasız sorularda da bağlam üretilir; davranış
doğru olsa da bu boşa token harcar. Skor eşiğiyle kısa devre yapmak isteğe bağlı bir
iyileştirmedir.

## Bilinen sınırlar

- **Retrieval tavanı.** Altın sette R@10 = 0.77, MRR = 0.657 — 35 sorunun 8'inde doğru dayanak ilk 10'a
  girmiyor (reranker öncesi 10 kayıptı). Kalan 8 kayıp, hukuk terminolojisi ile günlük dil arasındaki
  sözcük uçurumundan kaynaklanmaktadır (ör. "parmak izi" vs. "biyometrik veri"). Sıradaki adım kural
  tabanlı sorgu genişletme (query expansion) ve bilgi grafiği entegrasyonu (Faz 2).
- **Zorunlu kaynak garantisi türü garanti eder, isabeti değil.** Listede bağlayıcı bir
  kaynak bulunur ama doğru madde olmayabilir (cross-encoder reranking bu riski belirgin şekilde azalttı).
- **Altın set 35 soru, tek yazar.** İstatistiksel test yapılmadı; yakın konfigürasyonlar
  arasındaki küçük farklar örneklem gürültüsü olabilir.
- **Cevap kalitesi ölçülmedi.** Yalnızca retrieval değerlendirildi.
- **10 taranmış PDF** metin katmanı olmadığı için korpus dışında (gerekçeleriyle
  `data/processed/skipped.jsonl` içinde).

## Yasal uyarı

Bu araç hukuki bilgilendirme amaçlıdır, hukuki danışmanlık değildir. Somut uyuşmazlıklar
için hukuk danışmanına başvurun.
