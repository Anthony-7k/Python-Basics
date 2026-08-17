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