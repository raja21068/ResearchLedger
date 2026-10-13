"""Subscription-backed CLI provider; imported from the ResearchLedger host."""
from __future__ import annotations
import asyncio
from .base import LLMProvider, LLMRequest


class SubscriptionCLIProvider(LLMProvider):
    def __init__(self, provider: str, *, default_model: str | None = None):
        if provider not in {"claude", "codex"}:
            raise ValueError("provider must be claude or codex")
        self.provider=provider
        self.default_model=default_model

    async def complete(self, request: LLMRequest):
        from factory.integrations.subscription_bridge import ask_json
        return await asyncio.to_thread(ask_json,self.provider,
             system=request.system,user=request.user,schema=request.schema,
             model=request.model if request.model not in (None,"","host-default") else self.default_model)
