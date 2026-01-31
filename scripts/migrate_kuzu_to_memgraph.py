"""Kuzu to Memgraph migration utilities."""

from __future__ import annotations


class KuzuToMemgraphMigrator:
    """Export, transform, import, and validate migration payloads."""

    def __init__(self, source=None, target=None) -> None:
        self._source = source
        self._target = target

    def export(self) -> dict[str, list[dict]]:
        source = self._require_source()
        nodes = [dict(node) for node in source.list_nodes()]
        edges = [dict(edge) for edge in source.list_edges()]
        return {"nodes": nodes, "edges": edges}

    def transform(self, exported: dict[str, list[dict]]) -> dict[str, list[dict]]:
        nodes = [self._normalize_node(node) for node in exported["nodes"]]
        edges = [self._normalize_edge(edge) for edge in exported["edges"]]
        return {"nodes": nodes, "edges": edges}

    def import_data(self, payload: dict[str, list[dict]]) -> dict[str, list[str]]:
        target = self._require_target()
        nodes = payload["nodes"]
        edges = payload["edges"]
        node_ids = [node["id"] for node in nodes]
        node_id_set = set(node_ids)
        for edge in edges:
            if edge["from_id"] not in node_id_set or edge["to_id"] not in node_id_set:
                raise ValueError("edge references missing node")
        target.insert_nodes(nodes)
        target.insert_edges(edges)
        return {
            "node_ids": node_ids,
            "edge_ids": [edge["id"] for edge in edges],
        }

    def validate_integrity(
        self,
        exported: dict[str, list[dict]],
        snapshot: dict[str, list[dict]],
        *,
        sample_size: int,
    ) -> None:
        exported_nodes = exported["nodes"]
        exported_edges = exported["edges"]
        snapshot_nodes = snapshot["nodes"]
        snapshot_edges = snapshot["edges"]
        assert len(exported_nodes) == len(snapshot_nodes)
        assert len(exported_edges) == len(snapshot_edges)

        node_index = {node["id"]: node for node in snapshot_nodes}
        edge_index = {edge["id"]: edge for edge in snapshot_edges}

        node_sample = exported_nodes[-sample_size:] if sample_size else []
        for node in node_sample:
            stored = node_index[node["id"]]
            assert stored["label"] == node["label"]
            assert stored["properties"] == node["properties"]

        edge_sample = exported_edges[-min(sample_size, len(exported_edges)) :] if sample_size else []
        for edge in edge_sample:
            stored = edge_index[edge["id"]]
            assert stored["type"] == edge["type"]
            assert stored["from_id"] == edge["from_id"]
            assert stored["to_id"] == edge["to_id"]
            assert stored["properties"] == edge["properties"]

    def _require_source(self):
        if self._source is None:
            raise ValueError("source is required")
        return self._source

    def _require_target(self):
        if self._target is None:
            raise ValueError("target is required")
        return self._target

    @staticmethod
    def _normalize_node(node: dict) -> dict:
        return {
            "id": node["id"],
            "label": node["label"],
            "properties": dict(node["properties"]),
        }

    @staticmethod
    def _normalize_edge(edge: dict) -> dict:
        return {
            "id": edge["id"],
            "type": edge["type"],
            "from_id": edge["from_id"],
            "to_id": edge["to_id"],
            "properties": dict(edge["properties"]),
        }
