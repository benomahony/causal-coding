"""Map DevLake domain-layer rows onto this project's normalised event contracts.

Every function here is a best-effort translation, not a guarantee of
completeness: DevLake's domain layer does not carry some fields this project's
event contracts ask for (pull request draft state, deployment rollback
linkage, "required" CI check status). Those are set to an explicit,
documented default rather than guessed. See the docstring on each function for
what is and isn't recoverable from DevLake alone.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from causal_coding.events import CIRun, Deployment, Incident, PullRequest, ReviewEvent, WorkItem

from .tables import (
    DevLakeCicdDeployment,
    DevLakeCicdDeploymentCommit,
    DevLakeCicdPipelineCommit,
    DevLakeCicdTask,
    DevLakeCommit,
    DevLakeCommitFile,
    DevLakeIncident,
    DevLakeIssue,
    DevLakeIssueChangelog,
    DevLakePullRequest,
    DevLakePullRequestComment,
    DevLakePullRequestCommit,
)

SOURCE_SYSTEM = "devlake"


class Ingested[T](BaseModel):
    """Successfully mapped events, plus the scope keys team_map couldn't resolve.

    Records with an unmapped scope key are dropped from `events` rather than
    emitted with a guessed team_id -- surface `unmapped_scope_keys` to the
    caller instead of silently under- or mis-attributing data.
    """

    model_config = ConfigDict(frozen=True)

    events: tuple[T, ...]
    unmapped_scope_keys: frozenset[str] = frozenset()


def fetch_pull_requests(
    session: Session, team_map: dict[str, str], *, since: datetime | None = None
) -> Ingested[PullRequest]:
    """Build PullRequest events from pull_requests (+ linked commits for size/first-commit).

    Caveats: DevLake's domain layer does not track draft status, so
    ``is_draft`` is always False.
    """
    query = select(DevLakePullRequest)
    if since is not None:
        query = query.where(DevLakePullRequest.created_date >= since)
    pr_rows = session.exec(query).all()
    pr_ids = [row.id for row in pr_rows]

    commit_links = (
        session.exec(select(DevLakePullRequestCommit).where(DevLakePullRequestCommit.pull_request_id.in_(pr_ids))).all()
        if pr_ids
        else []
    )
    shas_by_pr: dict[str, list[str]] = defaultdict(list)
    for link in commit_links:
        shas_by_pr[link.pull_request_id].append(link.commit_sha)

    all_shas = [link.commit_sha for link in commit_links]
    commits_by_sha = {
        c.sha: c for c in (session.exec(select(DevLakeCommit).where(DevLakeCommit.sha.in_(all_shas))).all() if all_shas else [])
    }
    files_by_sha: dict[str, set[str]] = defaultdict(set)
    if all_shas:
        for f in session.exec(select(DevLakeCommitFile).where(DevLakeCommitFile.commit_sha.in_(all_shas))).all():
            files_by_sha[f.commit_sha].add(f.file_path)

    events: list[PullRequest] = []
    unmapped: set[str] = set()
    for row in pr_rows:
        scope_key = row.base_repo_id or ""
        team_id = team_map.get(scope_key)
        if team_id is None:
            unmapped.add(scope_key or "<missing base_repo_id>")
            continue

        shas = shas_by_pr.get(row.id, [])
        commits = [commits_by_sha[s] for s in shas if s in commits_by_sha]
        changed_files = tuple(sorted({path for s in shas for path in files_by_sha.get(s, ())}))
        first_commit_at = min((c.authored_date for c in commits if c.authored_date is not None), default=None)

        events.append(
            PullRequest(
                observed_at=row.created_date,
                source_system=SOURCE_SYSTEM,
                pull_request_id=row.id,
                repository_id=row.base_repo_id or "",
                team_id=team_id,
                opened_at=row.created_date,
                merged_at=row.merged_date,
                closed_at=row.closed_date,
                is_draft=False,
                additions=sum(c.additions or 0 for c in commits),
                deletions=sum(c.deletions or 0 for c in commits),
                changed_files=changed_files,
                first_commit_at=first_commit_at,
            )
        )
    return Ingested(events=tuple(events), unmapped_scope_keys=frozenset(unmapped))


def fetch_review_events(
    session: Session, *, review_types: tuple[str, ...] = ("REVIEW",), since: datetime | None = None
) -> tuple[ReviewEvent, ...]:
    """Build ReviewEvent events from pull_request_comments filtered to review-type rows.

    Caveat: the literal `type` values distinguishing a review from a plain
    comment are connector-specific (they come from whichever DevLake plugin
    collected the PR -- GitHub, GitLab, ...). Verify `review_types` against
    the actual values in your `pull_request_comments.type` column; "REVIEW"
    is a reasonable default, not a documented constant.
    """
    query = select(DevLakePullRequestComment).where(DevLakePullRequestComment.type.in_(review_types))
    if since is not None:
        query = query.where(DevLakePullRequestComment.created_date >= since)
    rows = session.exec(query).all()
    return tuple(
        ReviewEvent(
            observed_at=row.created_date,
            source_system=SOURCE_SYSTEM,
            pull_request_id=row.pull_request_id,
            reviewer_id=row.account_id or "",
            review_submitted_at=row.created_date,
            state=row.status or row.type or "",
            substantive=True,
        )
        for row in rows
    )


def fetch_ci_runs(session: Session, *, since: datetime | None = None) -> tuple[CIRun, ...]:
    """Build CIRun events from cicd_tasks, joined to cicd_pipeline_commits for commit_sha.

    Caveats: DevLake does not track which checks are "required" -- every run
    is emitted with `required=True`; filter/reclassify downstream if your
    CI has optional jobs. `commit_sha` is "" when no pipeline-commit linkage
    exists for the task's pipeline (e.g. manually triggered pipelines).
    `pull_request_id` is always None -- DevLake's domain layer does not link
    cicd_tasks to pull requests.
    """
    query = select(DevLakeCicdTask)
    if since is not None:
        query = query.where(DevLakeCicdTask.created_date >= since)
    task_rows = session.exec(query).all()

    pipeline_ids = [row.pipeline_id for row in task_rows if row.pipeline_id is not None]
    pipeline_commits = (
        session.exec(select(DevLakeCicdPipelineCommit).where(DevLakeCicdPipelineCommit.pipeline_id.in_(pipeline_ids))).all()
        if pipeline_ids
        else []
    )
    sha_by_pipeline: dict[str, str] = {}
    for link in pipeline_commits:
        sha_by_pipeline.setdefault(link.pipeline_id, link.commit_sha)

    return tuple(
        CIRun(
            observed_at=row.created_date,
            source_system=SOURCE_SYSTEM,
            ci_run_id=row.id,
            pull_request_id=None,
            commit_sha=sha_by_pipeline.get(row.pipeline_id or "", ""),
            check_category=row.type or "unknown",
            required=True,
            triggered_at=row.created_date,
            started_at=row.started_date,
            completed_at=row.finished_date,
            result=row.result,
            failure_classification=None,
        )
        for row in task_rows
    )


def fetch_deployments(
    session: Session, team_map: dict[str, str], *, since: datetime | None = None
) -> Ingested[Deployment]:
    """Build Deployment events from cicd_deployments (+ cicd_deployment_commits for repo/shas).

    Caveats: `manual_intervention`, `deployment_type` and
    `rollback_of_deployment_id` are not tracked in DevLake's domain layer and
    are always None. Team is resolved from the repo of the deployment's first
    linked commit; a deployment spanning multiple repos with different teams
    will be attributed to only one.
    """
    query = select(DevLakeCicdDeployment)
    if since is not None:
        query = query.where(DevLakeCicdDeployment.created_date >= since)
    deployment_rows = session.exec(query).all()
    deployment_ids = [row.id for row in deployment_rows]

    commit_links = (
        session.exec(
            select(DevLakeCicdDeploymentCommit).where(DevLakeCicdDeploymentCommit.cicd_deployment_id.in_(deployment_ids))
        ).all()
        if deployment_ids
        else []
    )
    links_by_deployment: dict[str, list[DevLakeCicdDeploymentCommit]] = defaultdict(list)
    for link in commit_links:
        if link.cicd_deployment_id is not None:
            links_by_deployment[link.cicd_deployment_id].append(link)

    events: list[Deployment] = []
    unmapped: set[str] = set()
    for row in deployment_rows:
        links = links_by_deployment.get(row.id, [])
        repo_id = next((link.repo_id for link in links if link.repo_id), None)
        team_id = team_map.get(repo_id or "")
        if team_id is None:
            unmapped.add(repo_id or "<no linked repo>")
            continue

        commit_shas = tuple(dict.fromkeys(link.commit_sha for link in links if link.commit_sha))
        deployed_at = row.finished_date or row.started_date or row.created_date

        events.append(
            Deployment(
                observed_at=row.created_date,
                source_system=SOURCE_SYSTEM,
                deployment_id=row.id,
                team_id=team_id,
                environment=row.environment or "unknown",
                status=row.result or row.status or "unknown",
                deployed_at=deployed_at,
                commit_shas=commit_shas,
                manual_intervention=None,
                deployment_type=None,
                rollback_of_deployment_id=None,
            )
        )
    return Ingested(events=tuple(events), unmapped_scope_keys=frozenset(unmapped))


def fetch_incidents(session: Session, *, since: datetime | None = None) -> tuple[Incident, ...]:
    """Build Incident events from the incidents table.

    Caveat: `attributable_deployment_ids` is always empty. DevLake's
    project_issue_metrics.deployment_id links an incident to a cicd_task id,
    not a Deployment.deployment_id (cicd_deployments.id) -- the two are not
    directly comparable, so this project does not fabricate a linkage here.
    Resolve task -> pipeline -> cicd_pipeline_commits -> cicd_deployment_commits
    yourself if you need that attribution, and treat it as approximate.
    """
    query = select(DevLakeIncident)
    if since is not None:
        query = query.where(DevLakeIncident.created_date >= since)
    rows = session.exec(query).all()
    return tuple(
        Incident(
            observed_at=row.created_date or row.resolution_date,
            source_system=SOURCE_SYSTEM,
            incident_id=row.id,
            started_at=row.created_date,
            resolved_at=row.resolution_date,
            severity=row.severity,
            attributable_deployment_ids=(),
        )
        for row in rows
        if row.created_date is not None
    )


def fetch_work_items(
    session: Session, team_map: dict[str, str], *, since: datetime | None = None, status_field_names: tuple[str, ...] = ("status",)
) -> Ingested[WorkItem]:
    """Build WorkItem events (one per status transition) from issue_changelogs joined to issues.

    Using issue_changelogs rather than issues.updated_date gives an actual
    status-changed-at timestamp per transition, matching this project's event
    semantics. Caveat: the changelog `field_name` literal for a status change
    is connector-specific (e.g. Jira vs GitHub Issues); verify
    `status_field_names` against your data.
    """
    issue_query = select(DevLakeIssue)
    issue_rows = session.exec(issue_query).all()
    project_by_issue = {row.id: row.original_project for row in issue_rows}

    changelog_query = select(DevLakeIssueChangelog).where(DevLakeIssueChangelog.field_name.in_(status_field_names))
    if since is not None:
        changelog_query = changelog_query.where(DevLakeIssueChangelog.created_date >= since)
    changelog_rows = session.exec(changelog_query).all()

    events: list[WorkItem] = []
    unmapped: set[str] = set()
    for row in changelog_rows:
        project = project_by_issue.get(row.issue_id)
        team_id = team_map.get(project or "")
        if team_id is None:
            unmapped.add(project or "<unknown project>")
            continue

        events.append(
            WorkItem(
                observed_at=row.created_date,
                source_system=SOURCE_SYSTEM,
                work_item_id=row.issue_id,
                team_id=team_id,
                status=row.to_value or "",
                status_changed_at=row.created_date,
            )
        )
    return Ingested(events=tuple(events), unmapped_scope_keys=frozenset(unmapped))
