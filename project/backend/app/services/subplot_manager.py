"""Subplot activation and resolution workflow."""

from __future__ import annotations


class SubplotManager:
    """Manage subplot lifecycle transitions."""

    def __init__(self, storage) -> None:
        self._storage = storage

    def activate_subplot(self, subplot):
        if subplot.status != "dormant":
            raise ValueError("subplot must be dormant to activate")
        subplot.status = "active"
        return self._storage.update_subplot(subplot)

    def resolve_subplot(self, subplot):
        if subplot.status != "active":
            raise ValueError("subplot must be active to resolve")
        subplot.status = "resolved"
        return self._storage.update_subplot(subplot)
