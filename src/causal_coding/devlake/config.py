from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from sqlalchemy import URL, Engine
from sqlmodel import create_engine


class DevLakeConfig(BaseModel):
    """Connection settings for DevLake's domain-layer MySQL database.

    DevLake exposes no query API for collected data (its REST API only manages
    connections/plugins/pipelines); the domain layer lands in MySQL and that is
    what every downstream consumer, including this one, reads directly.
    """

    model_config = ConfigDict(frozen=True)

    host: str
    port: int = 3306
    user: str
    password: str
    database: str

    @classmethod
    def from_env(cls) -> DevLakeConfig:
        """Read connection settings from DEVLAKE_DB_* environment variables."""
        required = ("DEVLAKE_DB_HOST", "DEVLAKE_DB_USER", "DEVLAKE_DB_PASSWORD", "DEVLAKE_DB_NAME")
        missing = [name for name in required if name not in os.environ]
        if missing:
            raise RuntimeError(
                f"Missing DevLake connection env var(s): {', '.join(missing)}. "
                "DEVLAKE_DB_PORT defaults to 3306 if unset."
            )
        return cls(
            host=os.environ["DEVLAKE_DB_HOST"],
            port=int(os.environ.get("DEVLAKE_DB_PORT", "3306")),
            user=os.environ["DEVLAKE_DB_USER"],
            password=os.environ["DEVLAKE_DB_PASSWORD"],
            database=os.environ["DEVLAKE_DB_NAME"],
        )

    @property
    def sqlalchemy_url(self) -> URL:
        return URL.create(
            "mysql+pymysql", username=self.user, password=self.password,
            host=self.host, port=self.port, database=self.database,
        )


def engine_from_config(config: DevLakeConfig) -> Engine:
    return create_engine(config.sqlalchemy_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})


def load_team_map(path: Path) -> dict[str, str]:
    """Load a DevLake scope key -> team_id mapping maintained outside DevLake.

    The domain layer has no team concept. Keys are either a DevLake repo id
    (``repos.id``, e.g. ``"github:GithubRepo:1:12345"``) for repo-scoped
    entities (pull requests, deployments) or an issue tracker project name
    (``issues.original_project``) for issue-tracker entities. Both key
    namespaces share one file; keep them unambiguous in practice (DevLake repo
    ids always carry a ``:`` scoped prefix, project names usually don't).

    Expected JSON shape::

        {
          "github:GithubRepo:1:12345": "team-checkout",
          "CHECKOUT": "team-checkout"
        }
    """
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        raise ValueError(f"{path} must contain a flat JSON object of string -> string")
    return data
