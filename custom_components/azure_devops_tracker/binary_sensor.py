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
        HasNewCommentOnAuthoredPullRequestsBinarySensor(coordinator),
        HasNewCommentOnReviewedPullRequestsBinarySensor(coordinator),
        HasActiveCommentsOnAuthoredPullRequestsBinarySensor(coordinator),
        HasActiveCommentsOnReviewedPullRequestsBinarySensor(coordinator),
        HasFailedBuildOnAuthoredPullRequestsBinarySensor(coordinator),
        HasFailedBuildOnReviewedPullRequestsBinarySensor(coordinator),
        HasAuthoredPullRequestReadyToCompleteBinarySensor(coordinator),
        HasReviewedPullRequestReadyToCompleteBinarySensor(coordinator),
    ]
    async_add_entities(entities)


class AzureDevOpsTrackerBinarySensor(AzureDevOpsTrackerEntity, BinarySensorEntity):
    """Shared Azure DevOps Tracker binary sensor behavior."""

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return None


class HasNewCommentOnAuthoredPullRequestsBinarySensor(AzureDevOpsTrackerBinarySensor):
    _attr_name = "Has new comment on authored pull requests"
    _attr_icon = "mdi:comment-alert"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_has_new_comment_on_authored_pull_requests"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.authored_pull_requests_with_new_comments)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        latest_comment = self.coordinator.latest_authored_new_comment
        return {
            "new_comment_count": sum(pr.new_comment_count for pr in self.coordinator.authored_pull_requests_with_new_comments),
            "pull_request_count": len(self.coordinator.authored_pull_requests_with_new_comments),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.authored_pull_requests_with_new_comments],
            "latest_comment_author": latest_comment.author.display_name if latest_comment else None,
            "latest_comment_text": latest_comment.text if latest_comment else None,
            "latest_comment_timestamp": latest_comment.published_date if latest_comment else None,
            "latest_comment_thread_id": latest_comment.thread_id if latest_comment else None,
            "latest_comment_url": latest_comment.url if latest_comment else None,
            "latest_comment_file_path": latest_comment.file_path if latest_comment else None,
        }


class HasNewCommentOnReviewedPullRequestsBinarySensor(AzureDevOpsTrackerBinarySensor):
    _attr_name = "Has new comment on reviewed pull requests"
    _attr_icon = "mdi:comment-alert-outline"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_has_new_comment_on_reviewed_pull_requests"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.reviewed_pull_requests_with_new_comments)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        latest_comment = self.coordinator.latest_reviewed_new_comment
        return {
            "new_comment_count": sum(pr.new_comment_count for pr in self.coordinator.reviewed_pull_requests_with_new_comments),
            "pull_request_count": len(self.coordinator.reviewed_pull_requests_with_new_comments),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.reviewed_pull_requests_with_new_comments],
            "latest_comment_author": latest_comment.author.display_name if latest_comment else None,
            "latest_comment_text": latest_comment.text if latest_comment else None,
            "latest_comment_timestamp": latest_comment.published_date if latest_comment else None,
            "latest_comment_thread_id": latest_comment.thread_id if latest_comment else None,
            "latest_comment_url": latest_comment.url if latest_comment else None,
            "latest_comment_file_path": latest_comment.file_path if latest_comment else None,
        }


class HasFailedBuildOnAuthoredPullRequestsBinarySensor(AzureDevOpsTrackerBinarySensor):
    _attr_name = "Has failed build on authored pull requests"
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_has_failed_build_on_authored_pull_requests"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.authored_pull_requests_with_failed_builds)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "failed_build_count": len(self.coordinator.authored_pull_requests_with_failed_builds),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.authored_pull_requests_with_failed_builds],
        }


class HasFailedBuildOnReviewedPullRequestsBinarySensor(AzureDevOpsTrackerBinarySensor):
    _attr_name = "Has failed build on reviewed pull requests"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_has_failed_build_on_reviewed_pull_requests"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.reviewed_pull_requests_with_failed_builds)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "failed_build_count": len(self.coordinator.reviewed_pull_requests_with_failed_builds),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.reviewed_pull_requests_with_failed_builds],
        }


class HasActiveCommentsOnAuthoredPullRequestsBinarySensor(AzureDevOpsTrackerBinarySensor):
    _attr_name = "Has active comments on authored pull requests"
    _attr_icon = "mdi:comment-processing"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_has_active_comments_on_authored_pull_requests"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.authored_pull_requests_with_active_comments)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "pull_request_count": len(self.coordinator.authored_pull_requests_with_active_comments),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.authored_pull_requests_with_active_comments],
        }


class HasActiveCommentsOnReviewedPullRequestsBinarySensor(AzureDevOpsTrackerBinarySensor):
    _attr_name = "Has active comments on reviewed pull requests"
    _attr_icon = "mdi:comment-processing-outline"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_has_active_comments_on_reviewed_pull_requests"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.reviewed_pull_requests_with_active_comments)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "pull_request_count": len(self.coordinator.reviewed_pull_requests_with_active_comments),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.reviewed_pull_requests_with_active_comments],
        }


class HasAuthoredPullRequestReadyToCompleteBinarySensor(AzureDevOpsTrackerBinarySensor):
    _attr_name = "Has authored pull request ready to complete"
    _attr_icon = "mdi:check-decagram"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_has_authored_pull_request_ready_to_complete"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.authored_ready_pull_requests)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "ready_pull_request_count": len(self.coordinator.authored_ready_pull_requests),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.authored_ready_pull_requests],
        }


class HasReviewedPullRequestReadyToCompleteBinarySensor(AzureDevOpsTrackerBinarySensor):
    _attr_name = "Has reviewed pull request ready to complete"
    _attr_icon = "mdi:check-decagram-outline"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_has_reviewed_pull_request_ready_to_complete"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.reviewed_ready_pull_requests)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "ready_pull_request_count": len(self.coordinator.reviewed_ready_pull_requests),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.reviewed_ready_pull_requests],
        }
