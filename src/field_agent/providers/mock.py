"""Scripted provider for tests: returns queued outputs (or raises queued exceptions) in order."""

from __future__ import annotations

from collections.abc import Iterable

from .base import ProviderResult


class MockProvider:
    name = "mock"
    model = "mock-1"
    supports_repair = True

    def __init__(self, outputs: Iterable[str | Exception]):
        self._outputs = list(outputs)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> ProviderResult:
        self.calls.append((system, user))
        if not self._outputs:
            raise AssertionError("MockProvider ran out of scripted outputs")
        nxt = self._outputs.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return ProviderResult(text=nxt, model=self.model)
