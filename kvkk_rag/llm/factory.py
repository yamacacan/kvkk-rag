# Saglayici secimi ve uc adaptor: Gemini API, Anthropic API, lokal Ollama.
from __future__ import annotations

import os

from ..config import settings
from .base import LLM, Message, split_system


class GeminiLLM:
    name = "gemini"

    def __init__(self, model: str | None = None):
        import google.generativeai as genai
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY tanimli degil (.env)")
        genai.configure(api_key=key)
        self._genai = genai
        self.model = model or settings.GEMINI_MODEL

    def complete(self, messages: list[Message], temperature: float = 0.2,
                 max_tokens: int = 2048) -> str:
        system, rest = split_system(messages)
        model = self._genai.GenerativeModel(self.model, system_instruction=system or None)
        # Cok turlu sohbette roller korunur; Gemini asistan rolune "model" der.
        contents = [{"role": "model" if m["role"] == "assistant" else "user",
                     "parts": [m["content"]]} for m in rest]
        resp = model.generate_content(
            contents,
            generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
        )
        return resp.text


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, model: str | None = None):
        import anthropic
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY tanimli degil (.env)")
        self._client = anthropic.Anthropic(api_key=key)
        self.model = model or settings.ANTHROPIC_MODEL

    def complete(self, messages: list[Message], temperature: float = 0.2,
                 max_tokens: int = 2048) -> str:
        system, rest = split_system(messages)
        resp = self._client.messages.create(
            model=self.model, max_tokens=max_tokens, temperature=temperature,
            system=system or None,
            messages=[{"role": m["role"], "content": m["content"]} for m in rest],
        )
        return "".join(b.text for b in resp.content if b.type == "text")


class OllamaLLM:
    name = "ollama"

    def __init__(self, model: str | None = None):
        import ollama
        self._client = ollama.Client(host=settings.OLLAMA_HOST)
        self.model = model or settings.OLLAMA_MODEL

    def complete(self, messages: list[Message], temperature: float = 0.2,
                 max_tokens: int = 2048) -> str:
        resp = self._client.chat(
            model=self.model, messages=messages,
            options={"temperature": temperature, "num_predict": max_tokens},
        )
        return resp["message"]["content"]


PROVIDERS = {"gemini": GeminiLLM, "anthropic": AnthropicLLM, "ollama": OllamaLLM}


def get_llm(provider: str | None = None, model: str | None = None) -> LLM:
    provider = (provider or settings.LLM_PROVIDER).lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Bilinmeyen saglayici: {provider}. Secenekler: {list(PROVIDERS)}")
    return PROVIDERS[provider](model)
