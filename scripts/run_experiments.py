# Chunking x embedding x retrieval deney matrisi. Bellek ici indeks kullanir,
# uretim depolarindan (LanceDB/SQLite) bagimsizdir - tekrarlanabilirlik icin.
from __future__ import annotations

import gc
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from rank_bm25 import BM25Okapi  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

from kvkk_rag.chunking.recursive import chunk_recursive  # noqa: E402
from kvkk_rag.chunking.semantic import chunk_karar  # noqa: E402
from kvkk_rag.chunking.structural import MADDE_RE, chunk_mevzuat  # noqa: E402
from kvkk_rag.config import settings  # noqa: E402
from kvkk_rag.eval import metrics  # noqa: E402
from kvkk_rag.index import embedder  # noqa: E402
from kvkk_rag.ingest import pipeline  # noqa: E402
from kvkk_rag.ingest.models import normalize_text  # noqa: E402

RRF_K = 60
TOPK = 40
PARENT_LIMIT = 10

EMBEDDINGS = {
    "berturk-sts@75":  ("emrecan/bert-base-turkish-cased-mean-nli-stsb-tr", 75),
    "berturk-sts@512": ("emrecan/bert-base-turkish-cased-mean-nli-stsb-tr", 512),
    "e5-base@512":     ("intfloat/multilingual-e5-base", 512),
}
# e5 ailesi asimetrik arama icin onek bekler
E5_PREFIX = {"query": "query: ", "passage": "passage: "}


def load_docs() -> list:
    records = json.loads(settings.MANIFEST_PATH.read_text(encoding="utf-8"))
    docs = []
    for rec in records:
        doc, _ = pipeline.load_document(rec)
        if doc is not None:
            docs.append(doc)
    return docs


def _provenance(doc) -> str:
    # Contextual Retrieval'in deterministik, LLM'siz varyanti
    bits = [doc.belge_adi[:70]]
    if doc.karar_no:
        bits.append(doc.karar_no)
    if doc.karar_tarihi:
        bits.append(doc.karar_tarihi)
    return "[" + " · ".join(bits) + "]"


def chunk_all(docs: list, strategy: str) -> list[dict]:
    out = []
    for i, doc in enumerate(docs):
        if strategy.startswith("recursive"):
            chunks = chunk_recursive(doc, parent_ord=i)
            if strategy == "recursive+prefix":
                pre = _provenance(doc)
                for c in chunks:
                    if c.level == "child":
                        c.text = f"{pre}\n{c.text_raw}"
                        c.char_len = len(c.text)
        else:  # structural+semantic (bizim yaklasim)
            if doc.kaynak_turu in pipeline.STRUCTURAL_SOURCES and MADDE_RE.search(doc.text):
                chunks = chunk_mevzuat(doc)
            else:
                paras = doc.extra.get("paragraflar") or [
                    l.strip() for l in doc.text.splitlines() if l.strip()]
                chunks = chunk_karar(doc, paras, parent_ord=i)
        out.extend(c.to_dict() for c in chunks)
    return out


def _free_gpu(model=None) -> None:
    # 6 GB VRAM'de modelleri konfigler arasi gercekten birakmak sart; aksi halde
    # sonraki model ~300 MiB bosta calismaya calisip bellek tikanmasina giriyor.
    if model is not None:
        model.to("cpu")
        del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


def build_dense(children: list[dict], model_key: str) -> tuple[np.ndarray, SentenceTransformer]:
    name, max_len = EMBEDDINGS[model_key]
    model = SentenceTransformer(name, device="cuda" if torch.cuda.is_available() else "cpu")
    model.max_seq_length = max_len
    texts = [c["text"] for c in children]
    if "e5" in model_key:
        texts = [E5_PREFIX["passage"] + t for t in texts]
    # Uzun dizilerde batch kucultulur: 512 token x 64 ornek 6 GB'a sigmiyor
    batch = 16 if max_len > 256 else 64
    vecs = model.encode(texts, batch_size=batch, normalize_embeddings=True,
                        convert_to_numpy=True, show_progress_bar=False).astype(np.float32)
    return vecs, model


def rrf(ranked_lists: list[list[int]]) -> dict[int, float]:
    scores: dict[int, float] = {}
    for lst in ranked_lists:
        for rank, idx in enumerate(lst, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (RRF_K + rank)
    return scores


def to_parents(idxs: list[int], children: list[dict], by_id: dict[str, dict]) -> list[dict]:
    seen, out = set(), []
    for i in idxs:
        pid = children[i]["parent_id"] or children[i]["chunk_id"]
        if pid in seen:
            continue
        seen.add(pid)
        out.append(by_id.get(pid, children[i]))
        if len(out) >= PARENT_LIMIT:
            break
    return out


def run_config(model_key: str, chunks: list[dict], children: list[dict],
               by_id: dict[str, dict], bm25: BM25Okapi, gold: list[dict]) -> dict:
    t0 = time.time()
    vecs, model = build_dense(children, model_key)
    embed_sec = time.time() - t0

    results = {"dense": {}, "bm25": {}, "hybrid": {}}
    t0 = time.time()
    for q in gold:
        qtext = E5_PREFIX["query"] + q["soru"] if "e5" in model_key else q["soru"]
        qv = model.encode([qtext], normalize_embeddings=True, convert_to_numpy=True)[0]

        dense_idx = list(np.argsort(-(vecs @ qv))[:TOPK])
        bm_scores = bm25.get_scores(normalize_text(q["soru"]).split())
        bm_idx = list(np.argsort(-bm_scores)[:TOPK])
        fused = sorted(rrf([dense_idx, bm_idx]).items(), key=lambda kv: -kv[1])

        results["dense"][q["id"]] = to_parents(dense_idx, children, by_id)
        results["bm25"][q["id"]] = to_parents(bm_idx, children, by_id)
        results["hybrid"][q["id"]] = to_parents([i for i, _ in fused], children, by_id)
    query_sec = (time.time() - t0) / len(gold)

    _free_gpu(model)
    del vecs

    out = {}
    for mode, res in results.items():
        m = metrics.evaluate(res, gold)
        m.pop("per_question")
        out[mode] = {**m, "embed_sec": round(embed_sec, 1),
                     "query_ms": round(query_sec * 1000, 1)}
    return out


def main() -> None:
    gold = metrics.load_gold()
    print(f"Altin set: {len(gold)} soru | Cihaz: {'cuda' if torch.cuda.is_available() else 'cpu'}")

    docs = load_docs()
    print(f"Belge: {len(docs)}")

    all_results = {}
    for strategy in ("recursive", "recursive+prefix", "structural+semantic"):
        chunks = chunk_all(docs, strategy)
        # Semantik chunker'in GPU'da tuttugu modeli birak
        embedder.get_model.cache_clear()
        _free_gpu()

        children = [c for c in chunks if c["level"] == "child"]
        by_id = {c["chunk_id"]: c for c in chunks}
        n_child = len(children)
        lens = sorted(c["char_len"] for c in children)
        print(f"\n### {strategy}: {n_child} child (medyan {lens[len(lens)//2]} krk)", flush=True)

        # BM25 embedding modelinden bagimsiz; kol basina bir kez kurulur
        t0 = time.time()
        bm25 = BM25Okapi([normalize_text(c["text"]).split() for c in children])
        print(f"  (BM25 indeksi {time.time()-t0:.0f}s)", flush=True)

        for model_key in EMBEDDINGS:
            res = run_config(model_key, chunks, children, by_id, bm25, gold)
            for mode, m in res.items():
                key = f"{strategy} | {model_key} | {mode}"
                all_results[key] = {**m, "n_child": n_child,
                                    "medyan_krk": lens[len(lens) // 2]}
                print(f"  {model_key:<17} {mode:<7} "
                      f"R@1={m['recall@1']:.2f} R@5={m['recall@5']:.2f} "
                      f"R@10={m['recall@10']:.2f} MRR={m['mrr']:.3f} "
                      f"nDCG={m['ndcg']:.3f} kayip={m['bulunamayan']}", flush=True)

    out_path = settings.DATA_DIR / "eval" / "experiment_results.json"
    out_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSonuclar: {out_path}")


if __name__ == "__main__":
    main()
