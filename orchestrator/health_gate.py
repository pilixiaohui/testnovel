from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .runtime_context import RuntimeContext


@dataclass(frozen=True)
class HealthGateResult:
    ready: bool
    findings: list[str]
    evidence: str


def _probe_http(url: str, *, timeout_seconds: float) -> tuple[bool, str]:
    req = Request(url=url, method="GET")
    try:
        with urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310
            return True, f"{url} -> {resp.status}"
    except HTTPError as exc:
        # 4xx/5xx 说明服务可达，但接口状态异常
        return True, f"{url} -> HTTP {exc.code}"
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        return False, f"{url} -> unreachable ({reason})"
    except TimeoutError as exc:
        return False, f"{url} -> timeout ({exc})"


def run_pre_validation_health_check(
    *,
    context: RuntimeContext,
    timeout_seconds: float = 5.0,
) -> HealthGateResult:
    """验证前基础设施门禁：前端可达 + 后端可达。"""
    findings: list[str] = []
    evidence_lines: list[str] = []

    frontend_ok, frontend_evidence = _probe_http(context.frontend_url, timeout_seconds=timeout_seconds)
    evidence_lines.append(frontend_evidence)
    if not frontend_ok:
        findings.append(f"前端不可达: {context.frontend_url}")

    backend_docs_url = f"{context.backend_base_url}/docs"
    backend_ok, backend_evidence = _probe_http(backend_docs_url, timeout_seconds=timeout_seconds)
    evidence_lines.append(backend_evidence)

    if not backend_ok:
        backend_openapi_url = f"{context.backend_base_url}/openapi.json"
        openapi_ok, openapi_evidence = _probe_http(backend_openapi_url, timeout_seconds=timeout_seconds)
        evidence_lines.append(openapi_evidence)
        backend_ok = openapi_ok

    if not backend_ok:
        findings.append(f"后端不可达: {context.backend_base_url}")

    ready = frontend_ok and backend_ok
    if ready:
        findings.append("基础设施门禁通过")

    return HealthGateResult(
        ready=ready,
        findings=findings,
        evidence="; ".join(evidence_lines),
    )
