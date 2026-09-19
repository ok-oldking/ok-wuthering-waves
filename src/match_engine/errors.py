from __future__ import annotations

from typing import Optional


class MatchEngineError(Exception):
    def __init__(
        self,
        message: str,
        *,
        path: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        self.message = message
        self.path = path
        self.name = name
        super().__init__(self._format())

    def _format(self) -> str:
        parts = [self.message]
        if self.path is not None:
            parts.append(f"path={self.path!r}")
        if self.name is not None:
            parts.append(f"name={self.name!r}")
        return " | ".join(parts)


__all__ = ["MatchEngineError"]
