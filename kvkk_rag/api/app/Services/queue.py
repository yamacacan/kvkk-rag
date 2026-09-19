"""Veritabani tabanli is kuyrugu (Laravel Queue facade + `database` driver + queue:work).

  Queue.push(job)            -> jobs tablosuna yazar (ShouldQueue isleri)
  Worker.run_once()          -> siradaki isi cekip calistirir; True/False
  Worker.start_thread()      -> API sureci icinde arka plan thread'i (KVKK_QUEUE_WORKER=0 ile kapatilir)
  python -m kvkk_rag.api.app.Console queue:work   -> ayri worker sureci

Basarisiz isler `jobs.status='failed'` olarak kalir (failed_jobs karsiligi);
`queue:retry --id N` ile yeniden kuyruga alinir. Olaylar: JobProcessed / JobFailed."""
from __future__ import annotations

import importlib
import logging
import os
import sqlite3
import threading
import time
import traceback
from typing import Any

from ...database.connection import connect
from ..Events import JobFailed, JobProcessed, dispatch
from ..Jobs.base import Job as JobBase
from ..Models.job import Job as JobRow

logger = logging.getLogger("kvkk_rag.api.queue")


class Queue:
    @staticmethod
    def push(job: JobBase, conn: sqlite3.Connection | None = None, user_id: int | None = None) -> JobRow:
        kendi = conn is None
        conn = conn or connect()
        try:
            kayit = JobRow.push(conn, job.path(), job.to_payload(), queue=getattr(job, "queue", "default"),
                                user_id=user_id, max_attempts=getattr(job, "max_attempts", 1))
        finally:
            if kendi:
                conn.close()
        logger.info("Kuyruga alindi #%s %s", kayit.id, type(job).__name__)
        Worker.wake()
        return kayit

    @staticmethod
    def resolve(path: str) -> type[JobBase]:
        modul, _, sinif = path.partition(":")
        m = importlib.import_module(modul)
        return getattr(m, sinif)


class Worker:
    _thread: threading.Thread | None = None
    _stop = threading.Event()
    _wake = threading.Event()

    @classmethod
    def run_once(cls, conn: sqlite3.Connection | None = None, queue: str | None = None) -> bool:
        """Bir is calistirir. Is yoksa False."""
        kendi = conn is None
        conn = conn or connect()
        try:
            kayit = JobRow.reserve_next(conn, queue)
            if kayit is None:
                return False
            cls._process(conn, kayit)
            return True
        finally:
            if kendi:
                conn.close()

    @classmethod
    def _process(cls, conn: sqlite3.Connection, kayit: JobRow) -> None:
        ad = kayit.job.rsplit(":", 1)[-1]
        t0 = time.perf_counter()
        job: JobBase | None = None
        retry_after = 30
        try:
            sinif = Queue.resolve(kayit.job)
            retry_after = int(getattr(sinif, "retry_after", 30))
            job = sinif.from_payload(kayit.data)
            job.handle()
        except Exception as e:  # noqa: BLE001 - is hatasi worker'i dusurmemeli
            hata = f"{type(e).__name__}: {e}"
            logger.warning("Is basarisiz #%s %s (deneme %s/%s): %s", kayit.id, ad, kayit.attempts,
                           kayit.max_attempts, hata)
            logger.debug("%s", traceback.format_exc())
            kayit = kayit.mark_failed(conn, hata, retry_in=retry_after)
            if kayit.status == "failed":
                if job is not None:
                    try:
                        job.failed(e)
                    except Exception:  # noqa: BLE001
                        logger.exception("%s.failed() basarisiz", ad)
                dispatch(JobFailed(job_id=kayit.id, job=ad, error=hata, user_id=kayit.get("user_id"), conn=conn))
            return
        kayit.mark_done(conn)
        sure = round((time.perf_counter() - t0) * 1000)
        logger.info("Is tamamlandi #%s %s (%s ms)", kayit.id, ad, sure)
        dispatch(JobProcessed(job_id=kayit.id, job=ad, duration_ms=sure, user_id=kayit.get("user_id"), conn=conn))

    # ---- surec ici worker thread ----
    @classmethod
    def start_thread(cls, interval: float = 2.0) -> bool:
        if os.getenv("KVKK_QUEUE_WORKER", "1") == "0":
            logger.info("Kuyruk worker thread'i kapali (KVKK_QUEUE_WORKER=0); `queue:work` ayrica calistirilmali")
            return False
        if cls._thread and cls._thread.is_alive():
            return True
        cls._stop.clear()
        cls._thread = threading.Thread(target=cls._loop, args=(interval,), name="kvkk-queue-worker", daemon=True)
        cls._thread.start()
        logger.info("Kuyruk worker thread'i basladi")
        return True

    @classmethod
    def stop_thread(cls, timeout: float = 5.0) -> None:
        cls._stop.set()
        cls._wake.set()
        if cls._thread:
            cls._thread.join(timeout)

    @classmethod
    def wake(cls) -> None:
        cls._wake.set()

    @classmethod
    def _loop(cls, interval: float) -> None:
        # Her turda: eskimis 'running' isleri serbest birak, bir is calistir; bos ise bekle
        sayac = 0
        while not cls._stop.is_set():
            try:
                conn = connect()
                try:
                    if sayac % 30 == 0:
                        JobRow.release_stale(conn)
                    calisti = cls.run_once(conn)
                finally:
                    conn.close()
            except Exception:  # noqa: BLE001
                logger.exception("Kuyruk worker turu basarisiz")
                calisti = False
            sayac += 1
            if not calisti:
                cls._wake.wait(interval)
                cls._wake.clear()

    @classmethod
    def work(cls, interval: float = 2.0, once: bool = False, queue: str | None = None) -> int:
        """`queue:work` on planda: Ctrl+C'ye kadar calisir. Donus: islenen is sayisi."""
        islenen = 0
        try:
            while True:
                conn = connect()
                try:
                    JobRow.release_stale(conn)
                    calisti = cls.run_once(conn, queue)
                finally:
                    conn.close()
                if calisti:
                    islenen += 1
                if once:
                    break
                if not calisti:
                    time.sleep(interval)
        except KeyboardInterrupt:
            pass
        return islenen


def stats(conn: sqlite3.Connection) -> dict[str, Any]:
    return {**JobRow.stats(conn), "worker": bool(Worker._thread and Worker._thread.is_alive())}
