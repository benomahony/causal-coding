from __future__ import annotations

from collections.abc import Iterable

from sqlmodel import Session, SQLModel


def save_events(session: Session, events: Iterable[SQLModel]) -> None:
    """Insert already-validated event instances. Insert-only, by design.

    Nothing here updates or deletes a row -- these are events, not mutable
    state; a later observation of the same entity (e.g. a PR after it merges)
    is a new row, not an edit to an old one.
    """
    for event in events:
        session.add(event)
    session.commit()
