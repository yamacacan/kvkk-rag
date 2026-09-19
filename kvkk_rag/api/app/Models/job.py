"""Kuyruk kaydi (jobs tablosu). Bir isin yasam dongusu:
  queued -> running -> done | failed (attempts < max_attempts ise tekrar queued)
Is sinifi `job` sutununda 'modul.yolu:SinifAdi' olarak, ozellikleri `payload` JSON'da."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .base import Model, now

QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"


class Job(Model):
    table = "jobs"
    fillable = ("queue", "job", "payload", "status", "attempts", "max_attempts", "user_id", "error",
                "available_at", "reserved_at", "started_at", "finished_at", "created_at", "updated_at")

    @property
    def data(self) -> dict[str, Any]:
        try:
            return json.loads(self.get("payload") or "{}")
        except ValueError:
            return {}

    @classmethod
    def push(cls, conn: sqlite3.Connection, job_path: str, payload: dict[str, Any], queue: str = "default",
             user_id: int | None = None, max_attempts: int = 1, available_at: str | None = None) -> "Job":
        return cls.create(conn, queue=queue, job=job_path,
                          payload=json.dumps(payload, ensure_ascii=False, default=str),
                          status=QUEUED, attempts=0, max_attempts=max_attempts, user_id=user_id,
                          available_at=available_at or now())

    @classmethod
    def reserve_next(cls, conn: sqlite3.Connection, queue: str | None = None) -> "Job | None":
        """Siradaki hazir isi atomik olarak ayirir (baska worker ayni isi almasin)."""
        t = now()
        conn.commit()  # acik ortuk islem varsa kapat; BEGIN IMMEDIATE ic ice islem kabul etmez
        conn.execute("BEGIN IMMEDIATE")
        try:
            sql = "SELECT id FROM jobs WHERE status = ? AND available_at <= ?"
            params: list[Any] = [QUEUED, t]
            if queue:
                sql += " AND queue = ?"
                params.append(queue)
            r = conn.execute(sql + " ORDER BY id LIMIT 1", params).fetchone()
            if not r:
                conn.execute("COMMIT")
                return None
            conn.execute("UPDATE jobs SET status = ?, reserved_at = ?, started_at = ?, attempts = attempts + 1, "
                         "updated_at = ? WHERE id = ?", (RUNNING, t, t, t, r[0]))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return cls.find(conn, r[0])

    def mark_done(self, conn: sqlite3.Connection) -> "Job":
        return self.update(conn, status=DONE, finished_at=now(), error=None)

    def mark_failed(self, conn: sqlite3.Connection, error: str, retry_in: int = 0) -> "Job":
        # Deneme hakki kaldiysa geri kuyruga; yoksa failed
        if self.attempts < self.max_attempts:
            from datetime import datetime, timedelta, timezone
            sonra = (datetime.now(timezone.utc) + timedelta(seconds=retry_in)).isoformat(timespec="seconds")
            return self.update(conn, status=QUEUED, error=error[:2000], reserved_at=None, available_at=sonra)
        return self.update(conn, status=FAILED, error=error[:2000], finished_at=now())

    def retry(self, conn: sqlite3.Connection) -> "Job":
        return self.update(conn, status=QUEUED, attempts=0, error=None, reserved_at=None,
                           started_at=None, finished_at=None, available_at=now())

    @classmethod
    def release_stale(cls, conn: sqlite3.Connection, older_than_seconds: int = 900) -> int:
        # Worker cokup 'running' kalan isler: sure asilinca tekrar kuyruga
        from datetime import datetime, timedelta, timezone
        esik = (datetime.now(timezone.utc) - timedelta(seconds=older_than_seconds)).isoformat(timespec="seconds")
        return cls.query(conn).where("status", RUNNING).where("reserved_at", "<", esik).update(
            {"status": QUEUED, "reserved_at": None, "updated_at": now()})

    @classmethod
    def stats(cls, conn: sqlite3.Connection) -> dict[str, int]:
        out = {QUEUED: 0, RUNNING: 0, DONE: 0, FAILED: 0}
        for durum, n in conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status"):
            out[durum] = int(n)
        return out

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["payload"] = self.data
        d["job"] = (d.get("job") or "").rsplit(":", 1)[-1]  # arayuze yalnizca sinif adi
        return d
