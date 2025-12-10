"""Kùzu Graph 存储封装，用于持久化雪花结构。"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence
from uuid import UUID, uuid4

import kuzu

from app.models import CharacterSheet, SceneNode, SnowflakeRoot


class GraphStorage:
    """封装 Kùzu 的基本写入与查询。"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = kuzu.Database(str(self.db_path))
        self.conn = kuzu.Connection(self.db)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.conn.execute(
            """
            CREATE NODE TABLE IF NOT EXISTS Root(
                id STRING,
                logline STRING,
                theme STRING,
                ending STRING,
                PRIMARY KEY (id)
            );
            """
        )
        self.conn.execute(
            """
            CREATE NODE TABLE IF NOT EXISTS Character(
                id STRING,
                name STRING,
                ambition STRING,
                conflict STRING,
                epiphany STRING,
                voice_dna STRING,
                root_id STRING,
                PRIMARY KEY (id)
            );
            """
        )
        self.conn.execute(
            """
            CREATE NODE TABLE IF NOT EXISTS Scene(
                id STRING,
                expected_outcome STRING,
                conflict_type STRING,
                logic_exception BOOLEAN,
                parent_act_id STRING,
                root_id STRING,
                PRIMARY KEY (id)
            );
            """
        )

    def save_snowflake(
        self,
        root: SnowflakeRoot,
        characters: Sequence[CharacterSheet],
        scenes: Sequence[SceneNode],
    ) -> str:
        root_id = str(uuid4())

        def esc(value: str) -> str:
            return value.replace("'", "''")

        self.conn.execute(
            f"CREATE (:Root {{id: '{root_id}', logline: '{esc(root.logline)}', "
            f"theme: '{esc(root.theme)}', ending: '{esc(root.ending)}'}});"
        )

        for c in characters:
            self.conn.execute(
                f"CREATE (:Character {{id: '{c.entity_id}', name: '{esc(c.name)}', "
                f"ambition: '{esc(c.ambition)}', conflict: '{esc(c.conflict)}', "
                f"epiphany: '{esc(c.epiphany)}', voice_dna: '{esc(c.voice_dna)}', "
                f"root_id: '{root_id}'}});"
            )

        for s in scenes:
            parent = "NULL" if s.parent_act_id is None else f"'{s.parent_act_id}'"
            self.conn.execute(
                f"CREATE (:Scene {{id: '{s.id}', expected_outcome: '{esc(s.expected_outcome)}', "
                f"conflict_type: '{esc(s.conflict_type)}', "
                f"logic_exception: {str(bool(s.logic_exception)).lower()}, "
                f"parent_act_id: {parent}, root_id: '{root_id}'}});"
            )

        return root_id

    def count_scenes(self, root_id: str) -> int:
        result = self.conn.execute(
            f"MATCH (s:Scene) WHERE s.root_id='{root_id}' RETURN COUNT(*)"
        )
        rows = [row[0] for row in result]
        return rows[0] if rows else 0

    def fetch_scene_ids(self, root_id: str) -> list[str]:
        result = self.conn.execute(
            f"MATCH (s:Scene) WHERE s.root_id='{root_id}' RETURN s.id"
        )
        return [row[0] for row in result]
