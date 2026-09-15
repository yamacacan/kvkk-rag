# Takilabilir LLM adaptoru. Saglayici degisse de cagri yuzeyi ayni kalir.
from __future__ import annotations

from typing import Protocol, runtime_checkable

Message = dict[str, str]  # {"role": "system"|"user"|"assistant", "content": ...}


@runtime_checkable
class LLM(Protocol):
    name: str

    def complete(self, messages: list[Message], temperature: float = 0.2,
                 max_tokens: int = 2048) -> str:
        ...


def split_system(messages: list[Message]) -> tuple[str, list[Message]]:
    # Gemini/Ollama system mesajini ayri alanda bekler
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    rest = [m for m in messages if m["role"] != "system"]
    return system, rest
