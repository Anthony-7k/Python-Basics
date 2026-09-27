from __future__ import annotations

from datetime import date, timedelta

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Enterprise Tools",
    instructions="Read-only enterprise policy and workday tools for the portfolio MVP.",
)


@mcp.tool()
def get_company_policy(topic: str) -> dict:
    """Return a deterministic company policy with a traceable source."""
    if "差旅" in topic or "报销" in topic:
        answer = "上海差旅单日合计上限为 750 元。"
        source = "mcp://company-policy/shanghai-travel"
    elif "年假" in topic or "休假" in topic:
        answer = "示例制度规定员工每年享有 10 天年假。"
        source = "mcp://employee-handbook/annual-leave"
    else:
        answer = "没有找到匹配的示例制度。"
        source = "mcp://company-policy/unanswerable"
    return {
        "answer": answer,
        "sources": [{"source_id": "MCP1", "uri": source, "untrusted": True}],
    }


@mcp.tool()
def calculate_workdays(start_date: str, days: int) -> dict:
    """Return a sequence of weekdays beginning on the requested date."""
    if days < 1 or days > 60:
        raise ValueError("days must be between 1 and 60")
    current = date.fromisoformat(start_date)
    result: list[str] = []
    while len(result) < days:
        if current.weekday() < 5:
            result.append(current.isoformat())
        current += timedelta(days=1)
    return {"workdays": result, "end_date": result[-1]}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
