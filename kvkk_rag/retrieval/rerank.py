# Cross-encoder yeniden siralama. Bi-encoder aday bulur, cross-encoder dogrusunu secer.
from __future__ import annotations

import functools

import numpy as np

from ..config import settings

# Parent metinleri 50k karaktere kadar cikabiliyor; cross-encoder 512 token goruyor.
# Bu yuzden eslesen child uzerinden puanlanir - zaten sorguyla eslesen kanit odur.
MAX_CHARS = 1800


@functools.lru_cache(maxsize=1)
def get_model():
    import torch
    from sentence_transformers import CrossEncoder

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CrossEncoder(settings.RERANK_MODEL, max_length=512, device=device)
    # CrossEncoder'in device parametresi modeli tasimiyor; acikca tasinmazsa CPU'da
    # kaliyor ve sorgu basina ~20 sn suruyor. fp16: e5 ile birlikte 6 GB'a sigsin.
    if device == "cuda":
        model.model.to(device).half()
    model.model.eval()
    return model


def score(query: str, passages: list[str], batch_size: int = 16) -> np.ndarray:
    # Ham logit dondurulur. sentence-transformers num_labels==1 modellerde varsayilan
    # olarak sigmoid uygular; bu logitleri ~0.001 araligina sikistirip ayrim gucunu
    # yok ediyor. Normalizasyon cagiran tarafta, aday kumesine gore yapilir.
    import torch

    if not passages:
        return np.zeros(0, dtype=np.float32)
    pairs = [[query, p[:MAX_CHARS]] for p in passages]
    return np.asarray(
        get_model().predict(pairs, batch_size=batch_size, show_progress_bar=False,
                            activation_fct=torch.nn.Identity()),
        dtype=np.float32,
    )


def normalize(scores: np.ndarray) -> np.ndarray:
    # Aday kumesi icinde min-max: otorite carpani ile ayni olcekte birlesebilsin
    if scores.size == 0:
        return scores
    lo, hi = float(scores.min()), float(scores.max())
    if hi - lo < 1e-9:
        return np.full_like(scores, 0.5)
    return (scores - lo) / (hi - lo)


def unload() -> None:
    # 6 GB VRAM'de embedder ile ayni anda yasamamasi gerekebilir
    import gc
    import torch

    get_model.cache_clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
