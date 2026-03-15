from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MessageSession:
    """SDK-visible message session identifier.

    The string form stays compatible with AstrBot's unified message origin:
    ``platform_id:message_type:session_id``.
    """

    platform_id: str
    message_type: str
    session_id: str

    def __post_init__(self) -> None:
        self.platform_id = str(self.platform_id)
        self.message_type = str(self.message_type).lower()
        self.session_id = str(self.session_id)

    def __str__(self) -> str:
        return f"{self.platform_id}:{self.message_type}:{self.session_id}"

    @classmethod
    def from_str(cls, session: str) -> MessageSession:
        platform_id, message_type, session_id = str(session).split(":", 2)
        return cls(
            platform_id=platform_id,
            message_type=message_type,
            session_id=session_id,
        )
