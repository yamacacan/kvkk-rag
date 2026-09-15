"""BERTurk-STS gomme katmani. CUDA varsa GPU, yoksa CPU."""
from __future__ import annotations

import functools

import numpy as np

from ..config import settings


@functools.lru_cache(maxsize=1)
def get_model():
    import torch
    from sentence_transformers import SentenceTransformer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(settings.EMBED_MODEL, device=device)
    # Model sinirini acikca sabitle: sessiz kirpma yerine bilincli kesme
    model.max_seq_length = min(model.max_seq_length, 512)
    return model


def _prefixed(texts: list[str], kind: str) -> list[str]:
    # e5 ailesi asimetrik arama icin "query:"/"passage:" oneki bekler; onsuz skorlar bozulur
    if "e5" not in settings.EMBED_MODEL.lower():
        return texts
    return [f"{kind}: {t}" for t in texts]


def embed(texts: list[str], batch_size: int | None = None, show_progress: bool = False,
          kind: str = "passage") -> np.ndarray:
    if not texts:
        return np.zeros((0, 768), dtype=np.float32)
    model = get_model()
    return model.encode(
        _prefixed(texts, kind),
        batch_size=batch_size or settings.EMBED_BATCH,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=show_progress,
    ).astype(np.float32)


def embed_query(text: str) -> np.ndarray:
    return embed([text], kind="query")[0]


def token_len(text: str) -> int:
    tok = get_model().tokenizer
    return len(tok.encode(text, add_special_tokens=True))


def device_info() -> str:
    import torch
    if torch.cuda.is_available():
        return f"cuda:{torch.cuda.get_device_name(0)}"
    return "cpu"
