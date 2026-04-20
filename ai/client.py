from __future__ import annotations

import logging
import os
from typing import List, Optional

from huggingface_hub import InferenceClient

logger = logging.getLogger("pawpal.ai.client")

DEFAULT_MODEL = os.environ.get("PAWPAL_MODEL", "google/gemma-4-31B-it:novita")


class ArchitectLLM:
    """Thin wrapper around ``huggingface_hub.InferenceClient.chat_completion``.

    Reads ``HF_TOKEN`` from the environment by default; model defaults to the
    Gemma variant routed via the Novita provider (``:novita`` suffix).
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        token: Optional[str] = None,
    ) -> None:
        self.model = model
        resolved_token = token or os.environ.get("HF_TOKEN")
        if not resolved_token:
            raise RuntimeError(
                "HF_TOKEN is not set. Create a token at "
                "https://huggingface.co/settings/tokens and export HF_TOKEN "
                "before running the Care Plan Architect."
            )
        self._client = InferenceClient(token=resolved_token)

    def complete(
        self,
        messages: List[dict],
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> str:
        logger.info(
            "HF chat_completion model=%s max_tokens=%d temp=%.2f turns=%d",
            self.model,
            max_tokens,
            temperature,
            len(messages),
        )
        resp = self._client.chat_completion(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""
