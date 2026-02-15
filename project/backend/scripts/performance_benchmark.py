#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from uuid import uuid4

from app.config import require_memgraph_host, require_memgraph_port
from app.storage.memgraph_storage import MemgraphStorage
from app.storage.schema import Branch, BranchHead, Commit, Root


@dataclass
class Metrics:
    count: int
    duration_s: float
    qps: float
    avg_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if pct <= 0:
        return min(values)
    if pct >= 1:
        return max(values)
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    low = math.floor(k)
    high = math.ceil(k)
    if low == high:
        return ordered[int(k)]
    weight = k - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _format_metrics(latencies_ms: list[float], duration_s: float) -> Metrics:
    if not latencies_ms:
        raise ValueError("no latency data")
    count = len(latencies_ms)
    qps = count / duration_s if duration_s > 0 else 0.0
    return Metrics(
        count=count,
        duration_s=duration_s,
        qps=qps,
        avg_ms=statistics.mean(latencies_ms),
        p50_ms=_percentile(latencies_ms, 0.50),
        p95_ms=_percentile(latencies_ms, 0.95),
        p99_ms=_percentile(latencies_ms, 0.99),
    )


def _create_storage() -> MemgraphStorage:
    host = require_memgraph_host()
    port = require_memgraph_port()
    return MemgraphStorage(host=host, port=port)


def _seed_graph(
    storage: MemgraphStorage,
    *,
    root_id: str,
    branch_id: str,
    entity_count: int,
    scene_count: int,
    relation_count: int,
) -> tuple[list[str], list[str]]:
    if entity_count <= 0:
        raise ValueError("entity_count must be > 0")
    if scene_count <= 0:
        raise ValueError("scene_count must be > 0")
    if relation_count > 0 and entity_count < 2:
        raise ValueError("relation_count requires entity_count >= 2")
    if relation_count > entity_count:
        raise ValueError("relation_count must be <= entity_count")

    root = Root(
        id=root_id,
        logline="benchmark",
        theme="benchmark",
        ending="benchmark",
        created_at=_utc_now(),
    )
    storage.create_root(root)

    branch = Branch(
        id=f"{root_id}:{branch_id}",
        root_id=root_id,
        branch_id=branch_id,
        parent_branch_id=None,
        fork_scene_origin_id=None,
        fork_commit_id=None,
    )
    storage.create_branch(branch)

    commit_id = f"{root_id}:{branch_id}:{uuid4()}"
    commit = Commit(
        id=commit_id,
        parent_id=None,
        message="benchmark seed",
        created_at=_utc_now(),
        root_id=root_id,
        branch_id=branch_id,
    )
    storage.create_commit(commit)

    branch_head = BranchHead(
        id=f"{root_id}:{branch_id}:head",
        root_id=root_id,
        branch_id=branch_id,
        head_commit_id=commit_id,
        version=1,
    )
    storage.create_branch_head(branch_head)

    entity_ids: list[str] = []
    for idx in range(entity_count):
        entity_id = storage.create_entity(
            root_id=root_id,
            branch_id=branch_id,
            name=f"Entity {idx}",
            entity_type="Character",
            tags=[],
            arc_status="seed",
            semantic_states={"seed": idx},
        )
        entity_ids.append(entity_id)

    scene_ids: list[str] = []
    for idx in range(scene_count):
        result = storage.create_scene_origin(
            root_id=root_id,
            branch_id=branch_id,
            title=f"Scene {idx + 1}",
            parent_act_id="act-1",
            content={
                "expected_outcome": "benchmark",
                "conflict_type": "internal",
                "actual_outcome": "benchmark",
                "summary": "benchmark",
                "pov_character_id": entity_ids[idx % len(entity_ids)],
            },
        )
        scene_ids.append(result["scene_origin_id"])

    from_candidates = random.sample(entity_ids, relation_count)
    for idx, from_id in enumerate(from_candidates):
        to_id = from_id
        while to_id == from_id:
            to_id = random.choice(entity_ids)
        relation_type = f"KNOWS_{root_id}_{idx}"
        storage.upsert_entity_relation(
            root_id=root_id,
            branch_id=branch_id,
            from_entity_id=from_id,
            to_entity_id=to_id,
            relation_type=relation_type,
            tension=50,
        )

    return entity_ids, scene_ids


def _run_workers(
    *,
    total_ops: int,
    concurrency: int,
    worker_fn,
) -> tuple[list[float], float]:
    if total_ops <= 0:
        raise ValueError("total_ops must be > 0")
    if concurrency <= 0:
        raise ValueError("concurrency must be > 0")
    per_worker = total_ops // concurrency
    remainder = total_ops % concurrency

    latencies: list[float] = []
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = []
        for idx in range(concurrency):
            count = per_worker + (1 if idx < remainder else 0)
            if count == 0:
                continue
            futures.append(executor.submit(worker_fn, idx, count))
        for future in futures:
            latencies.extend(future.result())
    duration = time.perf_counter() - start
    return latencies, duration


def _benchmark_writes(
    *,
    root_id: str,
    branch_id: str,
    total_ops: int,
    concurrency: int,
    seed: int,
) -> Metrics:
    def worker(worker_index: int, count: int) -> list[float]:
        rng = random.Random(seed + worker_index)
        storage = _create_storage()
        try:
            samples: list[float] = []
            for _ in range(count):
                start = time.perf_counter()
                storage.create_entity(
                    root_id=root_id,
                    branch_id=branch_id,
                    name=f"bench-{uuid4()}",
                    entity_type="Character",
                    tags=[],
                    arc_status="seed",
                    semantic_states={"hp": rng.randint(1, 100)},
                )
                samples.append((time.perf_counter() - start) * 1000)
            return samples
        finally:
            storage.close()

    latencies, duration = _run_workers(
        total_ops=total_ops, concurrency=concurrency, worker_fn=worker
    )
    return _format_metrics(latencies, duration)


def _benchmark_reads(
    *,
    scene_ids: list[str],
    branch_id: str,
    total_ops: int,
    concurrency: int,
    seed: int,
) -> Metrics:
    if not scene_ids:
        raise ValueError("scene_ids must not be empty")

    def worker(worker_index: int, count: int) -> list[float]:
        rng = random.Random(seed + worker_index)
        storage = _create_storage()
        try:
            samples: list[float] = []
            for _ in range(count):
                scene_id = scene_ids[rng.randrange(len(scene_ids))]
                start = time.perf_counter()
                storage.get_scene_context(scene_id=scene_id, branch_id=branch_id)
                samples.append((time.perf_counter() - start) * 1000)
            return samples
        finally:
            storage.close()

    latencies, duration = _run_workers(
        total_ops=total_ops, concurrency=concurrency, worker_fn=worker
    )
    return _format_metrics(latencies, duration)


def _cleanup(storage: MemgraphStorage, *, root_id: str) -> None:
    storage.db.execute(
        "MATCH (n {root_id: $root_id}) DETACH DELETE n;",
        {"root_id": root_id},
    )
    storage.db.execute(
        "MATCH (n:Root {id: $root_id}) DETACH DELETE n;",
        {"root_id": root_id},
    )


def _print_metrics(title: str, metrics: Metrics) -> None:
    print(title)
    print(f"  ops: {metrics.count}")
    print(f"  duration_s: {metrics.duration_s:.4f}")
    print(f"  qps: {metrics.qps:.2f}")
    print(
        "  latency_ms: "
        f"avg={metrics.avg_ms:.2f} "
        f"p50={metrics.p50_ms:.2f} "
        f"p95={metrics.p95_ms:.2f} "
        f"p99={metrics.p99_ms:.2f}"
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memgraph storage benchmark")
    parser.add_argument("--entities", type=int, default=200)
    parser.add_argument("--scenes", type=int, default=200)
    parser.add_argument("--relations", type=int, default=200)
    parser.add_argument("--write-ops", type=int, default=2000)
    parser.add_argument("--read-ops", type=int, default=2000)
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--keep-data", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    random.seed(args.seed)

    host = require_memgraph_host()
    port = require_memgraph_port()

    root_id = f"bench-{uuid4()}"
    branch_id = f"bench-{uuid4()}"

    print("Benchmark configuration:")
    print(f"  root_id: {root_id}")
    print(f"  branch_id: {branch_id}")
    print(f"  memgraph_host: {host}")
    print(f"  memgraph_port: {port}")
    print(f"  seed_entities: {args.entities}")
    print(f"  seed_scenes: {args.scenes}")
    print(f"  seed_relations: {args.relations}")
    print(f"  write_ops: {args.write_ops}")
    print(f"  read_ops: {args.read_ops}")
    print(f"  concurrency: {args.concurrency}")
    print(f"  python: {sys.version.split()[0]}")

    storage = _create_storage()
    try:
        result = next(storage.db.execute_and_fetch("RETURN 1 AS ok;"), None)
        if not result or result.get("ok") != 1:
            raise RuntimeError("Memgraph RETURN 1 failed")
        _, scene_ids = _seed_graph(
            storage,
            root_id=root_id,
            branch_id=branch_id,
            entity_count=args.entities,
            scene_count=args.scenes,
            relation_count=args.relations,
        )
    finally:
        storage.close()

    write_metrics = _benchmark_writes(
        root_id=root_id,
        branch_id=branch_id,
        total_ops=args.write_ops,
        concurrency=args.concurrency,
        seed=args.seed,
    )
    _print_metrics("Write benchmark (create_entity)", write_metrics)

    read_metrics = _benchmark_reads(
        scene_ids=scene_ids,
        branch_id=branch_id,
        total_ops=args.read_ops,
        concurrency=args.concurrency,
        seed=args.seed,
    )
    _print_metrics("Read benchmark (get_scene_context)", read_metrics)

    if not args.keep_data:
        storage = _create_storage()
        try:
            _cleanup(storage, root_id=root_id)
        finally:
            storage.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
