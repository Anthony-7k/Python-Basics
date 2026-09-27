from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.database import Database
from app.domain import AgentRequest, TaskStatus
from app.service import AgentService
from app.tools import build_tool_registry


async def main() -> None:
    with TemporaryDirectory() as directory:
        database = Database(f"sqlite:///{Path(directory) / 'demo.db'}")
        database.create_all()
        settings = Settings(
            database_url="sqlite://",
            planner_mode="rule_based",
            knowledge_backend="sample",
            log_level="WARNING",
        )
        registry = build_tool_registry(settings)
        session = database.session_factory()
        service = AgentService(session, settings, registry=registry)

        demos = [
            ("Knowledge", "查询公司年假制度"),
            ("Multi Tool", "查询上海差旅标准并计算 3 天最高报销金额"),
            ("Multi Step", "根据年假制度从 2026-09-07 安排 3 天休假方案"),
        ]
        for name, message in demos:
            response = await service.run(
                AgentRequest(message=message, user_id="demo", session_id=name),
                f"demo-{name}",
            )
            assert response.status == TaskStatus.COMPLETED
            print(f"[{name}] {response.status}: {response.answer}")
            print("  tools:", " -> ".join(call.name for call in response.tool_calls))

        approval = await service.run(
            AgentRequest(
                message="创建任务：提交作品集演示",
                user_id="demo",
                session_id="approval",
            ),
            "demo-approval",
        )
        assert approval.status == TaskStatus.WAITING_APPROVAL
        print(f"[Human Approval] before approval: {approval.status}")
        approval = await service.approve(approval.task_id, "demo")
        assert approval.status == TaskStatus.COMPLETED
        print(f"[Human Approval] after approval: {approval.status}: {approval.answer}")

        recovery_settings = settings.model_copy(update={"tool_max_retries": 0})
        recovery = AgentService(session, recovery_settings, registry=registry)
        failed = await recovery.run(
            AgentRequest(message="演示故障恢复", user_id="demo", session_id="recovery"),
            "demo-recovery",
        )
        assert failed.status == TaskStatus.FAILED
        print(f"[Failure Recovery] injected failure: {failed.status}")
        resumed = await recovery.resume(failed.task_id, "demo")
        assert resumed.status == TaskStatus.COMPLETED
        print(f"[Failure Recovery] resumed: {resumed.status}: {resumed.answer}")

        session.close()
        database.engine.dispose()
        print("All five portfolio demos passed")


if __name__ == "__main__":
    asyncio.run(main())
