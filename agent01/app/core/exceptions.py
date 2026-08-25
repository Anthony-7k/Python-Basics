class UpstreamTimeoutError(Exception):
    """上游服务请求超时。"""

    pass


class UpstreamServiceError(Exception):
    """上游服务调用失败。"""

    pass

class ConversationNotFoundError(
    Exception
):
    """指定的会话不存在。"""

    pass


class KnowledgeBaseNotFoundError(
    Exception
):
    """指定的知识库不存在。"""

    pass


class ConversationKnowledgeBaseMismatchError(
    Exception
):
    """会话与指定知识库不匹配。"""

    pass


class DocumentReindexConflictError(Exception):
    """文档当前状态不允许重新索引。"""

    pass


class DocumentFileMissingError(Exception):
    """文档的本地源文件已经不存在。"""

    pass


class RateLimitExceededError(Exception):
    """进程内请求速率已超过演示配置。"""

    def __init__(
        self,
        retry_after_seconds: int,
    ) -> None:
        super().__init__("Request rate limit exceeded")
        self.retry_after_seconds = (
            retry_after_seconds
        )
