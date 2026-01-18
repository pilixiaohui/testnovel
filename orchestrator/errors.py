from __future__ import annotations


class OrchestratorError(RuntimeError):
    """Base error for orchestrator failures (fail fast, no silent fallback)."""


class TemporaryError(OrchestratorError):
    """Transient error: retrying the same stage may succeed."""


class PermanentError(OrchestratorError):
    """Non-recoverable error: abort immediately."""
