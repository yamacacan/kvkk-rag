"""Is siniflari (Laravel Job).

Iki tur is vardir:
  Job                 : hafif, ayni surecte yanit dondukten sonra calisir
                        (FastAPI BackgroundTasks). Ornek: sifre e-postasi.
  Job + ShouldQueue   : `jobs` tablosuna yazilir; worker (surec ici thread ya da
                        `queue:work`) ceker ve calistirir. Ornek: belge uretimi.
                        Ozellikler JSON'a serilestirilebilir olmali (to_payload).

    class GenerateDocumentJob(Job, ShouldQueue):
        max_attempts = 1
        def __init__(self, document_id: int): ...
        def handle(self): ...
        def failed(self, error: Exception): ...   # deneme hakki bitince

    GenerateDocumentJob(5).dispatch(conn=conn, user_id=user.id)   # kuyruga
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

from fastapi import BackgroundTasks

logger = logging.getLogger("kvkk_rag.api.jobs")


class ShouldQueue:
    """Isaret sinifi: dispatch() BackgroundTasks yerine veritabani kuyruguna yazar."""
    queue: str = "default"
    max_attempts: int = 1
    retry_after: int = 30  # saniye; tekrar denemeler arasi bekleme


class Job:
    def handle(self) -> None:
        raise NotImplementedError

    def failed(self, error: Exception) -> None:  # noqa: B027 - istege bagli kanca
        pass

    # ---- kuyruk serilestirme ----
    def to_payload(self) -> dict[str, Any]:
        return {k: v for k, v in vars(self).items() if not k.startswith("_")}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "Job":
        obj = cls.__new__(cls)
        obj.__dict__.update(payload)
        return obj

    @classmethod
    def path(cls) -> str:
        return f"{cls.__module__}:{cls.__qualname__}"

    # ---- gonderim ----
    def dispatch(self, background: BackgroundTasks | None = None, *, conn: sqlite3.Connection | None = None,
                 user_id: int | None = None) -> Any:
        if isinstance(self, ShouldQueue):
            from ..Services.queue import Queue
            return Queue.push(self, conn=conn, user_id=user_id)
        if background is None:
            self.dispatch_sync()
        else:
            background.add_task(self.dispatch_sync)
        return None

    def dispatch_sync(self) -> None:
        try:
            self.handle()
        except Exception as e:  # noqa: BLE001 - arka plan isi istegi dusurmemeli
            logger.exception("%s başarısız", type(self).__name__)
            try:
                self.failed(e)
            except Exception:  # noqa: BLE001
                logger.exception("%s.failed() de başarısız", type(self).__name__)
