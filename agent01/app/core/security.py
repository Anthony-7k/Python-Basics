from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class AuthenticatedUser:
    email: str
    display_name: str | None = None

    @property
    def audit_id(self) -> str:
        return sha256(
            self.email.encode("utf-8")
        ).hexdigest()[:16]
