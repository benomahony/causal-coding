from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict
from sqlalchemy import URL, Engine
from sqlmodel import create_engine


class StoreConfig(BaseModel):
    """Connection settings for this project's own Postgres store.

    Distinct from devlake.config.DevLakeConfig: that connects read-only to an
    external DevLake instance's database; this is the database this project
    owns, that ingestion connectors (devlake/ or otherwise) write into.
    """

    model_config = ConfigDict(frozen=True)

    host: str
    port: int = 5432
    user: str
    password: str
    database: str

    @classmethod
    def from_env(cls) -> StoreConfig:
        required = ("CAUSAL_STORE_DB_HOST", "CAUSAL_STORE_DB_USER", "CAUSAL_STORE_DB_PASSWORD", "CAUSAL_STORE_DB_NAME")
        missing = [name for name in required if name not in os.environ]
        if missing:
            raise RuntimeError(
                f"Missing store connection env var(s): {', '.join(missing)}. "
                "CAUSAL_STORE_DB_PORT defaults to 5432 if unset."
            )
        return cls(
            host=os.environ["CAUSAL_STORE_DB_HOST"],
            port=int(os.environ.get("CAUSAL_STORE_DB_PORT", "5432")),
            user=os.environ["CAUSAL_STORE_DB_USER"],
            password=os.environ["CAUSAL_STORE_DB_PASSWORD"],
            database=os.environ["CAUSAL_STORE_DB_NAME"],
        )

    @property
    def sqlalchemy_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg", username=self.user, password=self.password,
            host=self.host, port=self.port, database=self.database,
        )


def engine_from_config(config: StoreConfig) -> Engine:
    return create_engine(config.sqlalchemy_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
