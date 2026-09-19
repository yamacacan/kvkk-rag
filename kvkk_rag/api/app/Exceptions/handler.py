"""Dogrulama hatalarini Turkce ve Laravel bicimine yakin dondurur:
{"detail": "<ilk mesaj>", "errors": {"alan": ["mesaj", ...]}}
`detail` mevcut istemcilerle uyum icin korunur; Pydantic'in Ingilizce mesajlari
tur koduna gore cevrilir (lang/tr/validation.php karsiligi)."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

MESAJLAR: dict[str, str] = {
    "missing": "Bu alan zorunludur.",
    "string_too_short": "En az {min_length} karakter olmalıdır.",
    "string_too_long": "En fazla {max_length} karakter olabilir.",
    "string_type": "Metin olmalıdır.",
    "int_parsing": "Tam sayı olmalıdır.",
    "int_type": "Tam sayı olmalıdır.",
    "bool_parsing": "Evet/hayır değeri olmalıdır.",
    "bool_type": "Evet/hayır değeri olmalıdır.",
    "list_type": "Liste olmalıdır.",
    "dict_type": "Nesne olmalıdır.",
    "json_invalid": "Gövde geçerli JSON değil.",
    "model_attributes_type": "Gövde geçerli bir nesne değil.",
    "greater_than_equal": "En az {ge} olmalıdır.",
    "less_than_equal": "En fazla {le} olabilir.",
    "enum": "Geçersiz seçenek.",
    "literal_error": "Geçersiz seçenek.",
}

ALAN_ADLARI: dict[str, str] = {
    "email": "E-posta", "password": "Şifre", "password_confirmation": "Şifre tekrarı",
    "token": "Jeton", "refresh_token": "Yenileme jetonu", "name": "Ad", "roles": "Roller",
    "query": "Sorgu", "messages": "Mesajlar", "kurum": "Kurum", "sablon": "Şablon",
}


def _mesaj(err: dict[str, Any]) -> str:
    tur = err.get("type", "")
    ctx = err.get("ctx") or {}
    if tur in ("value_error", "assertion_error"):
        # field_validator / model_validator icindeki ValueError metni zaten Turkce
        ham = str(ctx.get("error") or err.get("msg", ""))
        return ham.replace("Value error, ", "").replace("Assertion failed, ", "")
    kalip = MESAJLAR.get(tur)
    if kalip:
        try:
            return kalip.format(**ctx)
        except (KeyError, IndexError):
            return kalip
    return "Geçersiz değer."


def _alan(err: dict[str, Any]) -> str:
    loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path", "header")]
    return ".".join(loc) or "_"


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors: dict[str, list[str]] = {}
    for err in exc.errors():
        errors.setdefault(_alan(err), []).append(_mesaj(err))
    ilk_alan, ilk_mesajlar = next(iter(errors.items()), ("_", ["Doğrulama hatası."]))
    etiket = ALAN_ADLARI.get(ilk_alan.split(".")[-1], ilk_alan)
    detail = ilk_mesajlar[0] if ilk_alan == "_" else f"{etiket}: {ilk_mesajlar[0]}"
    return JSONResponse(status_code=422, content={"detail": detail, "errors": errors})


def register(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
