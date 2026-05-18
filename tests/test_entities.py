"""Tests for aggregate and per-PR entities."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.azure_devops_tracker.binary_sensor import (
    PullRequestBuildFailedBinarySensor,
    PullRequestHasNewCommentBinarySensor,
    PullRequestReadyToCompleteBinarySensor,
)
from custom_components.azure_devops_tracker.models import CommentInfo, IdentityInfo, PolicyInfo, PullRequestInfo
from custom_components.azure_devops_tracker.sensor import (
    PullRequestStateSensor,
    PullRequestUnseenCommentCountSensor,
)


def _coordinator_for_pull_request(pull_request: PullRequestInfo):
    return SimpleNamespace(
        organization="org",
        project=SimpleNamespace(id="project-1", name="Project One"),
        get_pull_request=lambda pull_request_id: pull_request if pull_request.pull_request_id == pull_request_id else None,
    )


def _pull_request() -> PullRequestInfo:
    latest_comment = CommentInfo(
        comment_id=5,
        thread_id=55,
        author=IdentityInfo(id="reviewer-1", display_name="Reviewer", unique_name="reviewer@example.com"),
        text="Please update the null handling.",
        published_date="2026-05-18T12:00:00Z",
        url=None,
        file_path="/src/service.cs",
        is_reply=False,
        comment_type="text",
        is_deleted=False,
    )
    return PullRequestInfo(
        pull_request_id=23,
        title="Handle null response path",
        status="active",
        merge_status="succeeded",
        is_draft=False,
        url="https://example/pr/23",
        created_date="2026-05-18T10:00:00Z",
        source_ref_name="refs/heads/feature/null-response",
        target_ref_name="refs/heads/main",
        repository_id="repo-1",
        repository_name="Main Repo",
        author=IdentityInfo(id="author-1", display_name="Author", unique_name="author@example.com"),
        latest_comment=latest_comment,
        latest_unseen_comment=latest_comment,
        unseen_comment_count=2,
        has_new_comment=True,
        build_failed=True,
        ready_to_complete=True,
        policies=[PolicyInfo(evaluation_id="eval-1", display_name="Build policy", status="rejected", is_blocking=True)],
    )


def test_pull_request_state_sensor_exposes_pr_details() -> None:
    """Per-PR state sensor should reflect the live PR model."""
    pull_request = _pull_request()
    sensor = PullRequestStateSensor(_coordinator_for_pull_request(pull_request), pull_request.pull_request_id)

    assert sensor.name == "PR 23 state"
    assert sensor.native_value == "active"
    assert sensor.extra_state_attributes["title"] == "Handle null response path"
    assert sensor.extra_state_attributes["latest_comment_text"] == "Please update the null handling."


def test_pull_request_unseen_comment_sensor_exposes_latest_comment() -> None:
    """Per-PR unseen comment sensor should expose comment details."""
    pull_request = _pull_request()
    sensor = PullRequestUnseenCommentCountSensor(_coordinator_for_pull_request(pull_request), pull_request.pull_request_id)

    assert sensor.name == "PR 23 unseen comments"
    assert sensor.native_value == 2
    assert sensor.extra_state_attributes["latest_comment_author"] == "Reviewer"
    assert sensor.extra_state_attributes["latest_comment_file_path"] == "/src/service.cs"


def test_pull_request_binary_sensors_reflect_flags() -> None:
    """Per-PR binary sensors should mirror the PR flags and expose useful attributes."""
    pull_request = _pull_request()
    coordinator = _coordinator_for_pull_request(pull_request)

    new_comment = PullRequestHasNewCommentBinarySensor(coordinator, pull_request.pull_request_id)
    build_failed = PullRequestBuildFailedBinarySensor(coordinator, pull_request.pull_request_id)
    ready = PullRequestReadyToCompleteBinarySensor(coordinator, pull_request.pull_request_id)

    assert new_comment.is_on is True
    assert new_comment.extra_state_attributes["latest_comment_text"] == "Please update the null handling."
    assert build_failed.is_on is True
    assert build_failed.extra_state_attributes["policies"][0]["display_name"] == "Build policy"
    assert ready.is_on is True
    assert ready.extra_state_attributes["source_ref_name"] == "refs/heads/feature/null-response"
