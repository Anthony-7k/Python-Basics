from __future__ import annotations

import argparse
import asyncio
import json
from statistics import quantiles
from time import perf_counter

import httpx


async def run(base_url: str, token: str, concurrency: int, total: int) -> dict:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    failures: list[dict] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:

        async def request(index: int) -> None:
            async with semaphore:
                started = perf_counter()
                try:
                    response = await client.post(
                        "/api/v2/agent/chat",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "message": "查询公司年假制度",
                            "session_id": f"load-{index}",
                        },
                    )
                    if response.status_code != 200:
                        failures.append(
                            {"index": index, "status": response.status_code}
                        )
                except httpx.HTTPError as exc:
                    failures.append({"index": index, "error": type(exc).__name__})
                finally:
                    latencies.append((perf_counter() - started) * 1000)

        await asyncio.gather(*(request(index) for index in range(total)))

    p95 = quantiles(latencies, n=20)[18] if len(latencies) >= 2 else latencies[0]
    return {
        "requests": total,
        "concurrency": concurrency,
        "failures": len(failures),
        "p95_latency_ms": round(p95, 3),
        "details": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--token", required=True)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--total", type=int, default=20)
    args = parser.parse_args()
    if args.concurrency < 1 or args.total < 1:
        raise SystemExit("concurrency and total must be positive")
    result = asyncio.run(run(args.base_url, args.token, args.concurrency, args.total))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["failures"] or result["p95_latency_ms"] >= 500:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
