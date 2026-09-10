"""Bootstraps this project's own tables -- and only this project's own tables.

`devlake/tables.py` registers its own SQLModel classes in the same global
`SQLModel.metadata` registry (read-only mirrors of an external DevLake
database, e.g. tablename "pull_requests"). Calling `SQLModel.metadata.create_all`
unfiltered against our own store's engine would try to create those too, which
is wrong on two counts: they belong to a different database, and this project
must never write DDL against a DevLake instance it doesn't own. `create_schema`
below explicitly scopes to the tables declared in events.py, survey_events.py
and commercial_events.py.
"""

from __future__ import annotations

from sqlalchemy import Engine, MetaData, Table, inspect, select, text
from sqlalchemy.schema import CreateColumn
from sqlmodel import SQLModel

from causal_coding import commercial_events, events, survey_events

_MODULES = (events, survey_events, commercial_events)


def _own_tables() -> tuple[Table, ...]:
    tables: list[Table] = []
    seen: set[str] = set()
    for module in _MODULES:
        for obj in vars(module).values():
            table = getattr(obj, "__table__", None)
            if isinstance(table, Table) and table.name not in seen:
                seen.add(table.name)
                tables.append(table)
    return tuple(tables)


OWN_TABLES = _own_tables()


def create_schema(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine, tables=OWN_TABLES)


def upgrade_schema(engine: Engine) -> None:
    """Upgrade a legacy store without dropping event history or touching DevLake.

    Legacy DevLake PR sizes/draft flags were inferred. Clear those values once,
    when adding commit linkage, so a fresh ingestion can replace them accurately.
    """
    create_schema(engine)
    tables = (events.PullRequest.__table__, events.CIRun.__table__)
    with engine.begin() as connection:
        for table in tables:
            old_columns = {column["name"]: column for column in inspect(connection).get_columns(table.name)}
            missing = [column for column in table.columns if column.name not in old_columns]
            nullable_changes = [
                column for column in table.columns
                if column.name in old_columns and column.nullable and not old_columns[column.name]["nullable"]
            ]
            if not missing and not nullable_changes:
                continue
            legacy_pr = table.name == events.PullRequest.__tablename__ and "commit_shas" not in old_columns
            if connection.dialect.name == "sqlite":
                replacement = table.to_metadata(MetaData(), name=f"{table.name}_upgrade")
                replacement.create(connection)
                old_table = Table(table.name, MetaData(), autoload_with=connection)
                names = [column.name for column in table.columns if column.name in old_columns]
                connection.execute(replacement.insert().from_select(names, select(*(old_table.c[name] for name in names))))
                old_table.drop(connection)
                connection.execute(text(f'ALTER TABLE "{replacement.name}" RENAME TO "{table.name}"'))
            elif connection.dialect.name == "postgresql":
                for column in missing:
                    definition = str(CreateColumn(column).compile(dialect=connection.dialect))
                    connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {definition}'))
                for column in nullable_changes:
                    connection.execute(text(f'ALTER TABLE "{table.name}" ALTER COLUMN "{column.name}" DROP NOT NULL'))
            else:
                raise RuntimeError("Store upgrades support PostgreSQL and SQLite only.")
            if legacy_pr:
                connection.execute(table.update().where(table.c.source_system == "devlake").values(
                    additions=None, deletions=None, changed_files=None, is_draft=None,
                ))
            if table.name == events.CIRun.__tablename__:
                connection.execute(table.update().where(table.c.source_system == "devlake").values(required=None))


def main() -> None:
    from causal_coding.store.config import StoreConfig, engine_from_config

    upgrade_schema(engine_from_config(StoreConfig.from_env()))
    print("Store schema is up to date. Existing event history is preserved.")
