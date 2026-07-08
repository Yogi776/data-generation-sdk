"""LLM provider abstraction. Rule zero: no module imports a provider SDK directly.

MiniMax (default), OpenAI, Gemini share the OpenAI-compatible chat protocol —
one implementation, different base_url/model. Anthropic uses its native API via
httpx. `local` is a deterministic offline stub for tests and demos.
Keys come from the environment (api_key_env indirection) — never from config
values or code.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from ai_data_platform.config import ModelProviderConfig
from ai_data_platform.core.exceptions import AIProviderError
from ai_data_platform.core.logging import get_logger

log = get_logger("adp.llm")


class LLMProvider(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class OpenAICompatibleProvider:
    """Chat-completions protocol: MiniMax, OpenAI, Gemini (OpenAI endpoint), vLLM…"""

    def __init__(self, cfg: ModelProviderConfig) -> None:
        self.cfg = cfg
        key = cfg.api_key()
        if not key:
            raise AIProviderError(
                f"No API key found in ${cfg.api_key_env}.",
                hint=f"export {cfg.api_key_env}=... or add it to your .env file.",
            )
        self._key = key

    def complete(self, system: str, user: str) -> str:
        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        try:
            resp = httpx.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {self._key}"},
                timeout=self.cfg.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise KeyError("empty content")
            usage = data.get("usage", {})
            log.info(
                "llm call ok model=%s tokens_in=%s tokens_out=%s",
                self.cfg.model,
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
            )
            return content
        except httpx.HTTPStatusError as e:
            raise AIProviderError(
                f"Provider returned HTTP {e.response.status_code}.",
                hint="Check model name, base_url, and API key validity.",
            ) from e
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as e:
            raise AIProviderError(f"Provider call failed: {e}") from e


class AnthropicProvider:
    def __init__(self, cfg: ModelProviderConfig) -> None:
        self.cfg = cfg
        key = cfg.api_key()
        if not key:
            raise AIProviderError(
                f"No API key found in ${cfg.api_key_env}.",
                hint=f"export {cfg.api_key_env}=...",
            )
        self._key = key

    def complete(self, system: str, user: str) -> str:
        url = (self.cfg.base_url.rstrip("/") or "https://api.anthropic.com/v1") + "/messages"
        try:
            resp = httpx.post(
                url,
                json={
                    "model": self.cfg.model,
                    "max_tokens": 2048,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
                headers={"x-api-key": self._key, "anthropic-version": "2023-06-01"},
                timeout=self.cfg.timeout_seconds,
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
        except (httpx.HTTPError, KeyError, IndexError) as e:
            raise AIProviderError(f"Anthropic call failed: {e}") from e


class LocalEchoProvider:
    """Deterministic offline stub: emits a trivially valid response so the full
    pipeline is testable without network or keys."""

    def __init__(self, cfg: ModelProviderConfig) -> None:
        self.cfg = cfg

    def complete(self, system: str, user: str) -> str:
        # For NL->SQL prompts, return a safe minimal SELECT over the first table
        # mentioned in the context, so downstream guards/parsers are exercised.
        for line in user.splitlines():
            if line.lower().startswith("table "):
                table = line.split()[1].strip(":")
                return json.dumps(
                    {
                        "sql": f'SELECT * FROM "{table}" LIMIT 10',
                        "explanation": "Offline stub: first table in context, first 10 rows.",
                        "confidence": 0.1,
                        "tables_used": [table],
                    }
                )
        return json.dumps(
            {
                "sql": "",
                "explanation": "Offline stub: no table context found.",
                "confidence": 0.0,
                "tables_used": [],
            }
        )


def get_provider(cfg: ModelProviderConfig) -> LLMProvider:
    if cfg.provider in ("minimax", "openai", "gemini"):
        return OpenAICompatibleProvider(cfg)
    if cfg.provider == "anthropic":
        return AnthropicProvider(cfg)
    if cfg.provider == "local":
        return LocalEchoProvider(cfg)
    raise AIProviderError(
        f"Unknown provider {cfg.provider!r}.",
        hint="Supported: minimax, openai, anthropic, gemini, local.",
    )
