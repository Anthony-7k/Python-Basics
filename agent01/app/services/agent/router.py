from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas.agent import (
    AgentRequest,
    AgentStatus,
    ToolCall,
    ToolError,
    ToolName,
)


COMPARE_PATTERN = re.compile(
    r"对比|比较|区别|差异|异同|\bvs\.?\b|\bversus\b",
    re.IGNORECASE,
)
SUMMARY_PATTERN = re.compile(
    r"总结|概括|摘要|提炼|梳理|\bsummar(?:y|ize|ise)\b",
    re.IGNORECASE,
)
DANGEROUS_ACTION_PATTERN = re.compile(
    r"(?:执行|运行|调用|打开|读取|访问|连接|请求|下载)"
    r".{0,16}"
    r"(?:shell|powershell|cmd(?:\.exe)?|sql|文件系统|本地文件|"
    r"https?://|url|动态导入|python)",
    re.IGNORECASE,
)
BOUNDARY_BYPASS_PATTERN = re.compile(
    r"(?:忽略|绕过|跳过|取消).{0,20}"
    r"(?:权限|授权|限制|系统提示|其他知识库|安全规则)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AgentRoutePlan:
    status: AgentStatus
    message: str
    tool_calls: list[ToolCall] = field(
        default_factory=list
    )
    error: ToolError | None = None


class DeterministicAgentRouter:
    """Route user intent without giving evidence control over tools."""

    def route(
        self,
        request: AgentRequest,
    ) -> AgentRoutePlan:
        instruction = request.instruction

        if (
            DANGEROUS_ACTION_PATTERN.search(instruction)
            or BOUNDARY_BYPASS_PATTERN.search(instruction)
        ):
            return AgentRoutePlan(
                status=AgentStatus.UNSUPPORTED,
                message=(
                    "该请求超出受控知识库工具范围"
                ),
                error=ToolError(
                    code="unsupported_operation",
                    message=(
                        "仅支持知识检索、单文档总结和双文档对比"
                    ),
                ),
            )

        if COMPARE_PATTERN.search(instruction):
            if len(request.document_ids) != 2:
                return self._invalid_parameters(
                    "文档对比需要提供两个不同的 document_id"
                )
            return AgentRoutePlan(
                status=AgentStatus.SUCCEEDED,
                message="已选择双文档对比工具",
                tool_calls=[
                    ToolCall(
                        tool_name=(
                            ToolName.COMPARE_DOCUMENTS
                        ),
                        selection_reason=(
                            "comparison_intent_with_two_documents"
                        ),
                        arguments={
                            "knowledge_base_id": (
                                request.knowledge_base_id
                            ),
                            "left_document_id": (
                                request.document_ids[0]
                            ),
                            "right_document_id": (
                                request.document_ids[1]
                            ),
                            "instruction": instruction,
                        },
                    )
                ],
            )

        if SUMMARY_PATTERN.search(instruction):
            if len(request.document_ids) != 1:
                return self._invalid_parameters(
                    "文档总结需要提供一个 document_id"
                )
            return AgentRoutePlan(
                status=AgentStatus.SUCCEEDED,
                message="已选择单文档总结工具",
                tool_calls=[
                    ToolCall(
                        tool_name=(
                            ToolName.SUMMARIZE_DOCUMENT
                        ),
                        selection_reason=(
                            "summary_intent_with_one_document"
                        ),
                        arguments={
                            "knowledge_base_id": (
                                request.knowledge_base_id
                            ),
                            "document_id": (
                                request.document_ids[0]
                            ),
                            "instruction": instruction,
                        },
                    )
                ],
            )

        return AgentRoutePlan(
            status=AgentStatus.SUCCEEDED,
            message="已选择知识检索工具",
            tool_calls=[
                ToolCall(
                    tool_name=(
                        ToolName.SEARCH_KNOWLEDGE
                    ),
                    selection_reason=(
                        "general_knowledge_question"
                    ),
                    arguments={
                        "knowledge_base_id": (
                            request.knowledge_base_id
                        ),
                        "query": instruction,
                        "top_k": 5,
                    },
                )
            ],
        )

    @staticmethod
    def _invalid_parameters(
        message: str,
    ) -> AgentRoutePlan:
        return AgentRoutePlan(
            status=AgentStatus.FAILED,
            message=message,
            error=ToolError(
                code="missing_required_parameters",
                message=message,
            ),
        )
