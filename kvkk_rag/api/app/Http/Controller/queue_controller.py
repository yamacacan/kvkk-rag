"""Kuyruk gozlemi (Laravel Horizon'un cok kucuk karsiligi): durum sayaclari, son isler,
basarisiz isi yeniden kuyruga alma. Denetim gunlugu izniyle (audit.view) korunur;
yeniden deneme yonetim islemi oldugu icin roles.update gerektirir."""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import Depends, HTTPException, Request

from ....database.connection import get_db
from ...Models.audit_log import AuditLog
from ...Models.job import FAILED, Job
from ...Models.user import User
from ...Services import queue as queue_service
from ..Middleware.authenticate import authenticate
from .base import Controller, route


class QueueController(Controller):
    prefix = "/api/queue"
    tags = ["kuyruk"]
    middleware = (authenticate,)

    @route("GET", "", permission="audit.view")
    def index(self, limit: int = 20, status: str | None = None,
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        q = Job.query(conn)
        if status:
            q.where("status", status)
        isler = q.order_by("id", "DESC").limit(min(limit, 200)).get()
        return {"durum": queue_service.stats(conn), "isler": [j.to_dict() for j in isler]}

    @route("POST", "/{job_id}/retry", permission="roles.update")
    def retry(self, job_id: int, request: Request, user: User = Depends(authenticate),
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        job = self.find_or_fail(Job.find(conn, job_id), "İş bulunamadı")
        if job.status != FAILED:
            raise HTTPException(409, "Yalnızca başarısız işler yeniden kuyruğa alınabilir.")
        job.retry(conn)
        AuditLog.record(conn, "queue.retry", actor=user, target_type="Is", target_id=job.id,
                        target_label=job.to_dict()["job"],
                        ip=request.client.host if request.client else None)
        queue_service.Worker.wake()
        return {"is": job.to_dict()}
