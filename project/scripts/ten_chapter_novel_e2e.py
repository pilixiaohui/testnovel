"""End-to-end novel generation script for a 10-chapter outline.

Run with:
  python project/scripts/ten_chapter_novel_e2e.py --story "你的故事概念"

API base URL must be provided via API_BASE_URL.
"""
from __future__ import annotations

import argparse
import json
import os
import unicodedata
from typing import Any, Dict, List

import requests

API_BASE_URL = os.getenv("API_BASE_URL")
if not API_BASE_URL:
    raise ValueError("API_BASE_URL is required")
API_BASE_URL = API_BASE_URL.rstrip("/")
TIMEOUT = float(os.getenv("API_TIMEOUT", "60"))

DEFAULT_STORY = "名为何方的时空旅人穿越到赛博朋克世界的日常生活故事"
CHAPTER_COUNT = 10
MIN_WORDS = 1800
MAX_WORDS = 2200


def _post(path: str, payload: Dict[str, Any]) -> Any:
    url = f"{API_BASE_URL}{path}"
    response = requests.post(url, json=payload, timeout=TIMEOUT)
    if response.status_code >= 400:
        raise RuntimeError(f"POST {path} failed: {response.status_code} {response.text}")
    return response.json()


def _get(path: str) -> Any:
    url = f"{API_BASE_URL}{path}"
    response = requests.get(url, timeout=TIMEOUT)
    if response.status_code >= 400:
        raise RuntimeError(f"GET {path} failed: {response.status_code} {response.text}")
    return response.json()


def _count_chars(content: str) -> int:
    return sum(
        1
        for ch in content
        if not ch.isspace() and not unicodedata.category(ch).startswith("P")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="10-chapter novel E2E script")
    parser.add_argument("--story", default=DEFAULT_STORY, help="故事概念")
    args = parser.parse_args()

    story = args.story

    print(f"Using API base: {API_BASE_URL}")
    print("Step1: generate loglines")
    loglines = _post("/snowflake/step1", {"idea": story})
    if not isinstance(loglines, list) or len(loglines) != 10:
        raise RuntimeError(f"step1 returned {len(loglines) if isinstance(loglines, list) else 'invalid'} loglines")
    logline = loglines[0]

    print("Step2: generate root structure")
    root = _post("/snowflake/step2", {"logline": logline})

    print("Step3: generate characters")
    characters = _post("/snowflake/step3", root)
    if not isinstance(characters, list) or not characters:
        raise RuntimeError("step3 returned empty characters")

    print("Step4: generate scenes")
    step4 = _post("/snowflake/step4", {"root": root, "characters": characters})
    root_id = step4.get("root_id")
    branch_id = step4.get("branch_id")
    scenes = step4.get("scenes", [])
    if not root_id or not branch_id:
        raise RuntimeError("step4 missing root_id or branch_id")
    if not isinstance(scenes, list) or not scenes:
        raise RuntimeError("step4 returned empty scenes")

    print("Step5a: generate acts")
    acts = _post(
        "/snowflake/step5a",
        {"root_id": root_id, "root": root, "characters": characters},
    )
    if not isinstance(acts, list) or not acts:
        raise RuntimeError("step5a returned empty acts")

    print("Step5b: generate chapters")
    chapters = _post(
        "/snowflake/step5b",
        {"root_id": root_id, "root": root, "characters": characters},
    )
    if not isinstance(chapters, list) or len(chapters) != CHAPTER_COUNT:
        raise RuntimeError(f"expected {CHAPTER_COUNT} chapters, got {len(chapters) if isinstance(chapters, list) else 'invalid'}")

    print("Step6: generate anchors")
    anchors = _post(
        f"/roots/{root_id}/anchors",
        {"branch_id": branch_id, "root": root, "characters": characters},
    )
    if not isinstance(anchors, list) or not anchors:
        raise RuntimeError("step6 returned empty anchors")

    chapter_texts: List[Dict[str, Any]] = []
    print("Render + Review: generate content and approve chapters")
    for chapter in chapters:
        chapter_id = chapter.get("id")
        title = chapter.get("title")
        if not chapter_id or not title:
            raise RuntimeError("chapter missing id or title")

        render_payload = _post(f"/chapters/{chapter_id}/render", {})
        content = render_payload.get("rendered_content")
        if not content:
            raise RuntimeError(f"chapter {chapter_id} render returned empty content")
        word_count = _count_chars(content)
        if not MIN_WORDS <= word_count <= MAX_WORDS:
            raise RuntimeError(
                f"chapter {chapter_id} word count {word_count} not in {MIN_WORDS}-{MAX_WORDS}"
            )

        review_payload = _post(
            f"/chapters/{chapter_id}/review",
            {"status": "approved"},
        )
        if review_payload.get("review_status") != "approved":
            raise RuntimeError(f"chapter {chapter_id} review failed")

        chapter_state = _get(f"/chapters/{chapter_id}")
        if chapter_state.get("review_status") != "approved":
            raise RuntimeError(f"chapter {chapter_id} review_status not approved")

        chapter_texts.append(
            {
                "id": chapter_id,
                "title": title,
                "word_count": word_count,
                "content": content,
            }
        )

    summary = {
        "story": story,
        "logline": logline,
        "root_id": root_id,
        "branch_id": branch_id,
        "chapter_count": len(chapter_texts),
        "anchor_count": len(anchors),
    }
    print("Summary:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n===== Full Novel =====")
    for idx, chapter in enumerate(chapter_texts, start=1):
        print(f"\n--- Chapter {idx}: {chapter['title']} (count={chapter['word_count']}) ---\n")
        print(chapter["content"])


if __name__ == "__main__":
    main()
