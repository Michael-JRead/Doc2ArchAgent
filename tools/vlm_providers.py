#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""VLM (Vision Language Model) provider abstraction for Doc2ArchAgent.

Swappable backends for image/document understanding: OpenAI, Anthropic,
Google Gemini, Ollama (local), or a stub for testing.

Usage:
    from tools.vlm_providers import create_provider

    # Auto-detect from environment
    provider = create_provider()

    # Or specify explicitly
    provider = create_provider("openai", model="gpt-4o")
    provider = create_provider("ollama", model="llava:13b", base_url="http://localhost:11434")

    result = provider.analyze_image(image_bytes, prompt="Describe this architecture diagram")
"""

from __future__ import annotations

import base64
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path


class VLMResponse:
    """Standardized response from any VLM provider."""

    def __init__(self, text: str, model: str, provider: str,
                 usage: dict | None = None, raw: dict | None = None):
        self.text = text
        self.model = model
        self.provider = provider
        self.usage = usage or {}
        self.raw = raw or {}


class VLMProvider(ABC):
    """Abstract base class for vision language model providers."""

    @abstractmethod
    def analyze_image(
        self,
        image: bytes | str | Path,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> VLMResponse:
        """Analyze an image with a text prompt.

        Args:
            image: Image as bytes, base64 string, file path, or URL.
            prompt: The analysis prompt.
            system_prompt: Optional system-level instruction.
            max_tokens: Maximum response tokens.
            temperature: Sampling temperature (0.0 = deterministic).

        Returns:
            VLMResponse with the model's text output.
        """

    @abstractmethod
    def analyze_document_page(
        self,
        page_image: bytes | str | Path,
        *,
        extraction_schema: dict | None = None,
        max_tokens: int = 4096,
    ) -> VLMResponse:
        """Analyze a document page image for architecture extraction.

        Specialized method that uses architecture-aware prompts.

        Args:
            page_image: Rendered page as image bytes or path.
            extraction_schema: Optional JSON schema to guide structured output.
            max_tokens: Maximum response tokens.

        Returns:
            VLMResponse with structured extraction results.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""

    def _load_image(self, image: bytes | str | Path) -> tuple[str, str]:
        """Convert image input to (base64_data, media_type) tuple."""
        if isinstance(image, bytes):
            data = base64.b64encode(image).decode("utf-8")
            return data, "image/png"

        if isinstance(image, Path):
            image = str(image)

        if isinstance(image, str):
            if image.startswith(("http://", "https://")):
                return image, "url"
            # File path
            path = Path(image)
            if path.exists():
                data = base64.b64encode(path.read_bytes()).decode("utf-8")
                suffix = path.suffix.lower()
                media_map = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                    ".bmp": "image/bmp",
                    ".tiff": "image/tiff",
                    ".tif": "image/tiff",
                }
                return data, media_map.get(suffix, "image/png")
            # Assume it's already base64
            return image, "image/png"

        raise ValueError(f"Unsupported image type: {type(image)}")


_ARCH_EXTRACTION_PROMPT = """Analyze this architecture document page and extract structured information.

Identify and extract:
- System/component names and their types (service, database, queue, cache, etc.)
- Technology stack (languages, frameworks, infrastructure)
- Communication protocols and ports
- Network zones and trust boundaries
- Security mechanisms (TLS, authentication, authorization)
- Data flows and relationships between components

Return the results as JSON with the following structure:
{
  "components": [{"name": "...", "type": "...", "technology": "...", "description": "..."}],
  "relationships": [{"source": "...", "target": "...", "protocol": "...", "description": "..."}],
  "tables": [{"caption": "...", "headers": [...], "rows": [[...]]}],
  "diagrams": [{"type": "...", "description": "...", "components_shown": [...]}],
  "security_notes": ["..."],
  "raw_text": "..."
}"""


class OpenAIProvider(VLMProvider):
    """OpenAI GPT-4o / GPT-4 Vision provider."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o",
                 base_url: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = base_url

    @property
    def name(self) -> str:
        return "openai"

    def _get_client(self):
        try:
            import openai
        except ImportError:
            raise ImportError("pip install openai  — required for OpenAI VLM provider")
        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return openai.OpenAI(**kwargs)

    def analyze_image(self, image, prompt, *, system_prompt=None,
                      max_tokens=4096, temperature=0.0):
        client = self._get_client()
        b64, media_type = self._load_image(image)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if media_type == "url":
            image_content = {"type": "image_url", "image_url": {"url": b64}}
        else:
            image_content = {
                "type": "image_url",
                "image_url": {"url": f"data:{media_type};base64,{b64}"},
            }

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                image_content,
            ],
        })

        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return VLMResponse(
            text=resp.choices[0].message.content or "",
            model=self.model,
            provider=self.name,
            usage={"input_tokens": resp.usage.prompt_tokens,
                   "output_tokens": resp.usage.completion_tokens} if resp.usage else {},
            raw=resp.model_dump() if hasattr(resp, "model_dump") else {},
        )

    def analyze_document_page(self, page_image, *, extraction_schema=None, max_tokens=4096):
        prompt = _ARCH_EXTRACTION_PROMPT
        if extraction_schema:
            prompt += f"\n\nExpected output schema:\n{json.dumps(extraction_schema, indent=2)}"
        return self.analyze_image(
            page_image, prompt,
            system_prompt="You are an expert software architect analyzing documentation.",
            max_tokens=max_tokens,
        )


class AnthropicProvider(VLMProvider):
    """Anthropic Claude Vision provider."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model

    @property
    def name(self) -> str:
        return "anthropic"

    def _get_client(self):
        try:
            import anthropic
        except ImportError:
            raise ImportError("pip install anthropic  — required for Anthropic VLM provider")
        return anthropic.Anthropic(api_key=self.api_key)

    def analyze_image(self, image, prompt, *, system_prompt=None,
                      max_tokens=4096, temperature=0.0):
        client = self._get_client()
        b64, media_type = self._load_image(image)

        if media_type == "url":
            image_block = {
                "type": "image",
                "source": {"type": "url", "url": b64},
            }
        else:
            image_block = {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64},
            }

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{
                "role": "user",
                "content": [image_block, {"type": "text", "text": prompt}],
            }],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        resp = client.messages.create(**kwargs)

        return VLMResponse(
            text=resp.content[0].text if resp.content else "",
            model=self.model,
            provider=self.name,
            usage={"input_tokens": resp.usage.input_tokens,
                   "output_tokens": resp.usage.output_tokens} if resp.usage else {},
            raw=resp.model_dump() if hasattr(resp, "model_dump") else {},
        )

    def analyze_document_page(self, page_image, *, extraction_schema=None, max_tokens=4096):
        prompt = _ARCH_EXTRACTION_PROMPT
        if extraction_schema:
            prompt += f"\n\nExpected output schema:\n{json.dumps(extraction_schema, indent=2)}"
        return self.analyze_image(
            page_image, prompt,
            system_prompt="You are an expert software architect analyzing documentation.",
            max_tokens=max_tokens,
        )


class OllamaProvider(VLMProvider):
    """Ollama local VLM provider (privacy-first, no cloud API calls)."""

    def __init__(self, model: str = "llava:13b",
                 base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "ollama"

    def analyze_image(self, image, prompt, *, system_prompt=None,
                      max_tokens=4096, temperature=0.0):
        import urllib.request

        b64, media_type = self._load_image(image)
        if media_type == "url":
            raise ValueError("Ollama provider requires local images, not URLs")

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = json.dumps({
            "model": self.model,
            "prompt": full_prompt,
            "images": [b64],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }).encode()

        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

        return VLMResponse(
            text=data.get("response", ""),
            model=self.model,
            provider=self.name,
            usage={"eval_count": data.get("eval_count", 0),
                   "prompt_eval_count": data.get("prompt_eval_count", 0)},
            raw=data,
        )

    def analyze_document_page(self, page_image, *, extraction_schema=None, max_tokens=4096):
        prompt = _ARCH_EXTRACTION_PROMPT
        if extraction_schema:
            prompt += f"\n\nExpected output schema:\n{json.dumps(extraction_schema, indent=2)}"
        return self.analyze_image(
            page_image, prompt,
            system_prompt="You are an expert software architect analyzing documentation.",
            max_tokens=max_tokens,
        )


class StubProvider(VLMProvider):
    """Stub provider for testing — returns empty structured responses."""

    def __init__(self, **kwargs):
        self.responses: list[str] = kwargs.get("responses", [])
        self._call_count = 0

    @property
    def name(self) -> str:
        return "stub"

    def analyze_image(self, image, prompt, *, system_prompt=None,
                      max_tokens=4096, temperature=0.0):
        text = ""
        if self._call_count < len(self.responses):
            text = self.responses[self._call_count]
        self._call_count += 1

        return VLMResponse(text=text, model="stub", provider="stub")

    def analyze_document_page(self, page_image, *, extraction_schema=None, max_tokens=4096):
        return self.analyze_image(page_image, _ARCH_EXTRACTION_PROMPT)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
    "stub": StubProvider,
}


def create_provider(
    provider_name: str | None = None,
    **kwargs,
) -> VLMProvider:
    """Create a VLM provider instance.

    Auto-detection order (when provider_name is None):
    1. D2A_VLM_PROVIDER env var
    2. ANTHROPIC_API_KEY set → anthropic
    3. OPENAI_API_KEY set → openai
    4. Ollama reachable at localhost:11434 → ollama
    5. StubProvider (no-op)

    Args:
        provider_name: Explicit provider name (openai/anthropic/ollama/stub).
        **kwargs: Passed to provider constructor (model, api_key, base_url, etc.)

    Returns:
        Configured VLMProvider instance.
    """
    if provider_name is None:
        provider_name = os.environ.get("D2A_VLM_PROVIDER", "").lower()

    if not provider_name:
        # Auto-detect
        if os.environ.get("ANTHROPIC_API_KEY"):
            provider_name = "anthropic"
        elif os.environ.get("OPENAI_API_KEY"):
            provider_name = "openai"
        else:
            # Check if Ollama is running
            try:
                import urllib.request
                import urllib.error
                req = urllib.request.Request(
                    kwargs.get("base_url", "http://localhost:11434") + "/api/tags",
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=2):
                    provider_name = "ollama"
            except (urllib.error.URLError, OSError, ValueError):
                provider_name = "stub"

    cls = _PROVIDERS.get(provider_name)
    if cls is None:
        raise ValueError(
            f"Unknown VLM provider: {provider_name!r}. "
            f"Available: {', '.join(_PROVIDERS.keys())}"
        )

    return cls(**kwargs)


def list_providers() -> list[str]:
    """Return available provider names."""
    return list(_PROVIDERS.keys())
