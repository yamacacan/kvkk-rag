from __future__ import annotations

from typing import Any, Iterable


class Resource:
    def __init__(self, item: Any, **context: Any) -> None:
        self.item = item
        self.context = context

    def to_array(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def make(cls, item: Any, **context: Any) -> dict[str, Any]:
        return cls(item, **context).to_array()

    @classmethod
    def collection(cls, items: Iterable[Any], **context: Any) -> list[dict[str, Any]]:
        return [cls(i, **context).to_array() for i in items]
