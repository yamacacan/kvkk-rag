"""Merkezi yapilandirma. Yollar konteyner icinde /app/data, host'ta proje koku."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(os.getenv("KVKK_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))

RAW_DIR = DATA_DIR / "raw"
MEVZUAT_DIR = RAW_DIR / "mevzuat"
KARARLAR_DIR = RAW_DIR / "kararlar"
REHBERLER_DIR = RAW_DIR / "rehberler"
MANIFEST_PATH = RAW_DIR / "manifest.json"

TEMPLATES_DIR = DATA_DIR / "templates"
INVENTORY_PATH = DATA_DIR / "inventory" / "veri_envanteri.xlsx"
PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "index"
LANCE_DIR = INDEX_DIR / "lance"
SQLITE_PATH = INDEX_DIR / "kvkk.db"

EMBED_MODEL = os.getenv("KVKK_EMBED_MODEL", "intfloat/multilingual-e5-base")
EMBED_MAX_TOKENS = 480  # e5-base 512 token; guvenlik payi birakiliyor
EMBED_BATCH = 16  # 512 token x 64 ornek 6 GB VRAM'e sigmiyor

# XLM-RoBERTa tabanli, 100+ dil (Turkce dahil). Sadece ~40 aday puanlanir, maliyeti dusuk.
RERANK_MODEL = os.getenv("KVKK_RERANK_MODEL", "BAAI/bge-reranker-v2-m3")

LLM_PROVIDER = os.getenv("KVKK_LLM_PROVIDER", "gemini")
GEMINI_MODEL = os.getenv("KVKK_GEMINI_MODEL", "gemini-3.5-flash-lite")
ANTHROPIC_MODEL = os.getenv("KVKK_ANTHROPIC_MODEL", "claude-sonnet-5")
OLLAMA_MODEL = os.getenv("KVKK_OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

INGEST_VERSION = "1"

# Kaynak turu -> (baglayicilik, otorite skoru). Akademik kaynaklardaki
# zorunlu/tavsiye ayrimi; cevap uretiminde ve retrieval kotasinda kullanilir.
SOURCE_AUTHORITY: dict[str, tuple[str, int]] = {
    "kanun":             ("zorunlu", 5),
    "yonetmelik":        ("zorunlu", 4),
    "teblig":            ("zorunlu", 4),
    "ilke_karari":       ("zorunlu", 4),
    "kurul_karari":      ("zorunlu", 3),
    "karar_ozeti":       ("tavsiye", 2),
    "standart_sozlesme": ("zorunlu_form", 3),
    "bcr":               ("zorunlu_form", 3),
    "rehber":            ("tavsiye", 1),
}

# manifest kategorisi -> kaynak turu
CATEGORY_TO_SOURCE: dict[str, str] = {
    "kanun": "kanun",
    "mevzuat/yonetmelikler": "yonetmelik",
    "mevzuat/tebligler": "teblig",
    "kararlar/ilke_kararlari": "ilke_karari",
    "kararlar/kurul_kararlari": "kurul_karari",
    "kararlar/kurul_karar_ozetleri": "karar_ozeti",
    "rehberler/standart_sozlesmeler": "standart_sozlesme",
    "rehberler/baglayici_sirket_kurallari": "bcr",
}


def source_type_for(category: str) -> str:
    if category in CATEGORY_TO_SOURCE:
        return CATEGORY_TO_SOURCE[category]
    if category.startswith("rehberler/kvkk_rehberleri"):
        return "rehber"
    return "rehber"
