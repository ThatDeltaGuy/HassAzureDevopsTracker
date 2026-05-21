"""Tests for Azure DevOps Tracker coordinator logic."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from custom_components.azure_devops_tracker.const import HUMAN_COMMENT_TYPE
from custom_components.azure_devops_tracker.coordinator import AzureDevOpsCoordinator
from custom_components.azure_devops_tracker.models import CommentInfo, CoordinatorData, IdentityInfo, PolicyInfo, ProjectInfo, PullRequestInfo


class _FakeStore:
    def __init__(self) -> None:
        self.saved = None

    async def async_save(self, data):
        self.saved = data


def _comment(
    comment_id: int,
    *,
    author_id: str,
    author_name: str,
    text: str | None,
    published_date: str,
    comment_type: str = HUMAN_COMMENT_TYPE,
    is_deleted: bool = False,
) -> CommentInfo:
    return CommentInfo(
        comment_id=comment_id,
        thread_id=100 + comment_id,
        author=IdentityInfo(id=author_id, display_name=author_name, unique_name=f"{author_name}@example.com"),
        text=text,
        published_date=published_date,
        url=None,
        file_path="/file.cs",
        is_reply=False,
        comment_type=comment_type,
        is_deleted=is_deleted,
    )


def _pull_request(pr_id: int, *, has_new_comment: bool = False, build_failed: bool = False, ready: bool = False, latest_new_comment: CommentInfo | None = None, new_count: int = 0) -> PullRequestInfo:
    return PullRequestInfo(
        pull_request_id=pr_id,
        title=f"PR {pr_id}",
        status="active",
        merge_status="succeeded",
        is_draft=False,
        url=f"https://example/pr/{pr_id}",
        created_date="2026-05-18T10:00:00Z",
        source_ref_name="refs/heads/feature",
        target_ref_name="refs/heads/main",
        repository_id="repo-1",
        repository_name="Repo",
        author=IdentityInfo(id="author-1", display_name="Author", unique_name="author@example.com"),
        is_authored_by_current_user=True,
        is_reviewed_by_current_user=False,
        latest_new_comment=latest_new_comment,
        has_new_comment=has_new_comment,
        new_comment_count=new_count,
        build_failed=build_failed,
        ready_to_complete=ready,
        policies=[
            PolicyInfo(
                evaluation_id="eval-1",
                display_name="Build policy",
                status="rejected" if build_failed else "approved",
                is_blocking=True,
            )
        ],
    )


def test_classify_comments_ignores_deleted_system_and_own_comments() -> None:
    """Only unseen human comments from other users should count."""
    coordinator = object.__new__(AzureDevOpsCoordinator)
    coordinator._seen_state = {}

    own_comment = _comment(
        1,
        author_id="me",
        author_name="Me",
        text="internal note",
        published_date="2026-05-18T10:00:00Z",
    )
    system_comment = _comment(
        2,
        author_id="svc",
        author_name="System",
        text="build updated",
        published_date="2026-05-18T10:01:00Z",
        comment_type="system",
    )
    deleted_comment = _comment(
        3,
        author_id="user-2",
        author_name="Reviewer",
        text="old comment",
        published_date="2026-05-18T10:02:00Z",
        is_deleted=True,
    )
    unseen_comment = _comment(
        4,
        author_id="user-3",
        author_name="Reviewer Two",
        text="Please fix the null case",
        published_date="2026-05-18T10:03:00Z",
    )

    latest_comment, latest_new, new_count = AzureDevOpsCoordinator._classify_comments(
        coordinator,
        [own_comment, system_comment, deleted_comment, unseen_comment],
        {"me"},
        bootstrap=False,
        pr_key="42",
        bootstrap_cutoff=None,
        now=datetime(2026, 5, 18, 10, 5, tzinfo=timezone.utc),
    )

    assert latest_comment == unseen_comment
    assert latest_new == unseen_comment
    assert new_count == 1
    assert set(coordinator._seen_state["comments"]["42"].keys()) == {"4"}


def test_classify_comments_bootstrap_marks_existing_comments_as_seen() -> None:
    """Initial load should not produce a notification storm."""
    coordinator = object.__new__(AzureDevOpsCoordinator)
    coordinator._seen_state = {}

    bootstrap_comment = _comment(
        7,
        author_id="user-7",
        author_name="Reviewer",
        text="Existing comment",
        published_date="2026-05-18T09:00:00Z",
    )

    _latest_comment, latest_new, new_count = AzureDevOpsCoordinator._classify_comments(
        coordinator,
        [bootstrap_comment],
        {"me"},
        bootstrap=True,
        pr_key="101",
        bootstrap_cutoff=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
        now=datetime(2026, 5, 18, 10, 5, tzinfo=timezone.utc),
    )

    assert latest_new is None
    assert new_count == 0
    assert "7" in coordinator._seen_state["comments"]["101"]


def test_classify_comments_bootstrap_keeps_comments_new_if_after_entry_creation() -> None:
    """Comments newer than the entry creation time should remain unseen on first success."""
    coordinator = object.__new__(AzureDevOpsCoordinator)
    coordinator._seen_state = {}

    new_comment = _comment(
        8,
        author_id="user-8",
        author_name="Reviewer",
        text="New comment after setup",
        published_date="2026-05-18T10:30:00Z",
    )

    _latest_comment, latest_new, new_count = AzureDevOpsCoordinator._classify_comments(
        coordinator,
        [new_comment],
        {"me"},
        bootstrap=True,
        pr_key="102",
        bootstrap_cutoff=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
        now=datetime(2026, 5, 18, 10, 31, tzinfo=timezone.utc),
    )

    assert latest_new == new_comment
    assert new_count == 1
    assert "8" in coordinator._seen_state["comments"]["102"]


def test_classify_comments_keeps_new_comments_for_fifteen_minutes() -> None:
    """Detected comments should remain new for 15 minutes after first detection."""
    coordinator = object.__new__(AzureDevOpsCoordinator)
    coordinator._seen_state = {"comments": {"103": {"9": "2026-05-18T10:00:00+00:00"}}}

    comment = _comment(
        9,
        author_id="user-9",
        author_name="Reviewer",
        text="Still new",
        published_date="2026-05-18T09:59:00Z",
    )

    _latest_comment, latest_new, new_count = AzureDevOpsCoordinator._classify_comments(
        coordinator,
        [comment],
        {"me"},
        bootstrap=False,
        pr_key="103",
        bootstrap_cutoff=None,
        now=datetime(2026, 5, 18, 10, 10, tzinfo=timezone.utc),
    )

    assert latest_new == comment
    assert new_count == 1


def test_classify_comments_expires_new_comments_after_fifteen_minutes() -> None:
    """Detected comments should stop being new after 15 minutes."""
    coordinator = object.__new__(AzureDevOpsCoordinator)
    coordinator._seen_state = {"comments": {"104": {"10": "2026-05-18T10:00:00+00:00"}}}

    comment = _comment(
        10,
        author_id="user-10",
        author_name="Reviewer",
        text="No longer new",
        published_date="2026-05-18T09:59:00Z",
    )

    _latest_comment, latest_new, new_count = AzureDevOpsCoordinator._classify_comments(
        coordinator,
        [comment],
        {"me"},
        bootstrap=False,
        pr_key="104",
        bootstrap_cutoff=None,
        now=datetime(2026, 5, 18, 10, 16, tzinfo=timezone.utc),
    )

    assert latest_new is None
    assert new_count == 0


def test_identity_matches_by_id_and_unique_name() -> None:
    """Identity matching should support both id and unique name fallbacks."""
    by_id = IdentityInfo(id="abc", display_name="Alex", unique_name=None)
    by_name = IdentityInfo(id=None, display_name="Alex", unique_name="alex@example.com")
    by_display_name = IdentityInfo(id=None, display_name="Alex Lund", unique_name=None)
    by_email_alias = IdentityInfo(id=None, display_name=None, unique_name="alex.lund@eatechnology.com")

    assert AzureDevOpsCoordinator._identity_matches(by_id, {"abc"}) is True
    assert (
        AzureDevOpsCoordinator._identity_matches(by_name, {"alex"})
        is True
    )
    assert (
        AzureDevOpsCoordinator._identity_matches(by_display_name, {"alexlund"})
        is True
    )
    assert (
        AzureDevOpsCoordinator._identity_matches(by_email_alias, {"alexlund"})
        is True
    )
    assert (
        AzureDevOpsCoordinator._identity_matches(by_name, {"other"})
        is False
    )


def test_get_pull_request_returns_matching_item() -> None:
    """Lookup by PR id should return the current PR object."""
    coordinator = object.__new__(AzureDevOpsCoordinator)
    coordinator.data = CoordinatorData(
        organization="org",
        project=ProjectInfo(id="project-1", name="Project", description=None, url=None, state=None, visibility=None),
        current_user=None,
        pull_requests=[_pull_request(10), _pull_request(20)],
    )

    result = AzureDevOpsCoordinator.get_pull_request(coordinator, 20)

    assert result is not None
    assert result.pull_request_id == 20


def test_process_transitions_emits_expected_events() -> None:
    """Transition processing should emit one event per newly triggered condition."""
    latest_comment = _comment(
        11,
        author_id="reviewer-1",
        author_name="Reviewer",
        text="Looks good after the fix",
        published_date="2026-05-18T11:00:00Z",
    )
    pull_request = _pull_request(
        77,
        has_new_comment=True,
        build_failed=True,
        ready=True,
        latest_new_comment=latest_comment,
        new_count=1,
    )
    data = CoordinatorData(
        organization="org",
        project=ProjectInfo(id="project-1", name="Project", description=None, url=None, state=None, visibility=None),
        current_user=None,
        pull_requests=[pull_request],
    )

    events: list[tuple[str, dict]] = []
    coordinator = object.__new__(AzureDevOpsCoordinator)
    coordinator._seen_state = {}
    coordinator._initialized = True
    coordinator.store = _FakeStore()
    coordinator._dispatch_event = lambda event_type, payload: events.append((event_type, payload))

    asyncio.run(AzureDevOpsCoordinator._process_transitions(coordinator, data))

    event_types = [event_type for event_type, _payload in events]
    assert event_types == [
        "azure_devops_new_comment_on_authored_pull_requests",
        "azure_devops_failed_build_on_authored_pull_requests",
        "azure_devops_authored_pull_request_ready_to_complete",
    ]
    new_comment_payload = events[0][1]
    assert new_comment_payload["pull_request_id"] == 77
    assert new_comment_payload["author_name"] == "Reviewer"
    assert new_comment_payload["text"] == "Looks good after the fix"
    assert new_comment_payload["repository_name"] == "Repo"

    build_failed_payload = events[1][1]
    assert build_failed_payload["policies"][0]["display_name"] == "Build policy"

    ready_payload = events[2][1]
    assert ready_payload["source_ref_name"] == "refs/heads/feature"
    assert ready_payload["target_ref_name"] == "refs/heads/main"
    assert coordinator.store.saved is not None
    assert coordinator._seen_state["pr_build_failed"]["77"] is True
    assert coordinator._seen_state["pr_ready"]["77"] is True


def test_active_comments_only_include_text_comments_from_active_threads() -> None:
    """Active comments should exclude fixed/system/deleted thread comments."""
    active_text = _comment(
        20,
        author_id="reviewer-1",
        author_name="Reviewer",
        text="Please revisit this logic.",
        published_date="2026-05-18T12:00:00Z",
    )
    active_text.thread_status = "active"

    fixed_text = _comment(
        21,
        author_id="reviewer-2",
        author_name="Reviewer Two",
        text="This was already addressed.",
        published_date="2026-05-18T12:05:00Z",
    )
    fixed_text.thread_status = "fixed"

    system_active = _comment(
        22,
        author_id="svc",
        author_name="System",
        text="Merge status changed",
        published_date="2026-05-18T12:10:00Z",
        comment_type="system",
    )
    system_active.thread_status = "active"

    active_comments = AzureDevOpsCoordinator._active_comments(
        [active_text, fixed_text, system_active]
    )

    assert active_comments == [active_text]
