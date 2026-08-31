"""Shell-completion helpers for command arguments and options."""

from wv.core.session import DETECTION_LABELS
from wv.use_cases.session._shared import SessionError
from wv.use_cases.session.list import ListSessionsInput
from wv.use_cases.session.list import run as run_list_sessions
from wv.workspace.common import WorkspaceError


def complete_session_id(incomplete: str) -> list[str]:
    """Complete managed session IDs matching the typed prefix."""
    return _complete_sessions(incomplete, completed_detection_only=False)


def complete_reviewable_session_id(incomplete: str) -> list[str]:
    """Complete session IDs whose content detection is ready for GUI review."""
    return _complete_sessions(incomplete, completed_detection_only=True)


def complete_detection_label(incomplete: str) -> list[str]:
    """Complete supported detection labels case-insensitively."""
    normalized = incomplete.lower()
    return [label for label in DETECTION_LABELS if label.startswith(normalized)]


def _complete_sessions(incomplete: str, *, completed_detection_only: bool) -> list[str]:
    try:
        return [
            session.id
            for session in run_list_sessions(
                ListSessionsInput(
                    completed_detection_only=completed_detection_only,
                    limit=100,
                )
            ).items
            if session.id.startswith(incomplete)
        ]
    except (SessionError, WorkspaceError):
        return []
