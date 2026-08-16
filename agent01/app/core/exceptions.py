class UpstreamTimeoutError(Exception):
    """上游服务请求超时。"""

    pass


class UpstreamServiceError(Exception):
    """上游服务调用失败。"""

    pass