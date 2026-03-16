from __future__ import annotations

from ..contracts import TeamMailboxMessage, TeamMailboxState
from ..utils import now_iso

_MANAGER_RECIPIENTS = {"A0", "a0", "manager", "all"}
_MANAGER_SCOPES = {"broadcast", "manager"}


def is_resolved_message(message: TeamMailboxMessage | dict[str, object] | None) -> bool:
    normalized = message if isinstance(message, dict) else {}
    return str(normalized.get("ack_state") or "").strip() == "resolved"


def is_manager_message(message: TeamMailboxMessage | dict[str, object] | None) -> bool:
    normalized = message if isinstance(message, dict) else {}
    recipient = str(normalized.get("to") or "").strip()
    scope = str(normalized.get("scope") or "").strip()
    return recipient in _MANAGER_RECIPIENTS or scope in _MANAGER_SCOPES


def pending_mailbox_messages(messages: list[TeamMailboxMessage] | None) -> list[TeamMailboxMessage]:
    normalized_messages = messages if isinstance(messages, list) else []
    return [item for item in normalized_messages if isinstance(item, dict) and not is_resolved_message(item)]


def manager_inbox(messages: list[TeamMailboxMessage] | None) -> list[TeamMailboxMessage]:
    return [item for item in pending_mailbox_messages(messages) if is_manager_message(item)]


def build_team_mailbox_catalog(
    messages: list[TeamMailboxMessage] | None,
    *,
    message_limit: int = 50,
    inbox_limit: int = 20,
) -> TeamMailboxState:
    normalized_messages = [item for item in (messages if isinstance(messages, list) else []) if isinstance(item, dict)]
    pending_messages = pending_mailbox_messages(normalized_messages)
    inbox = manager_inbox(normalized_messages)
    return {
        "messages": normalized_messages[-message_limit:],
        "pending_count": len(pending_messages),
        "a0_pending_count": len(inbox),
        "a0_inbox": inbox[-inbox_limit:],
        "last_updated": now_iso(),
    }
