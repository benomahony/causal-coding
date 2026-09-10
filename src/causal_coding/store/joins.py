"""Validated deployment-to-PR attribution using persisted commit identities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from causal_coding.events import Deployment, PullRequest


@dataclass(frozen=True)
class DeployedChange:
    deployment_id: str
    pull_request_id: str
    team_id: str
    first_commit_at: datetime
    deployed_at: datetime

    @property
    def lead_time_hours(self) -> float:
        return (self.deployed_at - self.first_commit_at).total_seconds() / 3600


def deployed_changes(session: Session) -> tuple[DeployedChange, ...]:
    """Join latest real snapshots, preferring merge SHAs over historical PR links.

    Only successful production deployments with a merged, same-team PR qualify.
    Repeated snapshots and later redeployments do not duplicate a delivered PR.
    """
    latest_prs = {}
    latest_deployments = {}
    for pull_request in session.exec(select(PullRequest).where(PullRequest.source_system != "fixtures").order_by(PullRequest.observed_at, PullRequest.id)):
        latest_prs[(pull_request.source_system, pull_request.pull_request_id)] = pull_request
    for deployment in session.exec(select(Deployment).where(Deployment.source_system != "fixtures").order_by(Deployment.observed_at, Deployment.id)):
        latest_deployments[(deployment.source_system, deployment.deployment_id)] = deployment
    changes = []
    delivered = set()
    for deployment in sorted(latest_deployments.values(), key=lambda row: row.deployed_at):
        if deployment.environment.upper() != "PRODUCTION" or deployment.status.upper() != "SUCCESS":
            continue
        for key, pull_request in latest_prs.items():
            if key in delivered or pull_request.source_system != deployment.source_system:
                continue
            if pull_request.team_id != deployment.team_id or pull_request.merged_at is None or pull_request.first_commit_at is None:
                continue
            commits = {pull_request.merge_commit_sha} if pull_request.merge_commit_sha else set(pull_request.commit_shas or ())
            if not commits.intersection(deployment.commit_shas):
                continue
            if deployment.deployed_at < max(pull_request.merged_at, pull_request.first_commit_at):
                continue
            changes.append(DeployedChange(
                deployment.deployment_id, pull_request.pull_request_id, pull_request.team_id,
                pull_request.first_commit_at, deployment.deployed_at,
            ))
            delivered.add(key)
    return tuple(changes)
