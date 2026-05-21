"""Tests for aggregate and per-PR entities."""

from __future__ import annotations

from types import SimpleNamespace
import asyncio

from custom_components.azure_devops_tracker.binary_sensor import (
    HasActiveCommentsBinarySensor,
    HasFailedBuildBinarySensor,
    HasNewCommentBinarySensor,
    HasReadyPullRequestBinarySensor,
    async_setup_entry as async_setup_binary_entry,
)
from custom_components.azure_devops_tracker.models import CommentInfo, IdentityInfo, PolicyInfo, PullRequestInfo
from custom_components.azure_devops_tracker.event import AzureDevOpsTrackerProjectEvent
from custom_components.azure_devops_tracker.sensor import (
    AuthoredOpenPullRequestsSensor,
    ReviewedOpenPullRequestsSensor,
    async_setup_entry as async_setup_sensor_entry,
)


def _coordinator_for_pull_request(pull_request: PullRequestInfo):
    return SimpleNamespace(
        organization="org",
        project=SimpleNamespace(id="project-1", name="Project One"),
        get_pull_request=lambda pull_request_id: pull_request if pull_request.pull_request_id == pull_request_id else None,
    )


class _DynamicCoordinator(SimpleNamespace):
    def __init__(self, pull_requests):
        authored = [pr for pr in pull_requests if pr.is_authored_by_current_user]
        reviewed = [pr for pr in pull_requests if pr.is_reviewed_by_current_user]
        super().__init__(
            organization="org",
            project=SimpleNamespace(id="project-1", name="Project One"),
            data=SimpleNamespace(pull_requests=pull_requests),
            authored_pull_requests=authored,
            reviewed_pull_requests=reviewed,
            pull_requests_with_new_comments=[pr for pr in pull_requests if pr.has_new_comment],
            authored_pull_requests_with_new_comments=[pr for pr in authored if pr.has_new_comment],
            authored_pull_requests_with_active_comments=[pr for pr in authored if pr.has_active_comments],
            authored_ready_pull_requests=[pr for pr in authored if pr.ready_to_complete],
            reviewed_ready_pull_requests=[pr for pr in reviewed if pr.ready_to_complete],
            failed_builds=[],
            work_items_by_type={},
            work_items_by_state={},
            latest_new_comment=(pull_requests[0].latest_new_comment if pull_requests else None),
            async_add_listener=self.async_add_listener,
            async_add_event_listener=self.async_add_event_listener,
        )
        self._listeners = []
        self._event_listeners = []

    def async_add_listener(self, listener):
        self._listeners.append(listener)

        def remove_listener():
            self._listeners.remove(listener)

        return remove_listener

    def async_add_event_listener(self, listener):
        self._event_listeners.append(listener)

        def remove_listener():
            self._event_listeners.remove(listener)

        return remove_listener


class _FakeEntry(SimpleNamespace):
    def __init__(self, runtime_data):
        super().__init__(runtime_data=runtime_data)
        self.unload_callbacks = []

    def async_on_unload(self, callback):
        self.unload_callbacks.append(callback)


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
        is_authored_by_current_user=True,
        is_reviewed_by_current_user=False,
        latest_comment=latest_comment,
        latest_new_comment=latest_comment,
        active_comments=[latest_comment],
        active_comment_count=1,
        has_active_comments=True,
        new_comment_count=2,
        has_new_comment=True,
        build_failed=True,
        ready_to_complete=True,
        policies=[PolicyInfo(evaluation_id="eval-1", display_name="Build policy", status="rejected", is_blocking=True)],
    )


def test_authored_open_pull_requests_sensor_exposes_pr_details() -> None:
    """Aggregate authored PR sensor should expose structured PR details."""
    pull_request = _pull_request()
    sensor = AuthoredOpenPullRequestsSensor(_DynamicCoordinator([pull_request]))

    assert sensor.native_value == 1
    assert sensor.extra_state_attributes["pull_requests"][0]["title"] == "Handle null response path"
    assert sensor.extra_state_attributes["new_comment_count"] == 2


def test_reviewed_open_pull_requests_sensor_exposes_reviewed_items_only() -> None:
    """Reviewed PR sensor should exclude authored PRs."""
    authored = _pull_request()
    reviewed = _pull_request()
    reviewed.pull_request_id = 99
    reviewed.is_authored_by_current_user = False
    reviewed.is_reviewed_by_current_user = True
    reviewed.title = "Reviewed PR"

    sensor = ReviewedOpenPullRequestsSensor(_DynamicCoordinator([authored, reviewed]))

    assert sensor.native_value == 1
    assert sensor.extra_state_attributes["pull_requests"][0]["pull_request_id"] == 99


def test_aggregate_binary_sensors_reflect_authored_flags() -> None:
    """Aggregate binary sensors should mirror authored PR state and expose useful attributes."""
    pull_request = _pull_request()
    coordinator = _DynamicCoordinator([pull_request])

    new_comment = HasNewCommentBinarySensor(coordinator)
    active_comments = HasActiveCommentsBinarySensor(coordinator)
    build_failed = HasFailedBuildBinarySensor(coordinator)
    ready = HasReadyPullRequestBinarySensor(coordinator)

    assert new_comment.is_on is True
    assert new_comment.extra_state_attributes["latest_comment_text"] == "Please update the null handling."
    assert active_comments.is_on is True
    assert active_comments.extra_state_attributes["pull_request_count"] == 1
    assert build_failed.is_on is False
    assert ready.is_on is True
    assert ready.extra_state_attributes["pull_requests"][0]["source_ref_name"] == "refs/heads/feature/null-response"


def test_aggregate_active_comments_entities_reflect_matching_prs() -> None:
    """Aggregate authored sensor should expose active-comment details."""
    pull_request = _pull_request()
    coordinator = _DynamicCoordinator([pull_request])

    sensor = AuthoredOpenPullRequestsSensor(coordinator)
    binary_sensor = HasActiveCommentsBinarySensor(coordinator)

    assert sensor.native_value == 1
    assert sensor.extra_state_attributes["pull_requests"][0]["has_active_comments"] is True
    assert sensor.extra_state_attributes["active_comment_count"] == 1
    assert binary_sensor.is_on is True
    assert binary_sensor.extra_state_attributes["pull_request_count"] == 1


def test_dynamic_sensor_setup_adds_only_aggregate_entities() -> None:
    """Sensor setup should add only aggregate entities."""
    pull_request = _pull_request()
    coordinator = _DynamicCoordinator([pull_request])
    entry = _FakeEntry(coordinator)
    added_entities = []

    asyncio.run(async_setup_sensor_entry(None, entry, lambda entities: added_entities.extend(entities)))

    entity_names = {entity.name for entity in added_entities}
    assert "Authored open pull requests" in entity_names
    assert "Reviewed open pull requests" in entity_names
    assert "Failed builds" in entity_names
    assert "Active work items" in entity_names
    assert "Pipelines" in entity_names
    assert all(not name.startswith("PR 23") for name in entity_names)


def test_dynamic_binary_sensor_setup_adds_only_aggregate_entities() -> None:
    """Binary sensor setup should add only aggregate entities."""
    pull_request = _pull_request()
    coordinator = _DynamicCoordinator([pull_request])
    entry = _FakeEntry(coordinator)
    added_entities = []

    asyncio.run(async_setup_binary_entry(None, entry, lambda entities: added_entities.extend(entities)))

    entity_names = {entity.name for entity in added_entities}
    assert "Has new comment" in entity_names
    assert "Has active comments" in entity_names
    assert "Has failed build" in entity_names
    assert "Has ready pull request" in entity_names
    assert all(not name.startswith("PR 23") for name in entity_names)


def test_event_entity_forwards_matching_payloads() -> None:
    """Event entities should capture coordinator payloads for matching event types only."""
    pull_request = _pull_request()
    coordinator = _DynamicCoordinator([pull_request])
    entity = AzureDevOpsTrackerProjectEvent(
        coordinator,
        "azure_devops_new_pr_comment",
        "New PR comment",
        "mdi:comment-outline",
    )

    asyncio.run(entity.async_added_to_hass())

    payload = {"pull_request_id": 23, "text": "Please update the null handling."}
    for listener in coordinator._event_listeners:
        listener("azure_devops_new_pr_comment", payload)

    assert entity._last_event == ("azure_devops_new_pr_comment", payload)

    for listener in coordinator._event_listeners:
        listener("azure_devops_pr_build_failed", {"pull_request_id": 23})

    assert entity._last_event == ("azure_devops_new_pr_comment", payload)
