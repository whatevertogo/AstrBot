"""SDK-local rich message result objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .message_components import (
    BaseMessageComponent,
    Plain,
    component_to_payload,
    component_to_payload_sync,
    is_message_component,
)


class EventResultType(str, Enum):
    EMPTY = "empty"
    CHAIN = "chain"


@dataclass(slots=True)
class MessageChain:
    components: list[BaseMessageComponent] = field(default_factory=list)

    def to_payload(self) -> list[dict[str, Any]]:
        return [component_to_payload_sync(component) for component in self.components]

    async def to_payload_async(self) -> list[dict[str, Any]]:
        return [await component_to_payload(component) for component in self.components]

    def get_plain_text(self, with_other_comps_mark: bool = False) -> str:
        texts: list[str] = []
        for component in self.components:
            if isinstance(component, Plain):
                texts.append(component.text)
            elif with_other_comps_mark:
                texts.append(f"[{component.__class__.__name__}]")
        return " ".join(texts)


@dataclass(slots=True)
class MessageEventResult:
    type: EventResultType = EventResultType.EMPTY
    chain: MessageChain = field(default_factory=MessageChain)


def coerce_message_chain(value: Any) -> MessageChain | None:
    if isinstance(value, MessageEventResult):
        return value.chain
    if isinstance(value, MessageChain):
        return value
    if is_message_component(value):
        return MessageChain([value])
    if isinstance(value, (list, tuple)) and all(
        is_message_component(item) for item in value
    ):
        return MessageChain(list(value))
    return None


__all__ = [
    "EventResultType",
    "MessageChain",
    "MessageEventResult",
    "coerce_message_chain",
]
