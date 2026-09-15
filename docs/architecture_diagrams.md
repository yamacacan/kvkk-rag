# KVKK-RAG System Architecture Diagrams

> These Mermaid diagrams are designed for inclusion in [paper.tex](file:///c:/Users/yamac/OneDrive/Masaüstü/KVKK-RAG/docs/paper.tex).
>
> **Export instructions:** Render each diagram with [Mermaid Live Editor](https://mermaid.live) or `mmdc` CLI, export as PDF/PNG, and include in LaTeX with `\includegraphics`.

---
## 1. Experimental RAG Pipeline Architecture

The end-to-end experimental architecture from corpus ingestion and indexing to hybrid retrieval, neural reranking, and local LLM generation (excluding web/UI interfaces).

```mermaid
flowchart LR
    subgraph INPUT_STAGE["1. Query & Corpus Preparation"]
        direction TB
        QUERY["User Query<br/>(Conceptual / Referential)"]
        
        subgraph INGESTION["Corpus Ingestion (372 Documents)"]
            direction TB
            RAW_DOCS["Raw Legal Text<br/>(Laws, Regs, Decisions)"]
            CHUNKER["Structure-Aware Chunking<br/>• Legislation: Regex (MADDE n)<br/>• Decisions: Cosine Breakpoints"]
            PARENT_CHILD["Hierarchical Units<br/>Parent: Full Article / Decision<br/>Child: Paragraph with Prefix"]
            RAW_DOCS --> CHUNKER --> PARENT_CHILD
        end
    end

    subgraph INDEX_STAGE["2. Dual-Representation Indexing"]
        direction TB
        BI_ENC["Bi-Encoder<br/>multilingual-e5-base @512<br/>(Prefix: passage:)"]
        DENSE_IDX[("Vector Index<br/>LanceDB<br/>4,359 Child Embeddings")]
        BM25_IDX[("Lexical Index<br/>SQLite FTS5<br/>Tokenized Chunks + Prefixes")]
        
        PARENT_CHILD -.-> BI_ENC --> DENSE_IDX
        PARENT_CHILD -.-> BM25_IDX
    end

    subgraph RETRIEVAL_STAGE["3. Hybrid Retrieval & Scoring"]
        direction TB
        QUERY_ENC["Query Encoding<br/>(Prefix: query:)"]
        
        DENSE_SEARCH["Dense Search<br/>Cosine Similarity<br/>Top-40 Children"]
        BM25_SEARCH["Lexical Search<br/>BM25 Matching<br/>Top-40 Children"]
        MAND_PASS["Mandatory Source Pass<br/>Binding Legislation<br/>Top-10 Guaranteed"]
        
        RRF_FUSION["Reciprocal Rank Fusion<br/>RRF(d) = sum 1 / (60 + rank_i)<br/>Fused Pool"]
        AUTH_WEIGHT["Authority Calibration<br/>Score x (1 + w x (auth-1)/4)<br/>w = 2.0 Multiplier"]

        QUERY --> QUERY_ENC
        QUERY_ENC --> DENSE_SEARCH
        QUERY --> BM25_SEARCH
        QUERY --> MAND_PASS
        
        DENSE_IDX --- DENSE_SEARCH
        BM25_IDX --- BM25_SEARCH
        
        DENSE_SEARCH --> RRF_FUSION
        BM25_SEARCH --> RRF_FUSION
        MAND_PASS --> RRF_FUSION
        RRF_FUSION --> AUTH_WEIGHT
    end

    subgraph RERANK_STAGE["4. Neural Reranking & Resolution"]
        direction TB
        CROSS_ENC["Cross-Encoder<br/>BAAI/bge-reranker-v2-m3<br/>(Raw Logits + Min-Max Norm)"]
        RESOLVE["Parent Deduplication<br/>Aggregate Children to<br/>Top-12 Complete Articles"]
        
        AUTH_WEIGHT -->|"Top-80 Candidates"| CROSS_ENC
        CROSS_ENC --> RESOLVE
    end

    subgraph GEN_STAGE["5. Grounded Generation"]
        direction TB
        PROMPT["Context Assembly<br/>12 Grounded Parent Articles<br/>+ Legal Citation Prompt"]
        LOCAL_LLM["Local LLM<br/>Deterministic Generation<br/>with Exact Statutory Basis"]
        ANSWER["Final Answer<br/>with Article-Level Citations"]

        RESOLVE --> PROMPT --> LOCAL_LLM --> ANSWER
    end
```

---

## 2. Retrieval Pipeline Detail

The scoring and reranking flow for a single query.

```mermaid
flowchart LR
    Q["User Query"] --> ENCODE["Bi-Encoder<br/>e5-base @512<br/>'query: ...'"]

    ENCODE --> DENSE_S["Dense Search<br/>LanceDB<br/>cosine similarity<br/>top-40 children"]
    ENCODE --> BM25_S["BM25 Search<br/>FTS5<br/>token overlap<br/>top-40 children"]

    DENSE_S --> CHILD_MAP_D["Child → Parent<br/>Dedup"]
    BM25_S --> CHILD_MAP_L["Child → Parent<br/>Dedup"]

    subgraph MANDATORY["Mandatory Source Pass"]
        MAND_D["Dense top-10<br/>WHERE binding = 'zorunlu'"]
        MAND_L["Lexical top-10<br/>WHERE binding = 'zorunlu'"]
    end

    ENCODE --> MAND_D
    ENCODE --> MAND_L

    CHILD_MAP_D --> RRF_FUSE
    CHILD_MAP_L --> RRF_FUSE
    MAND_D --> RRF_FUSE
    MAND_L --> RRF_FUSE

    RRF_FUSE["RRF Fusion<br/>score = Σ 1/(60 + rank_i)"] --> AUTH_W["Authority Weighting<br/>score × (1 + w·(auth-1)/4)<br/>w = 2.0"]

    AUTH_W --> CE_RERANK["Cross-Encoder Reranking<br/>bge-reranker-v2-m3<br/>top-80 candidates<br/>Identity() activation<br/>min-max normalize"]

    CE_RERANK --> FINAL["Final 12 Parents<br/>R@10 = 0.77<br/>MRR = 0.657<br/>0 ungrounded"]

    style Q fill:#e94560,stroke:#333,color:#fff
    style RRF_FUSE fill:#0f3460,stroke:#16213e,color:#fff
    style AUTH_W fill:#533483,stroke:#333,color:#fff
    style CE_RERANK fill:#e94560,stroke:#333,color:#fff
    style FINAL fill:#2d6a4f,stroke:#333,color:#fff
    style MANDATORY fill:#1a1a2e,stroke:#533483,color:#e8e8e8
```

---

## 3. Chunking Strategy Comparison

How the two chunking approaches differ.

```mermaid
flowchart TB
    DOC["Raw Document<br/>(PDF / HTML)"]

    DOC --> ROUTE{"Document Type?"}

    subgraph REC["Recursive Chunking (baseline)"]
        R1["Fixed 1000-char window<br/>200-char overlap"]
        R2["Split on: \\n\\n → \\n → . → space"]
        R3["No structure awareness"]
        R1 --> R2 --> R3
    end

    subgraph STRUCT["Structural + Semantic (proposed)"]
        direction TB
        ROUTE2{"Has article<br/>markers?"}

        subgraph LEG["Legislation Path"]
            L1["Parse MADDE n regex"]
            L2["Parent = Article"]
            L3["Child = Numbered paragraph"]
            L4["Recover article heading"]
            L1 --> L2 --> L3 --> L4
        end

        subgraph DEC["Decision Path"]
            D1["Merge paragraphs<br/>~700 char target"]
            D2["Cosine similarity<br/>between consecutive units"]
            D3["Break at 5th percentile"]
            D4["Hard cap: 1300 chars"]
            D1 --> D2 --> D3 --> D4
        end

        ROUTE2 -->|Yes: kanun,<br/>yönetmelik| LEG
        ROUTE2 -->|No: karar,<br/>rehber| DEC
    end

    ROUTE -->|Any document| REC
    ROUTE -->|Routed| ROUTE2

    subgraph ENRICH["Provenance Enrichment"]
        PREFIX["Add prefix:<br/>[Law 6698 · Art. 5 —<br/>Conditions for processing]"]
        INDEX["Index prefixed text<br/>in both dense + lexical"]
        PREFIX --> INDEX
    end

    REC --> ENRICH
    LEG --> ENRICH
    DEC --> ENRICH

    ENRICH --> EMB_STORE["Embed & Store<br/>4,359 child chunks<br/>509 parent units"]

    style REC fill:#c0392b,stroke:#333,color:#fff
    style STRUCT fill:#27ae60,stroke:#333,color:#fff
    style LEG fill:#2d6a4f,stroke:#333,color:#fff
    style DEC fill:#1b4332,stroke:#333,color:#fff
    style ENRICH fill:#0f3460,stroke:#333,color:#fff
    style EMB_STORE fill:#533483,stroke:#333,color:#fff
```

---

## 4. Knowledge Graph Schema

All node types and edge relationships in the SQLite-backed graph.

```mermaid
graph TB
    MEVZUAT["📜 Mevzuat<br/>(Legislation)"]
    MADDE["📄 Madde<br/>(Article)"]
    KARAR["⚖️ Karar<br/>(Decision)"]
    VKAT["🏷️ VeriKategorisi<br/>(Data Category)"]
    HSEBEP["📋 HukukiSebep<br/>(Legal Basis)"]
    AMAC_N["🎯 IslemeAmaci<br/>(Processing Purpose)"]
    KGRUB["👥 KisiGrubu<br/>(Data Subject Group)"]
    AGRUB["📤 AliciGrubu<br/>(Recipient Group)"]
    TTEDBIR["🔒 TeknikTedbir<br/>(Technical Measure)"]
    ITEDBIR["📝 IdariTedbir<br/>(Admin Measure)"]
    BIRIM_N["🏢 Birim<br/>(Department)"]
    FAALIYET_N["⚙️ Faaliyet<br/>(Activity)"]
    ENV["📊 EnvanterSatiri<br/>(Inventory Row)"]
    BULGU_N["🚨 Bulgu<br/>(Finding)"]

    MEVZUAT -->|HAS_PART| MADDE
    KARAR -->|CITES<br/>weight=confidence| MADDE
    HSEBEP -->|TANIMLI_MADDE| MADDE
    VKAT -->|OZEL_NITELIKLI| MADDE

    ENV -->|ICERIR| VKAT
    ENV -->|DAYANAK| HSEBEP
    ENV -->|AMAC| AMAC_N
    ENV -->|ILGILI_KISI| KGRUB
    ENV -->|AKTARIR| AGRUB
    ENV -->|TEDBIR| TTEDBIR
    ENV -->|TEDBIR| ITEDBIR
    ENV -->|AIT_BIRIM| BIRIM_N
    ENV -->|AIT_FAALIYET| FAALIYET_N

    BULGU_N -->|BULGU_OF| ENV
    BULGU_N -->|IHLAL_MADDE| MADDE

    style MEVZUAT fill:#1a5276,stroke:#154360,color:#fff
    style MADDE fill:#1a5276,stroke:#154360,color:#fff
    style KARAR fill:#7d3c98,stroke:#6c3483,color:#fff
    style VKAT fill:#c0392b,stroke:#a93226,color:#fff
    style HSEBEP fill:#27ae60,stroke:#229954,color:#fff
    style ENV fill:#e67e22,stroke:#d35400,color:#fff
    style BULGU_N fill:#e74c3c,stroke:#c0392b,color:#fff
    style AMAC_N fill:#2c3e50,stroke:#1a252f,color:#fff
    style KGRUB fill:#2c3e50,stroke:#1a252f,color:#fff
    style AGRUB fill:#2c3e50,stroke:#1a252f,color:#fff
    style TTEDBIR fill:#2c3e50,stroke:#1a252f,color:#fff
    style ITEDBIR fill:#2c3e50,stroke:#1a252f,color:#fff
    style BIRIM_N fill:#2c3e50,stroke:#1a252f,color:#fff
    style FAALIYET_N fill:#2c3e50,stroke:#1a252f,color:#fff
```

---

## 5. GraphQL API Architecture

How the Strawberry GraphQL layer connects to backend modules.

```mermaid
flowchart TB
    subgraph CLIENTS["Clients"]
        WEBUI["Web UI<br/>app.js / belgeler.js"]
        PLAYGROUND["GraphQL<br/>Playground"]
        CURL["cURL / Postman"]
    end

    subgraph FASTAPI["FastAPI Server"]
        direction TB
        REST_EP["REST Endpoints<br/>/api/ask<br/>/api/health<br/>/api/sources<br/>/api/inventory<br/>/api/compliance/*"]
        GQL_ROUTER["GraphQL Router<br/>/graphql"]
    end

    subgraph GQL_SCHEMA["Strawberry GraphQL Schema"]
        direction TB
        Q_ENV["envanter(birim, faaliyet,<br/>veri_kategorisi, ...)<br/>→ EnvanterSatiri[]"]
        Q_OZET["denetim_ozeti<br/>→ DenetimOzeti"]
        Q_RISK["faaliyet_riski(limit)<br/>→ FaaliyetRisk[]"]
        Q_MEV["mevzuat_ara(soru, limit)<br/>→ Kaynak[]"]
        Q_MADDE["madde_etkisi(madde_no)<br/>→ MaddeEtkisi"]
        Q_GRAF["graf_ozeti<br/>→ JSON"]
    end

    subgraph BACKEND["Backend Modules"]
        INV_MOD["inventory/<br/>loader · audit<br/>suggest · taxonomy"]
        HYBRID_MOD["retrieval/<br/>hybrid · rerank"]
        GRAPH_MOD["graph/<br/>schema · query · build"]
        COMP_MOD["compliance/<br/>generate · profile<br/>sections · store"]
        LLM_MOD["llm/<br/>factory · prompts"]
    end

    subgraph STORES["Data Stores"]
        LANCE_S[("LanceDB<br/>vectors")]
        SQLITE_S[("SQLite<br/>FTS5 + Graph")]
        XLSX[("Excel<br/>veri_envanteri.xlsx")]
    end

    WEBUI --> REST_EP
    WEBUI --> GQL_ROUTER
    PLAYGROUND --> GQL_ROUTER
    CURL --> REST_EP

    GQL_ROUTER --> Q_ENV & Q_OZET & Q_RISK & Q_MEV & Q_MADDE & Q_GRAF

    Q_ENV --> INV_MOD
    Q_OZET --> INV_MOD
    Q_RISK --> GRAPH_MOD
    Q_MEV --> HYBRID_MOD
    Q_MADDE --> GRAPH_MOD
    Q_GRAF --> GRAPH_MOD

    REST_EP --> HYBRID_MOD
    REST_EP --> LLM_MOD
    REST_EP --> COMP_MOD
    REST_EP --> INV_MOD

    INV_MOD --> XLSX
    HYBRID_MOD --> LANCE_S
    HYBRID_MOD --> SQLITE_S
    GRAPH_MOD --> SQLITE_S

    style CLIENTS fill:#1a1a2e,stroke:#16213e,color:#e8e8e8
    style FASTAPI fill:#0f3460,stroke:#16213e,color:#e8e8e8
    style GQL_SCHEMA fill:#533483,stroke:#6c3483,color:#e8e8e8
    style BACKEND fill:#162447,stroke:#1f4068,color:#e8e8e8
    style STORES fill:#0a0a0a,stroke:#333,color:#aaa
```

---

## 6. Experiment Design & Evaluation Flow

The 3×3×3 fully crossed experiment matrix.

```mermaid
flowchart LR
    subgraph FACTORS["Experimental Factors"]
        direction TB
        CHUNK["Chunking<br/>━━━━━━━━<br/>recursive<br/>recursive+prefix<br/>structural+semantic"]
        EMBED["Embedding<br/>━━━━━━━━<br/>berturk-sts @75<br/>berturk-sts @512<br/>e5-base @512"]
        RETR["Retrieval<br/>━━━━━━━━<br/>dense<br/>bm25<br/>hybrid (RRF)"]
    end

    CROSS["3 × 3 × 3<br/>= 27 configs"]

    subgraph EVAL["Evaluation"]
        direction TB
        GOLD["Gold Set<br/>35 questions<br/>30 conceptual<br/>5 referential"]
        METRICS["Metrics<br/>━━━━━━━━<br/>Recall @{1,3,5,10}<br/>MRR<br/>nDCG<br/>miss count"]
        SPLIT["Query-Type<br/>Disaggregation"]
    end

    subgraph PRODUCTION["Production Extensions"]
        direction TB
        AUTH_EXT["Authority<br/>Weighting<br/>w ∈ {0..3.0}"]
        MAND_EXT["Mandatory<br/>Source Pass<br/>top-{5,10,20}"]
        CE_EXT["Cross-Encoder<br/>Reranking<br/>w ∈ {1..5}"]
    end

    subgraph RESULTS["Key Results"]
        direction TB
        R1["Chunking: +45% MRR"]
        R2["Embedding: +35% MRR"]
        R3["Authority: +30% MRR"]
        R4["Reranker: +73% MRR"]
        R5["Final: R@10=0.77<br/>MRR=0.657"]
    end

    CHUNK --> CROSS
    EMBED --> CROSS
    RETR --> CROSS

    CROSS --> GOLD
    GOLD --> METRICS
    METRICS --> SPLIT

    CROSS --> PRODUCTION
    PRODUCTION --> R1
    SPLIT --> R1
    R1 --- R2
    R2 --- R3
    R3 --- R4
    R4 --- R5

    style FACTORS fill:#162447,stroke:#1f4068,color:#e8e8e8
    style EVAL fill:#0f3460,stroke:#16213e,color:#e8e8e8
    style PRODUCTION fill:#533483,stroke:#6c3483,color:#e8e8e8
    style RESULTS fill:#2d6a4f,stroke:#1b4332,color:#e8e8e8
```

---

## 7. Double-Sigmoid Defect (Before/After)

The cross-encoder scoring bug and its fix.

```mermaid
flowchart TB
    subgraph BROKEN["❌ BROKEN: Double Sigmoid"]
        B_INPUT["Raw Logits<br/>-10.97 ... -5.94"]
        B_SIG1["Internal Sigmoid<br/>(CrossEncoder.predict)"]
        B_SIG2["External Sigmoid<br/>(our pipeline)"]
        B_OUTPUT["Compressed Scores<br/>~0.498 ... ~0.503<br/>188 logits → near-zero variance"]

        B_INPUT --> B_SIG1 --> B_SIG2 --> B_OUTPUT
    end

    subgraph FIXED["✅ FIXED: Identity + MinMax"]
        F_INPUT["Raw Logits<br/>-10.97 ... -5.94"]
        F_IDENTITY["Identity()<br/>activation_fct"]
        F_MINMAX["Min-Max Normalize<br/>per candidate set"]
        F_OUTPUT["Spread Scores<br/>0.00 ... 1.00<br/>full discriminative power"]

        F_INPUT --> F_IDENTITY --> F_MINMAX --> F_OUTPUT
    end

    subgraph EFFECT["Impact on Metrics"]
        E_BROKEN["Broken w=1.0:<br/>R@5=0.77 MRR=0.657<br/>(misleading: authority<br/>is sole signal)"]
        E_FIXED_1["Fixed w=1.0:<br/>R@5=0.69 MRR=0.627<br/>(CE dilutes authority)"]
        E_FIXED_2["Fixed w=2.0:<br/>R@5=0.71 MRR=0.657<br/>(recalibrated balance)"]
    end

    B_OUTPUT --> E_BROKEN
    F_OUTPUT --> E_FIXED_1
    E_FIXED_1 -->|recalibrate w| E_FIXED_2

    style BROKEN fill:#c0392b,stroke:#a93226,color:#fff
    style FIXED fill:#27ae60,stroke:#229954,color:#fff
    style EFFECT fill:#2c3e50,stroke:#1a252f,color:#fff
```

---

## How to Include in LaTeX

```bash
# Install mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Export each diagram to PDF
mmdc -i diagrams.md -o diagram-1.pdf -e pdf
# Or to PNG (300 DPI for print)
mmdc -i diagrams.md -o diagram-1.png -s 3
```

Then in `paper.tex`:
```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\columnwidth]{figures/architecture.pdf}
  \caption{End-to-end system architecture.}
  \label{fig:architecture}
\end{figure}
```
