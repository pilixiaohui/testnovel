import time

import pytest


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if pct <= 0:
        return min(values)
    if pct >= 1:
        return max(values)
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    low = int(k)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return ordered[low]
    weight = k - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


class StaticGateway:
    def __init__(self, mapping: dict[str, str]):
        self._mapping = mapping

    async def generate_structured(self, payload):
        return self._mapping


@pytest.mark.asyncio
async def test_entity_resolution_performance_metrics():
    from app.services.entity_resolver import EntityResolver
    from app.storage.schema import Entity

    gateway = StaticGateway({"John": "e1", "Park": "e2"})
    resolver = EntityResolver(gateway)

    entities = [
        Entity(
            id="e1",
            root_id="root-alpha",
            branch_id="main",
            entity_type="Character",
            name="John",
            tags=[],
            semantic_states={},
            arc_status="active",
        ),
        Entity(
            id="e2",
            root_id="root-alpha",
            branch_id="main",
            entity_type="Location",
            name="Park",
            tags=[],
            semantic_states={},
            arc_status="active",
        ),
    ]
    text = "John walks to the Park."

    iterations = 50
    latencies_ms: list[float] = []
    start = time.perf_counter()
    result = None
    for _ in range(iterations):
        t0 = time.perf_counter()
        result = await resolver.resolve_mentions(text=text, known_entities=entities)
        latencies_ms.append((time.perf_counter() - t0) * 1000)
    duration = time.perf_counter() - start

    qps = iterations / duration if duration > 0 else 0.0
    p99_ms = _percentile(latencies_ms, 0.99)

    print(
        "entity_resolution_perf "
        f"iterations={iterations} duration_s={duration:.6f} "
        f"qps={qps:.2f} p99_ms={p99_ms:.4f}"
    )

    assert result == {"John": "e1", "Park": "e2"}
    assert qps >= 0
    assert p99_ms >= 0
