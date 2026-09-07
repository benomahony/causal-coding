"""Read-only SQLModel mappings onto Apache DevLake's domain-layer MySQL tables.

Column names follow DevLake's published domain layer schema
(https://devlake.apache.org/docs/DataModels/DevLakeDomainLayerSchema). Only the
columns this project's ingestion needs are declared; DevLake owns the real DDL
and these models are never used to create or migrate tables, only to select
from them. Verify field names against your installed DevLake version before
relying on this in production — the domain layer has changed across releases.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class DevLakePullRequest(SQLModel, table=True):
    __tablename__ = "pull_requests"

    id: str = Field(primary_key=True)
    base_repo_id: str | None = None
    pull_request_key: str | None = None
    status: str | None = None
    created_date: datetime
    merged_date: datetime | None = None
    closed_date: datetime | None = None


class DevLakePullRequestCommit(SQLModel, table=True):
    __tablename__ = "pull_request_commits"

    pull_request_id: str = Field(primary_key=True)
    commit_sha: str = Field(primary_key=True)


class DevLakePullRequestComment(SQLModel, table=True):
    __tablename__ = "pull_request_comments"

    id: str = Field(primary_key=True)
    pull_request_id: str
    account_id: str | None = None
    created_date: datetime
    type: str | None = None
    status: str | None = None


class DevLakeCommit(SQLModel, table=True):
    __tablename__ = "commits"

    sha: str = Field(primary_key=True)
    authored_date: datetime | None = None
    additions: int | None = None
    deletions: int | None = None


class DevLakeCommitFile(SQLModel, table=True):
    __tablename__ = "commit_files"

    id: str = Field(primary_key=True)
    commit_sha: str
    file_path: str


class DevLakeCicdTask(SQLModel, table=True):
    __tablename__ = "cicd_tasks"

    id: str = Field(primary_key=True)
    pipeline_id: str | None = None
    result: str | None = None
    status: str | None = None
    type: str | None = None
    created_date: datetime
    started_date: datetime | None = None
    finished_date: datetime | None = None


class DevLakeCicdPipelineCommit(SQLModel, table=True):
    __tablename__ = "cicd_pipeline_commits"

    pipeline_id: str = Field(primary_key=True)
    commit_sha: str = Field(primary_key=True)
    repo_id: str | None = None


class DevLakeCicdDeployment(SQLModel, table=True):
    __tablename__ = "cicd_deployments"

    id: str = Field(primary_key=True)
    result: str | None = None
    status: str | None = None
    environment: str | None = None
    created_date: datetime
    started_date: datetime | None = None
    finished_date: datetime | None = None


class DevLakeCicdDeploymentCommit(SQLModel, table=True):
    __tablename__ = "cicd_deployment_commits"

    id: str = Field(primary_key=True)
    cicd_deployment_id: str | None = None
    commit_sha: str | None = None
    repo_id: str | None = None


class DevLakeIssue(SQLModel, table=True):
    __tablename__ = "issues"

    id: str = Field(primary_key=True)
    original_project: str | None = None
    status: str | None = None
    updated_date: datetime | None = None


class DevLakeIssueChangelog(SQLModel, table=True):
    __tablename__ = "issue_changelogs"

    id: str = Field(primary_key=True)
    issue_id: str
    field_name: str | None = None
    to_value: str | None = None
    created_date: datetime


class DevLakeIncident(SQLModel, table=True):
    __tablename__ = "incidents"

    id: str = Field(primary_key=True)
    created_date: datetime | None = None
    resolution_date: datetime | None = None
    severity: str | None = None


class DevLakeProjectIssueMetric(SQLModel, table=True):
    """Maps an incident (issue) to the cicd_task id DevLake attributes it to.

    Note this links to a cicd_tasks.id, not a cicd_deployments.id -- DevLake's
    own deployment/incident attribution operates at task grain, not deployment
    grain. Resolve task -> pipeline -> cicd_pipeline_commits.repo_id yourself
    if you need a Deployment.deployment_id-compatible identifier.
    """

    __tablename__ = "project_issue_metrics"

    id: str = Field(primary_key=True)
    project_name: str = Field(primary_key=True)
    deployment_id: str | None = None
