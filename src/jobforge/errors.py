"""Errors that end a command with a message for the user, not a traceback."""
from __future__ import annotations


class JobforgeError(Exception):
    """A problem the user can act on. The CLI prints the message and exits 1."""

    exit_code = 1

    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = list(details or [])

    def render(self) -> str:
        if not self.details:
            return self.message
        return self.message + "\n" + "\n".join(f"  - {d}" for d in self.details)


class WorkspaceError(JobforgeError):
    """No workspace, or a broken one. Exit 2 so scripts can tell it apart."""

    exit_code = 2
