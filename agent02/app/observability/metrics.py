from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock


def _labels(values: dict[str, str]) -> str:
    if not values:
        return ""
    rendered = ",".join(
        f'{key}="{value.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"'
        for key, value in sorted(values.items())
    )
    return "{" + rendered + "}"


class MetricsRegistry:
    """Small in-process Prometheus registry with bounded latency samples."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = (
            defaultdict(float)
        )
        self._latencies: dict[tuple[str, tuple[tuple[str, str], ...]], deque[float]] = (
            defaultdict(lambda: deque(maxlen=2048))
        )

    def increment(self, name: str, value: float = 1, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] += value

    def observe(self, name: str, value: float, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._latencies[key].append(max(0.0, value))

    def observe_http(
        self, method: str, route: str, status_code: int, latency_ms: float
    ) -> None:
        labels = {"method": method, "route": route, "status": str(status_code)}
        self.increment("agent_http_requests_total", **labels)
        self.observe(
            "agent_http_request_duration_ms", latency_ms, method=method, route=route
        )

    def observe_task(self, status: str) -> None:
        self.increment("agent_tasks_total", status=status)

    def observe_tool(
        self, name: str, success: bool, retries: int, latency_ms: float
    ) -> None:
        self.increment(
            "agent_tool_calls_total",
            tool=name,
            outcome="success" if success else "failure",
        )
        self.increment("agent_tool_retries_total", retries, tool=name)
        self.observe("agent_tool_duration_ms", latency_ms, tool=name)

    def observe_llm(
        self,
        provider: str,
        model: str,
        latency_ms: float,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
        cost_usd: float | None,
        error_type: str | None = None,
    ) -> None:
        outcome = "failure" if error_type else "success"
        labels = {"provider": provider, "model": model, "outcome": outcome}
        self.increment("agent_llm_calls_total", **labels)
        self.observe(
            "agent_llm_duration_ms", latency_ms, provider=provider, model=model
        )
        if input_tokens is not None:
            self.increment(
                "agent_llm_tokens_total",
                input_tokens,
                direction="input",
                provider=provider,
                model=model,
            )
        if output_tokens is not None:
            self.increment(
                "agent_llm_tokens_total",
                output_tokens,
                direction="output",
                provider=provider,
                model=model,
            )
        if cost_usd is not None:
            self.increment(
                "agent_llm_estimated_cost_usd_total",
                cost_usd,
                provider=provider,
                model=model,
            )

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            counters = dict(self._counters)
            latencies = {key: list(values) for key, values in self._latencies.items()}
        for (name, label_items), value in sorted(counters.items()):
            lines.append(f"{name}{_labels(dict(label_items))} {value:g}")
        for (name, label_items), values in sorted(latencies.items()):
            labels = dict(label_items)
            lines.append(f"{name}_count{_labels(labels)} {len(values)}")
            lines.append(f"{name}_sum{_labels(labels)} {sum(values):g}")
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()
