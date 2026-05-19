"""Sensor platform for Azure DevOps Tracker."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import AzureDevOpsCoordinator, AzureDevOpsTrackerConfigEntry
from .entity import AzureDevOpsTrackerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AzureDevOpsTrackerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Azure DevOps Tracker sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        OpenPullRequestCountSensor(coordinator),
        ReadyPullRequestCountSensor(coordinator),
        PullRequestsWithActiveCommentsSensor(coordinator),
        PullRequestsWithNewCommentsSensor(coordinator),
        FailedBuildCountSensor(coordinator),
        ActiveWorkItemCountSensor(coordinator),
        PipelineCountSensor(coordinator),
    ]
    async_add_entities(entities)

    known_pr_ids: set[int] = set()

    @callback
    def _sync_pull_request_entities() -> None:
        new_entities: list[SensorEntity] = []
        for pull_request in coordinator.data.pull_requests:
            if pull_request.pull_request_id in known_pr_ids:
                continue
            known_pr_ids.add(pull_request.pull_request_id)
            new_entities.extend(
                [
                    PullRequestStateSensor(coordinator, pull_request.pull_request_id),
                    PullRequestUnseenCommentCountSensor(coordinator, pull_request.pull_request_id),
                ]
            )
        if new_entities:
            async_add_entities(new_entities)

    _sync_pull_request_entities()
    entry.async_on_unload(coordinator.async_add_listener(_sync_pull_request_entities))


class AzureDevOpsTrackerSensor(AzureDevOpsTrackerEntity, SensorEntity):
    """Shared Azure DevOps Tracker sensor behavior."""

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return None


class OpenPullRequestCountSensor(AzureDevOpsTrackerSensor):
    _attr_name = "Open pull requests"
    _attr_icon = "mdi:source-pull"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_open_pull_request_count"

    @property
    def native_value(self) -> StateType:
        return len(self.coordinator.data.pull_requests)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "project_name": self.coordinator.project.name,
            "project_id": self.coordinator.project.id,
            "pull_requests": [pr.as_dict() for pr in self.coordinator.data.pull_requests],
        }


class ReadyPullRequestCountSensor(AzureDevOpsTrackerSensor):
    _attr_name = "Ready pull requests"
    _attr_icon = "mdi:check-decagram"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_ready_pull_request_count"

    @property
    def native_value(self) -> StateType:
        return len(self.coordinator.ready_pull_requests)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "ready_pull_requests": [pr.as_dict() for pr in self.coordinator.ready_pull_requests],
        }


class PullRequestsWithNewCommentsSensor(AzureDevOpsTrackerSensor):
    _attr_name = "Pull requests with new comments"
    _attr_icon = "mdi:comment-alert"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_pull_requests_with_new_comments"

    @property
    def native_value(self) -> StateType:
        return len(self.coordinator.pull_requests_with_new_comments)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        latest_comment = self.coordinator.latest_unseen_comment
        return {
            "pull_requests": [pr.as_dict() for pr in self.coordinator.pull_requests_with_new_comments],
            "latest_comment_author": latest_comment.author.display_name if latest_comment else None,
            "latest_comment_text": latest_comment.text if latest_comment else None,
            "latest_comment_timestamp": latest_comment.published_date if latest_comment else None,
            "latest_comment_thread_id": latest_comment.thread_id if latest_comment else None,
            "latest_comment_url": latest_comment.url if latest_comment else None,
        }


class PullRequestsWithActiveCommentsSensor(AzureDevOpsTrackerSensor):
    _attr_name = "Pull requests with active comments"
    _attr_icon = "mdi:comment-processing"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_pull_requests_with_active_comments"

    @property
    def native_value(self) -> StateType:
        return len(self.coordinator.pull_requests_with_active_comments)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "pull_requests": [pr.as_dict() for pr in self.coordinator.pull_requests_with_active_comments],
        }


class FailedBuildCountSensor(AzureDevOpsTrackerSensor):
    _attr_name = "Failed builds"
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_failed_build_count"

    @property
    def native_value(self) -> StateType:
        return len(self.coordinator.failed_builds)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "failed_builds": [build.as_dict() for build in self.coordinator.failed_builds],
        }


class ActiveWorkItemCountSensor(AzureDevOpsTrackerSensor):
    _attr_name = "Active work items"
    _attr_icon = "mdi:clipboard-list"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_active_work_item_count"

    @property
    def native_value(self) -> StateType:
        return len(self.coordinator.data.work_items)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "work_items_by_type": self.coordinator.work_items_by_type,
            "work_items_by_state": self.coordinator.work_items_by_state,
            "sample_work_items": [item.as_dict() for item in self.coordinator.data.work_items[:25]],
        }


class PipelineCountSensor(AzureDevOpsTrackerSensor):
    _attr_name = "Pipelines"
    _attr_icon = "mdi:source-branch"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_pipeline_count"

    @property
    def native_value(self) -> StateType:
        return len(self.coordinator.data.pipelines)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "pipelines": [pipeline.as_dict() for pipeline in self.coordinator.data.pipelines],
            "latest_builds": [build.as_dict() for build in self.coordinator.data.builds],
        }


class AzureDevOpsTrackerPullRequestSensor(AzureDevOpsTrackerSensor):
    """Base class for sensors representing a single pull request."""

    def __init__(self, coordinator: AzureDevOpsCoordinator, pull_request_id: int) -> None:
        super().__init__(coordinator)
        self.pull_request_id = pull_request_id

    @property
    def pull_request(self):
        """Return the live pull request model."""
        return self.coordinator.get_pull_request(self.pull_request_id)

    @property
    def available(self) -> bool:
        """Keep the entity available only while the PR is in scope."""
        return super().available and self.pull_request is not None


class PullRequestStateSensor(AzureDevOpsTrackerPullRequestSensor):
    """State sensor for a single pull request."""

    _attr_icon = "mdi:source-pull"

    def __init__(self, coordinator: AzureDevOpsCoordinator, pull_request_id: int) -> None:
        super().__init__(coordinator, pull_request_id)
        self._attr_unique_id = f"{coordinator.project.id}_pull_request_{pull_request_id}_state"

    @property
    def name(self) -> str:
        """Return a display name for the PR sensor."""
        pull_request = self.pull_request
        if pull_request is None:
            return f"Pull request {self.pull_request_id}"
        return f"PR {self.pull_request_id} state"

    @property
    def native_value(self) -> StateType:
        pull_request = self.pull_request
        if pull_request is None:
            return None
        return pull_request.status

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        pull_request = self.pull_request
        if pull_request is None:
            return {}
        latest_comment = pull_request.latest_unseen_comment or pull_request.latest_comment
        return {
            **pull_request.as_dict(),
            "latest_comment_author": latest_comment.author.display_name if latest_comment else None,
            "latest_comment_text": latest_comment.text if latest_comment else None,
            "latest_comment_timestamp": latest_comment.published_date if latest_comment else None,
        }


class PullRequestUnseenCommentCountSensor(AzureDevOpsTrackerPullRequestSensor):
    """Unseen comment count sensor for a single pull request."""

    _attr_icon = "mdi:comment-processing-outline"

    def __init__(self, coordinator: AzureDevOpsCoordinator, pull_request_id: int) -> None:
        super().__init__(coordinator, pull_request_id)
        self._attr_unique_id = (
            f"{coordinator.project.id}_pull_request_{pull_request_id}_unseen_comment_count"
        )

    @property
    def name(self) -> str:
        """Return a display name for the PR comment counter."""
        return f"PR {self.pull_request_id} unseen comments"

    @property
    def native_value(self) -> StateType:
        pull_request = self.pull_request
        if pull_request is None:
            return None
        return pull_request.unseen_comment_count

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        pull_request = self.pull_request
        if pull_request is None:
            return {}
        latest_comment = pull_request.latest_unseen_comment
        return {
            "pull_request_title": pull_request.title,
            "pull_request_url": pull_request.url,
            "repository_name": pull_request.repository_name,
            "latest_comment_author": latest_comment.author.display_name if latest_comment else None,
            "latest_comment_text": latest_comment.text if latest_comment else None,
            "latest_comment_timestamp": latest_comment.published_date if latest_comment else None,
            "latest_comment_thread_id": latest_comment.thread_id if latest_comment else None,
            "latest_comment_file_path": latest_comment.file_path if latest_comment else None,
        }
