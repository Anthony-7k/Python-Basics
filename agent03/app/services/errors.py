class ServiceError(Exception):
    code = "service_error"
    status_code = 400


class InvalidInput(ServiceError):
    code = "invalid_input"
    status_code = 400


class Forbidden(ServiceError):
    code = "forbidden"
    status_code = 403


class Conflict(ServiceError):
    code = "conflict"
    status_code = 409

