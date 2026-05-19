"""Data models for Azure DevOps Tracker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class IdentityInfo:
    """Basic identity information."""

    id: str | None
    display_name: str | None
    unique_name: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return the identity as a serializable dict."""
        return {
            "id": self.id,
            "display_name": self.display_name,
            "unique_name": self.unique_name,
        }


@dataclass(slots=True)
class ProjectInfo:
    """Project info used in the config flow and runtime."""

    id: str
    name: str
    description: str | None
    url: str | None
    state: str | None
    visibility: str | None


@dataclass(slots=True)
class CommentInfo:
    """A user-visible pull request comment."""

    comment_id: int
    thread_id: int
    author: IdentityInfo
    text: str | None
    published_date: str | None
    url: str | None
    file_path: str | None
    is_reply: bool
    comment_type: str | None = None
    is_deleted: bool = False
    thread_status: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return the comment as a serializable dict."""
        return {
            "comment_id": self.comment_id,
            "thread_id": self.thread_id,
            "author_id": self.author.id,
            "author_name": self.author.display_name,
            "author_unique_name": self.author.unique_name,
            "text": self.text,
            "published_date": self.published_date,
            "url": self.url,
            "file_path": self.file_path,
            "is_reply": self.is_reply,
            "comment_type": self.comment_type,
            "is_deleted": self.is_deleted,
            "thread_status": self.thread_status,
        }


@dataclass(slots=True)
class PolicyInfo:
    """Policy evaluation info for a pull request."""

    evaluation_id: str
    display_name: str | None
    status: str | None
    is_blocking: bool

    def as_dict(self) -> dict[str, Any]:
        """Return the policy as a serializable dict."""
        return {
            "evaluation_id": self.evaluation_id,
            "display_name": self.display_name,
            "status": self.status,
            "is_blocking": self.is_blocking,
        }


@dataclass(slots=True)
class PullRequestInfo:
    """Pull request summary."""

    pull_request_id: int
    title: str
    status: str | None
    merge_status: str | None
    is_draft: bool
    url: str | None
    created_date: str | None
    source_ref_name: str | None
    target_ref_name: str | None
    repository_id: str | None
    repository_name: str | None
    author: IdentityInfo
    reviewers: list[IdentityInfo] = field(default_factory=list)
    policies: list[PolicyInfo] = field(default_factory=list)
    latest_comment: CommentInfo | None = None
    latest_unseen_comment: CommentInfo | None = None
    active_comments: list[CommentInfo] = field(default_factory=list)
    active_comment_count: int = 0
    has_active_comments: bool = False
    unseen_comment_count: int = 0
    has_new_comment: bool = False
    build_failed: bool = False
    ready_to_complete: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return the pull request as a serializable dict."""
        return {
            "pull_request_id": self.pull_request_id,
            "title": self.title,
            "status": self.status,
            "merge_status": self.merge_status,
            "is_draft": self.is_draft,
            "url": self.url,
            "created_date": self.created_date,
            "source_ref_name": self.source_ref_name,
            "target_ref_name": self.target_ref_name,
            "repository_id": self.repository_id,
            "repository_name": self.repository_name,
            "author_name": self.author.display_name,
            "author_unique_name": self.author.unique_name,
            "reviewers": [
                {
                    "id": reviewer.id,
                    "display_name": reviewer.display_name,
                    "unique_name": reviewer.unique_name,
                }
                for reviewer in self.reviewers
            ],
            "policies": [policy.as_dict() for policy in self.policies],
            "latest_comment": self.latest_comment.as_dict()
            if self.latest_comment
            else None,
            "latest_unseen_comment": self.latest_unseen_comment.as_dict()
            if self.latest_unseen_comment
            else None,
            "active_comments": [comment.as_dict() for comment in self.active_comments],
            "active_comment_count": self.active_comment_count,
            "has_active_comments": self.has_active_comments,
            "unseen_comment_count": self.unseen_comment_count,
            "has_new_comment": self.has_new_comment,
            "build_failed": self.build_failed,
            "ready_to_complete": self.ready_to_complete,
        }


@dataclass(slots=True)
class BuildInfo:
    """Build summary."""

    build_id: int
    definition_id: int | None
    definition_name: str | None
    build_number: str | None
    status: str | None
    result: str | None
    source_branch: str | None
    source_version: str | None
    queue_time: str | None
    start_time: str | None
    finish_time: str | None
    requested_for: str | None
    url: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return the build as a serializable dict."""
        return {
            "build_id": self.build_id,
            "definition_id": self.definition_id,
            "definition_name": self.definition_name,
            "build_number": self.build_number,
            "status": self.status,
            "result": self.result,
            "source_branch": self.source_branch,
            "source_version": self.source_version,
            "queue_time": self.queue_time,
            "start_time": self.start_time,
            "finish_time": self.finish_time,
            "requested_for": self.requested_for,
            "url": self.url,
        }


@dataclass(slots=True)
class PipelineInfo:
    """Pipeline definition summary."""

    definition_id: int
    name: str
    path: str | None
    queue_status: str | None
    url: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return the pipeline as a serializable dict."""
        return {
            "definition_id": self.definition_id,
            "name": self.name,
            "path": self.path,
            "queue_status": self.queue_status,
            "url": self.url,
        }


@dataclass(slots=True)
class WorkItemInfo:
    """Work item summary."""

    work_item_id: int
    title: str | None
    work_item_type: str | None
    state: str | None
    assigned_to: str | None
    changed_date: str | None
    url: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return the work item as a serializable dict."""
        return {
            "work_item_id": self.work_item_id,
            "title": self.title,
            "work_item_type": self.work_item_type,
            "state": self.state,
            "assigned_to": self.assigned_to,
            "changed_date": self.changed_date,
            "url": self.url,
        }


@dataclass(slots=True)
class CoordinatorData:
    """Data snapshot published by the coordinator."""

    organization: str
    project: ProjectInfo
    current_user: IdentityInfo | None
    pipelines: list[PipelineInfo] = field(default_factory=list)
    builds: list[BuildInfo] = field(default_factory=list)
    work_items: list[WorkItemInfo] = field(default_factory=list)
    pull_requests: list[PullRequestInfo] = field(default_factory=list)
