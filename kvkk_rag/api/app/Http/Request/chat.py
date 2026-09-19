from __future__ import annotations

from pydantic import BaseModel


class AskRequest(BaseModel):
    query: str
    provider: str | None = None
    limit: int | None = None      # None -> hybrid.PARENT_LIMIT
    sources_only: bool = False


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    provider: str | None = None
    limit: int | None = None
