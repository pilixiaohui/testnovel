from __future__ import annotations


class OrchestratorError(RuntimeError):
    """Base error for orchestrator failures (fail fast, no silent fallback)."""


class TemporaryError(OrchestratorError):
    """Transient error: retrying the same stage may succeed."""

    def __init__(self, message: str, session_id: str | None = None):
        super().__init__(message)
        self.session_id = session_id


class PermanentError(OrchestratorError):
    """Non-recoverable error: abort immediately."""
