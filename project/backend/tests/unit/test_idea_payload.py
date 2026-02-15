from app.models import IdeaPayload


def test_idea_payload_allows_special_characters():
    payload = IdeaPayload(idea="<script>alert('x')</script> 你好！@#")
    assert "<script>" in payload.idea
