from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class HistoryEntry:
    timestamp: datetime
    title: str
    summary: str
    success: bool
    details: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


_ENTRIES = []
_MAX_ENTRIES = 100


def add_result(result):
    entry = HistoryEntry(
        timestamp=datetime.now(),
        title=result.title,
        summary=result.summary,
        success=result.success,
        details=list(result.details or []),
        errors=list(result.errors or []),
    )
    _ENTRIES.insert(0, entry)
    del _ENTRIES[_MAX_ENTRIES:]
    return entry


def entries():
    return list(_ENTRIES)


def clear():
    _ENTRIES.clear()
