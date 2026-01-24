from __future__ import annotations

from typing import Any


def rollback_migration(target: Any, node_ids: list[str], edge_ids: list[str]) -> None:
    target.delete_edges(edge_ids)
    target.delete_nodes(node_ids)
