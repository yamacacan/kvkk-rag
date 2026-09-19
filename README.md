# KVKK-RAG

<p align="center">
  <b>Hukuki Dayanaklı KVKK Uyum Asistanı ve Veri Envanteri Yönetim Sistemi</b><br>
  <i>Production-Ready Turkish Data Protection Compliance Assistant & Data Inventory System</i>
</p>

<p align="center">
  <a href="#-english"><b>English</b></a> •
  <a href="#-türkçe"><b>Türkçe</b></a>
</p>

---

## 🇬🇧 English

A legal compliance assistant and intelligent data inventory management system built for Turkish Personal Data Protection Law No. 6698 (KVKK) and its secondary legislation, providing **verifiable legal citations** for every answer. Fully containerized with Docker and GPU acceleration.

The retrieval architecture was selected empirically through a 27-configuration benchmark matrix evaluated against a curated 35-question Turkish gold standard dataset. Methodology and detailed results: [docs/experiments/chunking_embedding_study.md](docs/experiments/chunking_embedding_study.md).

---

### Installation

**Prerequisites:** Docker Desktop (NVIDIA Container Runtime enabled), NVIDIA GPU.

```bash
cp .env.example .env
```

Add at least one LLM provider key (`GEMINI_API_KEY` or `ANTHROPIC_API_KEY`) to `.env`. No API key is required when using local models via Ollama.

```bash
docker compose build app
```

### Usage

The raw legal corpus is managed via `data/raw/manifest.json`. Build the ingestion pipeline and vector index (the embedding model will download on first run):

```bash
docker compose run --rm app bash -c "python scripts/ingest_all.py && python scripts/build_index.py"
```

Ask a compliance question:

```bash
docker compose run --rm app python scripts/ask.py "Can I retain health screening reports of my employees?"
```

Inspect retrieved legal sources without invoking an LLM:

```bash
docker compose run --rm app python scripts/ask.py "data breach notification" --kaynaklar
```

Switch LLM provider with `--saglayici gemini|anthropic|ollama`. If running a local model, launch Ollama first:
```bash
docker compose --profile local up -d ollama
```

Benchmark retrieval quality on the gold standard set:

```bash
docker compose run --rm app python scripts/run_experiments.py
```

---

### Architecture

```
kvkk.gov.tr / mevzuat.gov.tr / Official Gazette
        │  (crawled & verified)
        ▼
   data/raw/ ──► ingest ──► chunking ──► index ──► retrieval ──► rerank ──► LLM ──► response
                             │            │           │            │
              statutes: article/clause  LanceDB     hybrid RRF   cross-encoder
              decisions: semantic       SQLite FTS5 + mandatory  (bge-reranker-v2-m3)
                                                    pass         + authority weight (w=2.0)
```

**Key Architectural Decisions:**

- **Structural Chunking:** Turkish legislation defines strict legal hierarchies (`Article n`, `(1)`, `(a)`). Fixed-size chunking frequently detaches a legal processing condition from its limiting clause. Empirical evaluation demonstrated a +45% average MRR improvement over fixed-length chunking.
- **Parent-Child Retrieval:** Retrieval is executed at the granular clause/paragraph level, while full article context is provided to the LLM. Legal practitioners cite "Article 5/2-ç", not "character offset 4300–5300".
- **Hybrid Retrieval (RRF):** Conceptual questions (*"Can I scan fingerprints?"*) demand dense semantic generalization, while reference-based queries (*"Board Decision 2025/1072"*) require exact lexical matching. Hybrid reciprocal rank fusion (RRF) bridges both regimes.
- **Mandatory Source Pass:** Approximately 87% of the corpus consists of non-binding Board decision summaries. Pure dense search can easily displace mandatory statutory provisions. A filtered pass guarantees primary legislation enters the candidate pool.
- **Cross-Encoder Reranking & Authority Weighting:** While RRF retrieves candidate chunks, `bge-reranker-v2-m3` scores fine-grained relevance. Min-max normalization combined with authority weighting ($w=2.0$) increased MRR from 0.380 to 0.657 (+73%) and Recall@10 from 0.71 to 0.77.

---

### Legal Corpus

`data/raw/` comprises 363 documents and 4,868 chunks, tagged with authoritative weight preserved throughout LLM synthesis:

| Type | Binding Level | Documents |
|---|---|---|
| Law No. 6698 (Up to date, incl. Law No. 7499 amendments) | Mandatory | 1 |
| Regulations | Mandatory | 8 |
| Communiqués | Mandatory | 3 |
| Principle Decisions | Mandatory | 8 |
| Board Decisions (Formal) | Mandatory | 21 |
| Board Decision Summaries | Advisory | 314 |
| Standard Contractual Clauses / BCR | Mandatory Form | 8 |
| Official Guidelines | Advisory | 2 |

All documents are indexed in `data/raw/manifest.json` with source URLs and verification hashes.

---

### Project Structure

```
kvkk_rag/
  config/      Application settings and legal authority weight matrix
  ingest/      Manifest parser, Official Gazette HTML parser, PDF extractor, canonical schema
  chunking/    Structural (article/clause), semantic, recursive (baseline), citation enricher
  index/       Embedder (BERTurk/e5), LanceDB vector store, SQLite FTS5 lexical index
  retrieval/   Hybrid RRF, cross-encoder reranker, authority weighting, mandatory source filter
  inventory/   Excel loader/exporter, SQLite audit store (CRUD+logs), taxonomy, audit engine (ENV-001..006), AI suggester
  graph/       Knowledge graph schema, construction scripts, graph queries
  api/         FastAPI REST + Strawberry GraphQL, Laravel-style MVC layout:
                 app/Models (User, Role, Permission, PermissionScope, Envanter),
                 app/Services (ScopeResolver, ScopeFilter, PermissionCache, Auth),
                 app/Http/{Controller,Middleware,Request}, resource/ (JSON views),
                 database/{migrations,seeders}, app/{Console,Jobs,Observers,Listeners,Exports,Imports}
  llm/         Gemini, Anthropic, and Ollama adapters with specialized system prompts
  eval/        Gold standard evaluation suite (Recall@k, MRR, nDCG)
scripts/       Ingestion, indexing, benchmarking, graph building, and seeding utilities
web/           Vue 3 SPA (Vite, Vue Router, Pinia, Tailwind) — src/{views,components,stores,api,router}
docs/          Experimental benchmarking paper and architecture diagrams
data/          raw/, templates/, inventory/, processed/, eval/
```

---

### Data Inventory Management Module

The inventory is an active, auditable SQLite database synchronized in real-time. Every modification is recorded in `envanter_log`.

**Automated Compliance Auditing.** 3,108 rows run against a rule engine; each finding includes exact legal grounds:

| Code | Finding | Legal Ground | Count |
|---|---|---|---|
| ENV-001 | Retention period unspecified | KVKK Art. 4/2-d, 7/1 | 3,015 |
| ENV-002 | Disposal method undefined | KVKK Art. 7 · Deletion Reg. Art. 8-10 | 3,108 |
| ENV-003 | Technical/administrative measures missing | KVKK Art. 12/1 | 6,204 |
| **ENV-004** | **Special category data grounded on general processing condition** | **KVKK Art. 6/2-3** | **152** |
| ENV-005 | International transfer without supplementary safeguards | KVKK Art. 9 | 34 |
| ENV-006 | Explicit consent as sole legal basis | KVKK Art. 5/1, 11/1-e | 65 |

**AI-Assisted Entry.** Adding a new record prompts the assistant to inspect current statutes and auto-fill data subject groups, categories, legal grounds, processing purposes, recipient groups, and technical/administrative security measures with legal citations.

**Inventory Vector Index.** Each record is embedded into a dedicated LanceDB table and synchronized on every CRUD operation. The conversational assistant consults this index to determine whether an activity is already registered.

**Exact Excel Export.** Generates an official 14-column spreadsheet matching the KVKK Authority's Data Inventory Preparation Guide (Annex-1) and Registry Regulation Art. 4/1-(h), complete with dedicated sheets for `Supplementary Fields`, `Audit Findings`, and `Audit Summary`.

---

### Knowledge Graph & GraphQL

Over 16,463 nodes and 32,305 edges in SQLite (`data/index/kvkk.db`): articles, Board decisions, taxonomy concepts, and inventory records. 922 `CITES` edges link Board decisions to corresponding KVKK articles.

```bash
docker compose run --rm app python scripts/build_graph.py
```

Access the GraphQL playground at `http://localhost:8000/graphql`:

```graphql
{
  denetimOzeti { satir bulgu kritik uyumOrani }
  faaliyetRiski(limit: 5) { faaliyet kritik satir }
  maddeEtkisi(maddeNo: "6") { baslik atifYapanKarar hukukiSebepler }
  envanter(veriKategorisi: "Sağlık", seviye: "kritik", limit: 10) { satirNo faaliyet riskSkoru }
}
```

---

### Web Interface & API

The UI is a Vue 3 SPA (Vite, Vue Router, Pinia, Tailwind) under `web/`. Build it once, then the API serves `web/dist` with an SPA fallback:

```bash
docker compose --profile web run --rm web-build   # or: cd web && npm ci && npm run build
docker compose --profile api up -d api
```

Development with hot reload: `cd web && npm run dev` (Vite on :5173 proxies `/api` and `/graphql` to :8000). Pages: `/login`, `/sifremi-unuttum` (forgot password), `/sifre-sifirla` (reset via emailed link), then the app shell — collapsible sidebar, top bar with breadcrumb, command palette (`⌘K`: pages, users, inventory search) and user menu. The menu only shows modules the user's role permits.

- **Panel** (`/`): KPI cards, finding severity distribution, rule counts, riskiest activities, recent inventory changes; admins also see user/role/department/session counts and the latest audit entries (`GET /api/dashboard` returns only the blocks the caller is permitted to see).
- **Profilim** (`/profil`): edit name/e-mail, change password (other sessions are revoked), see roles/scopes, list and revoke active sessions (`/api/auth/sessions`).
- **Yönetim**: *Kullanıcılar* (create/edit, role assignment, department membership, activate/deactivate), *Roller & İzinler* (three-panel role editor: role list, module × action permission matrix with CRUD + special actions, per-module data-scope selector with per-action override, clone/delete), *Birimler* (departments with members and inventory counts; renaming a department also renames the inventory `Birim` values), *Kurum Profili* (organization profile — moved here from the documents page), *Denetim Günlüğü* (audit trail of auth and admin actions with before/after diffs, `GET /api/audit-logs`, permission `audit.view`).

Access `http://localhost:8000`:
- **Inventory Explorer:** Column filtering, pagination, inline editing, modal forms.
- **Compliance Audit Dashboard:** Risk metrics, filter by finding code (ENV-001..ENV-006).
- **Conversational Legal Assistant:** Multi-turn legal compliance chat with inventory checking and one-click "Add to Inventory" prepopulation.
- **Knowledge Graph Explorer:** Article impact analysis and activity risk queries.

---

### Authentication & RBAC

Every `/api/*` endpoint except `/api/health` and the auth endpoints requires `Authorization: Bearer <JWT>`. `POST /api/auth/login` returns a short-lived HS256 **access JWT** (`KVKK_JWT_TTL_MINUTES`, default 60) plus an opaque, rotating **refresh token** (`POST /api/auth/refresh`, 7 days); `POST /api/auth/logout` blacklists the JWT's `jti` until it expires. Sanctum-style `{id}|{secret}` API keys are still accepted for integrations. Password reset: `POST /api/auth/forgot-password` emails a one-time link (`KVKK_MAIL_DRIVER=log|smtp`; with `log` in `KVKK_APP_ENV=local` the link is also returned for development), `POST /api/auth/reset-password` sets the new password and revokes all sessions. Validation errors come back as `{"detail": "...", "errors": {field: [messages]}}` in Turkish. Authorization has two tiers, ported from a Laravel / Spatie-Permission architecture:

1. **Functional permission layer** (`User → Role → Permission`, format `module.action`, e.g. `inventory.view`, `findings.view`, `documents.generate`) — answers *"may the user perform this action?"*. Enforced per route by the `permission(...)` middleware (403 otherwise).
2. **Data-isolation layer** (`PermissionScope`: `(role_id, module, action) → scope`) — answers *"on which records?"*. Scope levels, by priority: `all (5) > department (4) > assigned (3) > own (2) > none (1)`.
   - `own` → `WHERE created_by = user.id`; `assigned` → `WHERE sorumlu_id = user.id OR EXISTS (envanter_denetcileri …)`; `department` → `birim IN (user's departments)` (single `department_id` + many-to-many `user_departments`).
   - Query-level: `ScopeFilter.apply(query, user, module, action)` injects the SQL predicate into the Eloquent-like `QueryBuilder` when listing. Record-level: `User.has_scoped_permission(conn, module, action, record)` checks the Spatie permission **and** the record's owner/department/assignment on `show`/`update`/`delete`.
   - Multi-role conflict resolution: the widest scope (highest priority) wins. `Superadmin` and `Admin` bypass the scope check (`all`). A permission without a scope row resolves to `none`.
3. **Versioned cache**: scope lookups are cached under `scope_v{version}_{roleIds}__{module}__{action}` (in-process by default, Redis via `KVKK_REDIS_URL`). Changing a role's permissions or scopes bumps `permission_scope_cache_version` through model observers — O(1) invalidation, no key deletion.

Seeded roles: `Superadmin`, `Admin` (bypass), `KVKK Sorumlusu` (all), `Denetçi` (assigned), `Birim Sorumlusu` (department), `Veri Giriş` (own), `İzleyici` (read-only, all). Departments are derived from the inventory's `Birim` column. The first Superadmin comes from `KVKK_ADMIN_EMAIL` / `KVKK_ADMIN_PASSWORD` (a random password is logged once if unset). Management endpoints: `/api/users`, `/api/roles` (`PUT /api/roles/{id}/scopes`), `/api/permissions`, `/api/departments`; console: `python -m kvkk_rag.api.app.Console {migrate|db:seed|user:create|user:role|role:list|permission:cache-reset}`.

---

### Out-of-Scope Handling & Safety

The system is strictly prompt-engineered and constrained to retrieved sources:

| Input | System Response |
|---|---|
| Irrelevant queries (*"What will the weather be like?"*) | Refuses politely, clarifies KVKK scope, points to official resources |
| Adjacent legal domains (*"Employment termination procedure"*) | Notes out-of-scope boundary, identifies data processing aspects, directs to Labor Code No. 4857 |
| Prompt injection (*"Ignore previous instructions..."*) | Resists injection; treats input strictly as ungrounded out-of-scope query |

---

### Legal Disclaimer

*This tool is intended for informational and compliance assistance purposes only and does not constitute formal legal counsel. For binding legal assessments, consult a qualified attorney.*

---

## 🇹🇷 Türkçe

6698 sayılı Kişisel Verilerin Korunması Kanunu ve ikincil mevzuatı üzerinde, **kaynak dayanağı göstererek** cevap veren bir hukuki uyum asistanı ve veri envanteri yönetim sistemi. Tüm bileşenler Docker içinde, GPU hızlandırmalı çalışır.

Retrieval mimarisi tahminle değil ölçümle seçildi: 27 konfigürasyonluk bir deney matrisi ve 35 soruluk Türkçe altın set üzerinden. Yöntem ve sonuçlar: [docs/experiments/chunking_embedding_study.md](docs/experiments/chunking_embedding_study.md).

---

### Kurulum

**Gereken:** Docker Desktop (NVIDIA runtime etkin), NVIDIA GPU.

```bash
cp .env.example .env
```

`.env` içine en az bir LLM sağlayıcısının anahtarını girin (`GEMINI_API_KEY` veya `ANTHROPIC_API_KEY`). Lokal model için anahtar gerekmez.

```bash
docker compose build app
```

### Kullanım

Korpus depoda yer almaz; `data/raw/` altına `manifest.json` ile birlikte yerleştirilir. İndeksi kurun (ilk çalıştırmada gömme modeli iner):

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

Sağlayıcı değiştirmek için `--saglayici gemini|anthropic|ollama`. Lokal model kullanacaksanız `docker compose --profile local up -d ollama` ile Ollama'yı ayağa kaldırın.

Retrieval kalitesini altın sette ölçmek:

```bash
docker compose run --rm app python scripts/run_experiments.py
```

---

### Mimari

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

- **Yapısal chunking** — mevzuat kendi hiyerarşisini ilan eder (`MADDE n`, `(1)`, `(a)`). Sabit uzunlukta bölmek bir işleme şartını onu sınırlayan fıkradan koparabilir. Ölçümde sabit uzunluğa göre ortalama MRR +%45.
- **Parent-child** — aranan birim fıkra, modele verilen birim maddenin tamamı. Uygulamacı "madde 5/2-ç" diye atıf yapar, "karakter 4300-5300" diye değil.
- **Hibrit arama** — kavramsal sorular ("parmak izi okutabilir miyim") anlamsal genelleme, referanslı sorular ("2025/1072 sayılı karar") birebir eşleşme ister. Tek bir mod ikisini birden karşılamıyor.
- **Zorunlu kaynak geçişi** — korpusun %87'si tavsiye niteliğinde karar özeti. Salt benzerlikle arandığında bağlayıcı madde listeye hiç giremeyebiliyor. Filtreli ayrı bir geçiş zorunlu mevzuatın aday havuzuna girmesini garanti altına alır.
- **Cross-encoder reranking ve otorite ağırlığı** — RRF adayları toplar, ancak hangi fıkranın soruyu doğrudan karşıladığını `bge-reranker-v2-m3` ayrıştırır. Ham logitlerin min-max normalizasyonu ve optimize edilmiş otorite ağırlığı ($w=2.0$) ile birleştirilmesi sonucu MRR 0.380'den 0.657'ye (+%73), R@10 ise 0.71'den 0.77'ye çıkmıştır (kayıp: 10/35 → 8/35).

---

### Korpus

`data/raw/` — 363 belge, 4.868 chunk. Kaynak türüne göre bağlayıcılık etiketi taşır ve bu ayrım cevapta korunur:

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

Korpus, kvkk.gov.tr / mevzuat.gov.tr / Resmî Gazete'den derlenir ve `data/raw/manifest.json` ile tanımlanır; her kayıt kaynak URL'sini ve yerel yolunu taşır.

---

### Proje Yapısı

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
  api/         FastAPI (REST) + strawberry (GraphQL), Laravel tarzı MVC dizini:
                 app/Models (User, Role, Permission, PermissionScope, Envanter),
                 app/Services (ScopeResolver, ScopeFilter, PermissionCache, Auth),
                 app/Http/{Controller,Middleware,Request}, resource/ (JSON görünümleri),
                 database/{migrations,seeders}, app/{Console,Jobs,Observers,Listeners,Exports,Imports}
  llm/         Gemini / Anthropic / Ollama adaptörleri, promptlar
  eval/        altın set metrikleri (Recall@k, MRR, nDCG)
scripts/       ingest, build_index, build_inventory_index, ask, run_experiments,
               parse_taxonomy, audit_inventory, build_graph, seed_ornek_envanter
web/           Vue 3 SPA (Vite, Vue Router, Pinia, Tailwind) — src/{views,components,stores,api,router}
docs/          deney raporu, mimari diyagramlar
data/          raw/ (korpus), templates/, inventory/, processed/, eval/
```

---

### Veri Envanteri Modülü

Envanter artık salt okunur bir xlsx değil: ilk açılışta SQLite'a aktarılır, sonrasında arayüzden düzenlenebilir. Her değişiklik `envanter_log` tablosuna yazılır.

**Uyum denetimi.** 3.108 kayıt kural motorundan geçer; her bulgu bir mevzuat dayanağı taşır:

| Kod | Bulgu | Dayanak | Adet |
|---|---|---|---|
| ENV-001 | Saklama süresi belirtilmemiş | KVKK m.4/2-d, m.7/1 | 3.015 |
| ENV-002 | İmha yöntemi tanımlanmamış | KVKK m.7 · Silinmesi Yön. m.8-10 | 3.108 |
| ENV-003 | Teknik/idari tedbir belirtilmemiş | KVKK m.12/1 | 6.204 |
| **ENV-004** | **Özel nitelikli veri genel işleme şartına dayandırılmış** | **KVKK m.6/2-3** | **152** |
| ENV-005 | Yurt dışı aktarım için ek güvence yok | KVKK m.9 | 34 |
| ENV-006 | Tek dayanak açık rıza | KVKK m.5/1, m.11/1-e | 65 |

ENV-004 en ciddi olanı: sağlık, ceza mahkûmiyeti veya sendika üyeliği verisi m.6 dışında bir şarta dayandırılmış 152 kayıt.

**Asistan destekli kayıt.** Yeni bir veri eklerken veriyi, birimi ve faaliyeti yazıp öneri istersiniz; sistem mevzuatı tarayıp ilgili kişi grubunu, veri kategorisini, hukuki sebebi, işleme amacını, alıcı grubunu ve teknik/idari tedbirleri **dayanak göstererek** doldurur.

**Değer listeleri** seeder'lardan gelir (25 hukuki sebep, 52 işleme amacı, 23 teknik + 17 idari tedbir, 9 alıcı grubu). Mevzuatta "Diğer" diye bir kategori olmadığı için listede karşılığı olmayan değerler `Diğer(açıklama)` biçiminde girilir — hem kullanıcı hem asistan bu kurala uyar. Birim ve faaliyet serbestçe eklenebilir.

**Envanter vektör indeksi.** Her satır ("Birim · Faaliyet · Kişisel veri · Kategori · Amaç · Hukuki sebep") mevzuatla aynı LanceDB'de ayrı bir tabloya gömülür; kayıt eklenince, güncellenince ve silinince indeks otomatik senkronize olur. Sohbet asistanı bu indeksle "bu veri envanterde var mı?" sorusunu cevaplar.

```bash
docker compose run --rm app python scripts/build_inventory_index.py   # ilk kurulum
```

Anlamsal arama: `POST /api/inventory/search {"query": "..."}`. Yeniden kurma: `POST /api/inventory/reindex`.

*"Aynı kayıt" kararı vektör benzerliğiyle değil, leksik örtüşmeyle verilir.* e5 kosinüs skorları dar bir banda sıkışır (0.83–0.86 arası her şey); mutlak eşik "Kan grubu"nu "T.C. kimlik numarası" ile eşleştiriyordu. Vektör yalnızca aday bulur; kaydın birebir sayılması için **kişisel veri ve faaliyet** kök düzeyinde örtüşmeli, "yönetim / işlem / süreç" gibi her faaliyette geçen kelimeler sayılmaz.

**Excel çıktısı.** "Excel indir" ana sayfada kaynak `veri_envanteri.xlsx` ile **birebir aynı 14 sütunu** aynı adlarla ve sırayla üretir; bu düzen KVKK Envanter Hazırlama Rehberi'nin EK-1 örneğiyle alan bazında örtüşür ve Sicil Yönetmeliği m.4/1-(h)'deki 7 asgari unsurun tamamını içerir. Rehberin "ilave edilebilir" dediği alanlar `Ek Alanlar` sayfasına, satır bazlı bulgular `Uyum Bulguları` sayfasına, özet `Uyum Özeti` sayfasına yazılır.

---

### Bilgi Grafiği ve GraphQL

`data/index/kvkk.db` içinde 16.463 düğüm / 32.305 kenar: mevzuat maddeleri, Kurul kararları, taksonomi ve 3.108 envanter satırı tek grafta. Kurul kararlarından çıkarılan 922 `CITES` kenarı kararları ilgili KVKK maddesine bağlar; hukuki sebep → madde eşlemesi seeder gruplarından deterministik olarak kurulur (m.5 / m.6 / m.28).

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

REST karşılıkları: `/api/inventory`, `/api/inventory/summary`, `/api/inventory/suggest`, `/api/taxonomy`, `/api/graph/risk`, `/api/graph/madde/{no}`, `/api/ask` (tek soru), `/api/chat` (sohbet), `/api/inventory/search` (anlamsal), `/api/inventory/{no}`.

---

### Web Arayüzü

Arayüz `web/` altında Vue 3 SPA'dır (Vite, Vue Router, Pinia, Tailwind). Bir kez derlenir; API `web/dist`'i SPA geri dönüşüyle kökten servis eder:

```bash
docker compose --profile web run --rm web-build   # ya da: cd web && npm ci && npm run build
docker compose --profile api up -d api
```

Geliştirme (anında yenileme): `cd web && npm run dev` (Vite :5173, `/api` ve `/graphql` :8000'e vekillenir). Sayfalar: `/login`, `/sifremi-unuttum`, `/sifre-sifirla` (e-postadaki bağlantı) ve uygulama kabuğu — daraltılabilir sidebar, breadcrumb'lı üst çubuk, komut paleti (`⌘K`: sayfa, kullanıcı, envanter araması) ve kullanıcı menüsü. Menüde yalnızca rolün izin verdiği modüller görünür.

- **Panel** (`/`): KPI kartları, bulgu seviye dağılımı, kural sayıları, en riskli faaliyetler, son envanter hareketleri; yöneticiler ayrıca kullanıcı/rol/birim/oturum sayıları ve son denetim günlüğü kayıtlarını görür (`GET /api/dashboard` yalnızca izinli blokları döner).
- **Profilim** (`/profil`): ad/e-posta düzenleme, şifre değiştirme (diğer oturumlar düşer), rol/kapsam görünümü, aktif oturumları listeleme ve kapatma (`/api/auth/sessions`).
- **Yönetim**: *Kullanıcılar* (oluştur/düzenle, rol atama, birim üyeliği, aktif/pasif), *Roller & İzinler* (üç panelli rol editörü: rol listesi, modül × aksiyon izin matrisi — CRUD + özel aksiyonlar —, modül başına veri kapsamı seçici ve aksiyon bazlı ince ayar, klonla/sil), *Birimler* (üyeler ve envanter sayısıyla departmanlar; birim yeniden adlandırılınca envanterdeki `Birim` değerleri de güncellenir), *Kurum Profili* (belgeler sayfasından buraya taşındı), *Denetim Günlüğü* (kimlik ve yönetim işlemlerinin önce/sonra farklarıyla izi, `GET /api/audit-logs`, izin `audit.view`).

**Ayrı deploy (frontend + API):** `VITE_API_BASE=https://api.ornek.com npm run build` ile arayüz API adresini derlemeye gömer; API tarafında `KVKK_CORS_ORIGINS=https://uygulama.ornek.com` ve `KVKK_APP_URL=https://uygulama.ornek.com` (şifre sıfırlama bağlantıları) ayarlanır. Kimlik JWT/Bearer olduğu için çerez/alan adı bağımlılığı yoktur.

`http://localhost:8000` — veri envanteri (sütun bazlı filtreler, sayfalama, düzenleme), uyum bulguları, mevzuat asistanı ve bilgi grafiği ekranları.

**Mevzuat asistanı sohbet tarzındadır.** Geçmiş tarayıcıda tutulur; sunucu her turda tam geçmişi alır (`POST /api/chat`, durumsuz). Her turda küçük bir ön-işleme çağrısı, son mesajı geçmişe göre bağımsız bir soruya çevirir ve kullanıcının kendi kurumunun somut bir veri işleme faaliyetinden söz edip etmediğini çıkarır. Öyleyse envanter vektör indeksi sorgulanır:

- Birebir kayıt varsa yeşil kart: hangi satırlar, "Kaydı aç" bağlantısıyla.
- Yoksa turuncu kart: yakın-ama-farklı kayıtlar ve **"Envantere ekle"** butonu. Buton kayıt formunu birim/faaliyet/veri ön-dolu açar ve mevzuat dayanaklı öneriyi otomatik çalıştırır; kullanıcı gözden geçirip kaydeder. Asistan kendisi kayıt yazmaz.

---

### Kimlik Doğrulama ve RBAC

`/api/health` ve kimlik uçları dışındaki tüm `/api/*` uçları `Authorization: Bearer <JWT>` ister. `POST /api/auth/login` kısa ömürlü HS256 **access JWT** (`KVKK_JWT_TTL_MINUTES`, varsayılan 60 dk) ve tek kullanımlık dönen **refresh jetonu** (`POST /api/auth/refresh`, 7 gün) verir; `POST /api/auth/logout` JWT'nin `jti`'sini süresi dolana dek kara listeye alır. Entegrasyonlar için Sanctum tarzı `{id}|{gizli}` API anahtarları da kabul edilir. Şifre sıfırlama: `POST /api/auth/forgot-password` tek kullanımlık bağlantıyı e-postalar (`KVKK_MAIL_DRIVER=log|smtp`; `log` + `KVKK_APP_ENV=local` ise bağlantı geliştirme kolaylığı için yanıtta da döner), `POST /api/auth/reset-password` yeni şifreyi yazar ve tüm oturumları düşürür. Doğrulama hataları Türkçe `{"detail": "...", "errors": {alan: [mesajlar]}}` biçimindedir. Yetkilendirme, Laravel / Spatie-Permission mimarisinin Python'a taşınmış iki kademeli hâlidir:

1. **Fonksiyonel izin katmanı** (`User → Role → Permission`, biçim `modul.aksiyon`; örn. `inventory.view`, `findings.view`, `documents.generate`) — *"kullanıcı bu eylemi yapabilir mi?"* Rota başına `permission(...)` middleware'i ile uygulanır (aksi hâlde 403).
2. **Veri izolasyon katmanı** (`PermissionScope`: `(role_id, module, action) → scope`) — *"hangi veriler üzerinde?"* Kapsam öncelikleri: `all (5) > department (4) > assigned (3) > own (2) > none (1)`.
   - `own` → `WHERE created_by = user.id`; `assigned` → `WHERE sorumlu_id = user.id OR EXISTS (envanter_denetcileri …)`; `department` → `birim IN (kullanıcının departmanları)` (tekil `department_id` + çoklu `user_departments`).
   - Sorgu seviyesi: listelemede `ScopeFilter.apply(query, user, module, action)` kapsamı Eloquent-benzeri `QueryBuilder`'a SQL koşulu olarak ekler. Kayıt seviyesi: `show`/`update`/`delete`'te `User.has_scoped_permission(conn, module, action, record)` hem Spatie iznini hem kaydın sahibi/departmanı/atamasını doğrular.
   - Çoklu rol çakışması: en geniş kapsam (en yüksek öncelik puanı) kazanır. `Superadmin` ve `Admin` kapsam kontrolünü atlar (`all`). Kapsam satırı tanımlanmamış izin `none` sayılır.
3. **Versiyonlu önbellek**: kapsam sorguları `scope_v{version}_{roleIds}__{module}__{action}` anahtarıyla saklanır (varsayılan süreç içi bellek, `KVKK_REDIS_URL` ile Redis). Rol izni veya kapsamı değişince model gözlemcileri `permission_scope_cache_version` sayacını artırır — anahtar silmeden O(1) geçersizleme.

Tohumlanan roller: `Superadmin`, `Admin` (atlar), `KVKK Sorumlusu` (all), `Denetçi` (assigned), `Birim Sorumlusu` (department), `Veri Giriş` (own), `İzleyici` (salt okunur, all). Departmanlar envanterin `Birim` sütunundan türetilir. İlk Superadmin `KVKK_ADMIN_EMAIL` / `KVKK_ADMIN_PASSWORD` ile oluşur (şifre verilmezse rastgele üretilip loga bir kez yazılır). Yönetim uçları: `/api/users`, `/api/roles` (`PUT /api/roles/{id}/scopes`), `/api/permissions`, `/api/departments`; konsol: `python -m kvkk_rag.api.app.Console {migrate|db:seed|user:create|user:role|role:list|permission:cache-reset}`.

Testler: `python -m unittest tests.test_rbac tests.test_rbac_api` (geçici SQLite; torch/lancedb gerektirmez).

---

### Kapsam Dışı Sorulara Davranış

Sistem yalnızca verilen kaynaklardan cevap verecek şekilde kısıtlanmıştır; bu aynı zamanda konu kilidi işlevi görür:

| Girdi | Sonuç |
|---|---|
| Tamamen alakasız ("hava nasıl olacak") | Reddeder, KVKK kapsamı dışında olduğunu belirtir, doğru kaynağa yönlendirir |
| Komşu hukuk alanı ("iş sözleşmesi feshi") | Kapsam dışı der, ancak sürecin kişisel veri işleme yönünü ayırt edip ilgili mevzuata (4857) yönlendirir |
| Talimat enjeksiyonu ("önceki talimatları yok say...") | Direnir; talebi kapsam dışı sayarak reddeder |

---

### Bilinen Sınırlar

- **Retrieval tavanı:** Altın sette R@10 = 0.77, MRR = 0.657 — 35 sorunun 8'inde doğru dayanak ilk 10'a girmiyor (reranker öncesi 10 kayıptı). Kalan 8 kayıp, hukuk terminolojisi ile günlük dil arasındaki sözcük uçurumundan kaynaklanmaktadır (ör. "parmak izi" vs. "biyometrik veri").
- **Zorunlu kaynak garantisi türü garanti eder, isabeti değil:** Listede bağlayıcı bir kaynak bulunur ama doğru madde olmayabilir (cross-encoder reranking bu riski belirgin şekilde azalttı).
- **Altın set 35 soru, tek yazar:** İstatistiksel test yapılmadı; yakın konfigürasyonlar arasındaki küçük farklar örneklem gürültüsü olabilir.
- **Cevap kalitesi ölçülmedi:** Yalnızca retrieval değerlendirildi.
- **10 taranmış PDF:** Metin katmanı olmadığı için korpus dışında (`data/processed/skipped.jsonl` içinde gerekçeli liste).

---

### Yasal Uyarı

Bu araç hukuki bilgilendirme amaçlıdır, hukuki danışmanlık değildir. Somut uyuşmazlıklar için hukuk danışmanına başvurun.
