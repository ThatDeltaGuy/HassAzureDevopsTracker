"""Tests for aggregate and per-PR entities."""

from __future__ import annotations

from types import SimpleNamespace
import asyncio

from custom_components.azure_devops_tracker.binary_sensor import (
    HasFailedBuildBinarySensor,
    HasNewCommentBinarySensor,
    HasReadyPullRequestBinarySensor,
    PullRequestBuildFailedBinarySensor,
    PullRequestHasNewCommentBinarySensor,
    PullRequestReadyToCompleteBinarySensor,
    async_setup_entry as async_setup_binary_entry,
)
from custom_components.azure_devops_tracker.models import CommentInfo, IdentityInfo, PolicyInfo, PullRequestInfo
from custom_components.azure_devops_tracker.event import AzureDevOpsTrackerProjectEvent
from custom_components.azure_devops_tracker.sensor import (
    PullRequestStateSensor,
    PullRequestUnseenCommentCountSensor,
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
        super().__init__(
            organization="org",
            project=SimpleNamespace(id="project-1", name="Project One"),
            data=SimpleNamespace(pull_requests=pull_requests),
            pull_requests_with_new_comments=[pr for pr in pull_requests if pr.has_new_comment],
            ready_pull_requests=[pr for pr in pull_requests if pr.ready_to_complete],
            failed_builds=[],
            work_items_by_type={},
            work_items_by_state={},
            latest_unseen_comment=(pull_requests[0].latest_unseen_comment if pull_requests else None),
            async_add_listener=self.async_add_listener,
            async_add_event_listener=self.async_add_event_listener,
            get_pull_request=lambda pull_request_id: next(
                (pr for pr in self.data.pull_requests if pr.pull_request_id == pull_request_id), None
            ),
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


def test_dynamic_sensor_setup_adds_aggregate_and_per_pr_entities() -> None:
    """Sensor setup should add aggregate entities and dynamic per-PR entities."""
    pull_request = _pull_request()
    coordinator = _DynamicCoordinator([pull_request])
    entry = _FakeEntry(coordinator)
    added_entities = []

    asyncio.run(async_setup_sensor_entry(None, entry, lambda entities: added_entities.extend(entities)))

    entity_names = {entity.name for entity in added_entities}
    assert "Open pull requests" in entity_names
    assert "PR 23 state" in entity_names
    assert "PR 23 unseen comments" in entity_names


def test_dynamic_binary_sensor_setup_adds_aggregate_and_per_pr_entities() -> None:
    """Binary sensor setup should add aggregate entities and dynamic per-PR entities."""
    pull_request = _pull_request()
    coordinator = _DynamicCoordinator([pull_request])
    entry = _FakeEntry(coordinator)
    added_entities = []

    asyncio.run(async_setup_binary_entry(None, entry, lambda entities: added_entities.extend(entities)))

    entity_names = {entity.name for entity in added_entities}
    assert "Has new comment" in entity_names
    assert "PR 23 has new comment" in entity_names
    assert "PR 23 build failed" in entity_names
    assert "PR 23 ready to complete" in entity_names


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
