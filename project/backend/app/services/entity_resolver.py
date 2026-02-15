"""Entity mention resolver that delegates to a structured gateway."""

from __future__ import annotations

from typing import Any, Sequence


class EntityResolver:
    def __init__(self, gateway: Any) -> None:
        self._gateway = gateway

    @staticmethod
    def _build_payload(text: str, known_entities: Sequence[Any]) -> dict[str, Any]:
        return {
            "text": text,
            "known_entities": [
                {
                    "id": entity.id,
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                }
                for entity in known_entities
            ],
        }

    @staticmethod
    def _filter_cached_mentions(
        text: str, mention_cache: dict[str, str]
    ) -> dict[str, str]:
        return {
            mention: entity_id
            for mention, entity_id in mention_cache.items()
            if mention in text
        }

    async def resolve_mentions(
        self,
        *,
        text: str,
        known_entities: Sequence[Any],
    ) -> dict[str, str]:
        payload = self._build_payload(text, known_entities)
        return await self._gateway.generate_structured(payload)

    async def resolve_incremental(
        self,
        *,
        text: str,
        known_entities: Sequence[Any],
        mention_cache: dict[str, str],
    ) -> dict[str, str]:
        cached_mentions = self._filter_cached_mentions(text, mention_cache)
        missing_entities = [
            entity
            for entity in known_entities
            if entity.name in text and entity.name not in mention_cache
        ]
        if not missing_entities:
            return cached_mentions

        resolved = await self.resolve_mentions(
            text=text,
            known_entities=known_entities,
        )
        mention_cache.update(resolved)
        return {**cached_mentions, **resolved}

    async def resolve_full_book(
        self,
        *,
        chunks: Sequence[str],
        known_entities: Sequence[Any],
        mention_cache: dict[str, str],
    ) -> dict[str, str]:
        merged: dict[str, str] = {}
        for chunk in chunks:
            resolved = await self.resolve_mentions(
                text=chunk,
                known_entities=known_entities,
            )
            mention_cache.update(resolved)
            merged.update(resolved)
        return merged
