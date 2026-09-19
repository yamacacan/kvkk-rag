"""Mevzuat asistani: tek soru (/api/ask) ve sohbet (/api/chat). Retrieval ve LLM
modulleri agir (torch); istek aninda tembel import edilir."""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

from fastapi import Depends, HTTPException

from ....database.connection import get_db
from ....resource import SourceResource
from ...Models.user import User
from ..Middleware.authenticate import authenticate
from ..Request.chat import AskRequest, ChatRequest
from .base import Controller, route

logger = logging.getLogger("kvkk_rag.api.chat")


class ChatController(Controller):
    prefix = "/api"
    tags = ["asistan"]
    middleware = (authenticate,)

    @route("POST", "/ask", permission="chat.use")
    def ask(self, req: AskRequest) -> dict[str, Any]:
        from .....index import lexical_store
        from .....llm import prompts
        from .....llm.factory import get_llm
        from .....retrieval import hybrid

        query_text = req.query.strip()
        if not query_text:
            raise HTTPException(status_code=400, detail="Soru metni boş olamaz.")

        conn = lexical_store.connect()
        try:
            rows = hybrid.search(query_text, conn=conn, limit=req.limit or hybrid.PARENT_LIMIT)
        except Exception as e:  # noqa: BLE001
            logger.exception("Retrieval hatası")
            raise HTTPException(status_code=500, detail=f"Arama sırasında hata oluştu: {e}")
        finally:
            conn.close()

        sources = SourceResource.collection(rows)
        if req.sources_only:
            return {"query": query_text, "answer": None, "provider": None, "sources": sources}

        llm = None
        try:
            llm = get_llm(req.provider)
            answer = llm.complete(prompts.build_messages(query_text, rows))
        except Exception as e:  # noqa: BLE001
            logger.exception("LLM tamamlama hatası")
            answer = (f"⚠️ LLM yanıtı oluşturulurken hata meydana geldi: {e}\n\n"
                      "(Kaynaklar başarıyla getirildi.)")
        return {"query": query_text, "answer": answer,
                "provider": getattr(llm, "name", req.provider or "unknown"),
                "sources": sources}

    @route("POST", "/chat", permission="chat.use")
    def chat(self, req: ChatRequest, user: User = Depends(authenticate),
             conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        from .....chat import engine as chat_engine
        from .....retrieval import hybrid

        # Durum sunucuda tutulmaz; gecmis tarayicidan her turda gelir.
        msgs = [{"role": m.role, "content": m.content} for m in req.messages
                if m.role in ("user", "assistant") and m.content.strip()]
        if not msgs or msgs[-1]["role"] != "user":
            raise HTTPException(400, "Son mesaj kullanıcıya ait olmalı.")
        try:
            r = chat_engine.chat(
                msgs, provider=req.provider, limit=req.limit or hybrid.PARENT_LIMIT,
                user=user, conn=conn,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Sohbet hatası")
            raise HTTPException(500, f"Sohbet sırasında hata: {e}")

        envanter_dict: dict[str, Any] = {
            "eslesen": [{k: v for k, v in e.items() if k != "text"} | {"ozet": e.get("text", "")[:200]}
                        for e in r.envanter_eslesen],
            "oneri": r.oneri,
        }
        if r.veritabani:
            envanter_dict["goruntuleme_yetkisi"] = r.veritabani.get("goruntuleme_yetkisi", False)
            envanter_dict["guncelleme_yetkisi"] = r.veritabani.get("guncelleme_yetkisi", False)
            envanter_dict["kapsam_view"] = r.veritabani.get("kapsam_view", "none")
            envanter_dict["kapsam_update"] = r.veritabani.get("kapsam_update", "none")
            envanter_dict["satirlar"] = r.veritabani.get("satirlar", [])
            envanter_dict["guncelleme"] = r.veritabani.get("guncelleme")

        return {
            "answer": r.answer, "provider": r.provider,
            "sources": SourceResource.collection(r.sources),
            "analiz": {"bagimsiz_soru": r.analiz.bagimsiz_soru,
                       "envanter_ilgili": r.analiz.envanter_ilgili,
                       "kisisel_veri": r.analiz.kisisel_veri,
                       "birim": r.analiz.birim, "faaliyet": r.analiz.faaliyet,
                       "satir_no": r.analiz.satir_no,
                       "veritabani_sorgusu": r.analiz.veritabani_sorgusu,
                       "guncelleme_istegi": r.analiz.guncelleme_istegi},
            "envanter": envanter_dict,
            "veritabani": r.veritabani,
        }
