"""Rollback migration changes."""

from __future__ import annotations


def rollback_migration(*, target, node_ids: list[str], edge_ids: list[str]) -> None:
    target.delete_edges(edge_ids)
    target.delete_nodes(node_ids)
