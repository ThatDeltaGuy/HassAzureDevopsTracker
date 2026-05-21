"""Binary sensor platform for Azure DevOps Tracker."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AzureDevOpsCoordinator, AzureDevOpsTrackerConfigEntry
from .entity import AzureDevOpsTrackerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AzureDevOpsTrackerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Azure DevOps Tracker binary sensors."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        HasNewCommentBinarySensor(coordinator),
        HasActiveCommentsBinarySensor(coordinator),
        HasFailedBuildBinarySensor(coordinator),
        HasReadyPullRequestBinarySensor(coordinator),
    ]
    async_add_entities(entities)


class AzureDevOpsTrackerBinarySensor(AzureDevOpsTrackerEntity, BinarySensorEntity):
    """Shared Azure DevOps Tracker binary sensor behavior."""

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return None


class HasNewCommentBinarySensor(AzureDevOpsTrackerBinarySensor):
    _attr_name = "Has new comment"
    _attr_icon = "mdi:comment-alert"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_has_new_comment"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.pull_requests_with_new_comments)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        latest_comment = self.coordinator.latest_new_comment
        return {
            "new_comment_count": sum(pr.new_comment_count for pr in self.coordinator.authored_pull_requests_with_new_comments),
            "pull_request_count": len(self.coordinator.pull_requests_with_new_comments),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.authored_pull_requests_with_new_comments],
            "latest_comment_author": latest_comment.author.display_name if latest_comment else None,
            "latest_comment_text": latest_comment.text if latest_comment else None,
            "latest_comment_timestamp": latest_comment.published_date if latest_comment else None,
            "latest_comment_thread_id": latest_comment.thread_id if latest_comment else None,
            "latest_comment_url": latest_comment.url if latest_comment else None,
            "latest_comment_file_path": latest_comment.file_path if latest_comment else None,
        }


class HasFailedBuildBinarySensor(AzureDevOpsTrackerBinarySensor):
    _attr_name = "Has failed build"
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_has_failed_build"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.failed_builds)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "failed_build_count": len(self.coordinator.failed_builds),
            "failed_builds": [build.as_dict() for build in self.coordinator.failed_builds],
        }


class HasActiveCommentsBinarySensor(AzureDevOpsTrackerBinarySensor):
    _attr_name = "Has active comments"
    _attr_icon = "mdi:comment-processing"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_has_active_comments"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.authored_pull_requests_with_active_comments)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "pull_request_count": len(self.coordinator.authored_pull_requests_with_active_comments),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.authored_pull_requests_with_active_comments],
        }


class HasReadyPullRequestBinarySensor(AzureDevOpsTrackerBinarySensor):
    _attr_name = "Has ready pull request"
    _attr_icon = "mdi:check-decagram"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_has_ready_pull_request"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.authored_ready_pull_requests)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "ready_pull_request_count": len(self.coordinator.authored_ready_pull_requests),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.authored_ready_pull_requests],
        }
