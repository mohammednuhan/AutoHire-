from __future__ import annotations

import asyncio
import json
import logging
import os
import time

import google.generativeai as genai
import httpx
from anthropic import AsyncAnthropic

logger = logging.getLogger("autohire.llm")


class LLMFailure(Exception):
    pass


class LLMRouter:
    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.quality_mode = os.getenv("LLM_QUALITY_MODE", "balanced").lower()
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "deepseek-r1:14b")

    def _select_model(self, task_type: str) -> tuple[str, bool]:
        if self.provider == "ollama":
            return f"ollama/{self.ollama_model}", False

        tier = "scan" if task_type in {"scan", "extract"} else task_type
        routes = {
            "scan": {
                "fast": ("gemini-flash", False),
                "balanced": ("gemini-flash", False),
                "maximum": ("claude-haiku-4-5", False),
            },
            "reason": {
                "fast": ("gemini-flash", False),
                "balanced": ("claude-haiku-4-5", False),
                "maximum": ("claude-sonnet-4-6", False),
            },
            "write": {
                "fast": ("gemini-flash", False),
                "balanced": ("claude-sonnet-4-6", False),
                "maximum": ("claude-sonnet-4-6", True),
            },
        }
        return routes.get(tier, routes["scan"]).get(self.quality_mode, routes["scan"]["balanced"])

    async def call(
        self,
        task_type: str,
        prompt: str,
        system: str = "",
        response_format: str = "text",
        trace_id: str | None = None,
    ) -> str:
        started = time.perf_counter()
        model, extended_thinking = self._select_model(task_type)
        try:
            if model.startswith("ollama/"):
                result = await self._call_ollama(model.removeprefix("ollama/"), system, prompt, response_format)
            elif model.startswith("claude-"):
                result = await self._call_claude(model, system, prompt, response_format, extended_thinking)
            else:
                result = await self._call_gemini(model, system, prompt, response_format)
            latency_ms = round((time.perf_counter() - started) * 1000)
            logger.info(
                "llm_call",
                extra={
                    "model": model,
                    "tokens": None,
                    "task_type": task_type,
                    "trace_id": trace_id,
                    "latency_ms": latency_ms,
                },
            )
            return result
        except Exception as exc:
            logger.exception(
                "llm_call_failed",
                extra={"model": model, "task_type": task_type, "trace_id": trace_id},
            )
            raise LLMFailure(str(exc)) from exc

    async def call_with_retry(
        self,
        task_type: str,
        prompt: str,
        system: str = "",
        response_format: str = "text",
        max_retries: int = 3,
        trace_id: str | None = None,
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                response = await self.call(task_type, prompt, system, response_format, trace_id)
                if response_format == "json":
                    json.loads(response)
                return response
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "llm_retry",
                    extra={"attempt": attempt, "task_type": task_type, "trace_id": trace_id},
                )
        raise LLMFailure(f"LLM response failed after {max_retries} attempts: {last_error}")

    async def _call_gemini(self, model: str, system: str, prompt: str, response_format: str) -> str:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise LLMFailure("GEMINI_API_KEY is not configured")
        genai.configure(api_key=api_key)
        generation_config = {"response_mime_type": "application/json"} if response_format == "json" else None
        gemini_model = genai.GenerativeModel(model_name="gemini-2.0-flash", system_instruction=system)
        response = await asyncio.to_thread(
            gemini_model.generate_content,
            prompt,
            generation_config=generation_config,
        )
        return response.text

    async def _call_claude(self, model: str, system: str, prompt: str, response_format: str, extended_thinking: bool) -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMFailure("ANTHROPIC_API_KEY is not configured")
        client = AsyncAnthropic(api_key=api_key)
        kwargs = {
            "model": model,
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        if extended_thinking:
            kwargs["extra_body"] = {"thinking": {"type": "enabled", "budget_tokens": 1024}}
        message = await client.messages.create(**kwargs)
        return "".join(block.text for block in message.content if getattr(block, "type", None) == "text")

    async def _call_ollama(self, model: str, system: str, prompt: str, response_format: str) -> str:
        payload = {
            "model": model,
            "prompt": f"{system}\n\n{prompt}",
            "stream": False,
        }
        if response_format == "json":
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(f"{self.ollama_base_url}/api/generate", json=payload)
            response.raise_for_status()
            return response.json()["response"]
