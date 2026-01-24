from __future__ import annotations

import random
from typing import Any


class KuzuToMemgraphMigrator:
    def __init__(self, source: Any, target: Any) -> None:
        self._source = source
        self._target = target

    def export(self) -> dict[str, list[dict]]:
        nodes = self._source.list_nodes()
        edges = self._source.list_edges()
        return {
            "nodes": [self._clone_item(node) for node in nodes],
            "edges": [self._clone_item(edge) for edge in edges],
        }

    def transform(self, exported: dict[str, list[dict]]) -> dict[str, list[dict]]:
        return {
            "nodes": [self._clone_item(node) for node in exported["nodes"]],
            "edges": [self._clone_item(edge) for edge in exported["edges"]],
        }

    def import_data(self, transformed: dict[str, list[dict]]) -> dict[str, list[str]]:
        nodes = transformed["nodes"]
        edges = transformed["edges"]
        self._target.insert_nodes(nodes)
        self._target.insert_edges(edges)
        return {
            "node_ids": [node["id"] for node in nodes],
            "edge_ids": [edge["id"] for edge in edges],
        }

    def validate_integrity(
        self,
        source_data: dict[str, list[dict]],
        target_snapshot: dict[str, list[dict]],
        sample_size: int,
    ) -> None:
        source_nodes = source_data["nodes"]
        source_edges = source_data["edges"]
        target_nodes = target_snapshot["nodes"]
        target_edges = target_snapshot["edges"]

        if len(source_nodes) != len(target_nodes):
            raise AssertionError("node count mismatch")
        if len(source_edges) != len(target_edges):
            raise AssertionError("edge count mismatch")

        source_node_index = {node["id"]: node for node in source_nodes}
        target_node_index = {node["id"]: node for node in target_nodes}
        source_edge_index = {edge["id"]: edge for edge in source_edges}
        target_edge_index = {edge["id"]: edge for edge in target_edges}

        if source_node_index.keys() != target_node_index.keys():
            raise AssertionError("node ids mismatch")
        if source_edge_index.keys() != target_edge_index.keys():
            raise AssertionError("edge ids mismatch")

        node_ids = sorted(source_node_index)
        edge_ids = sorted(source_edge_index)
        node_sample_size = min(sample_size, len(node_ids))
        edge_sample_size = min(sample_size, len(edge_ids))
        node_sample = random.Random(node_sample_size).sample(
            node_ids,
            node_sample_size,
        )
        edge_sample = random.Random(edge_sample_size).sample(
            edge_ids,
            edge_sample_size,
        )

        for node_id in node_sample:
            source_node = source_node_index[node_id]
            target_node = target_node_index[node_id]
            if source_node["label"] != target_node["label"]:
                raise AssertionError(f"node label mismatch for {node_id}")
            if source_node["properties"] != target_node["properties"]:
                raise AssertionError(f"node properties mismatch for {node_id}")

        for edge_id in edge_sample:
            source_edge = source_edge_index[edge_id]
            target_edge = target_edge_index[edge_id]
            if source_edge["type"] != target_edge["type"]:
                raise AssertionError(f"edge type mismatch for {edge_id}")
            if source_edge["from_id"] != target_edge["from_id"]:
                raise AssertionError(f"edge from_id mismatch for {edge_id}")
            if source_edge["to_id"] != target_edge["to_id"]:
                raise AssertionError(f"edge to_id mismatch for {edge_id}")
            if source_edge["properties"] != target_edge["properties"]:
                raise AssertionError(f"edge properties mismatch for {edge_id}")

    @staticmethod
    def _clone_item(item: dict) -> dict:
        cloned = dict(item)
        cloned["properties"] = dict(item["properties"])
        return cloned
