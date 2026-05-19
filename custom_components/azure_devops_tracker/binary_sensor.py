"""Binary sensor platform for Azure DevOps Tracker."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
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

    known_pr_ids: set[int] = set()

    @callback
    def _sync_pull_request_entities() -> None:
        new_entities: list[BinarySensorEntity] = []
        for pull_request in coordinator.data.pull_requests:
            if pull_request.pull_request_id in known_pr_ids:
                continue
            known_pr_ids.add(pull_request.pull_request_id)
            new_entities.extend(
                [
                    PullRequestHasNewCommentBinarySensor(coordinator, pull_request.pull_request_id),
                    PullRequestHasActiveCommentsBinarySensor(coordinator, pull_request.pull_request_id),
                    PullRequestBuildFailedBinarySensor(coordinator, pull_request.pull_request_id),
                    PullRequestReadyToCompleteBinarySensor(coordinator, pull_request.pull_request_id),
                ]
            )
        if new_entities:
            async_add_entities(new_entities)

    _sync_pull_request_entities()
    entry.async_on_unload(coordinator.async_add_listener(_sync_pull_request_entities))


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
        latest_comment = self.coordinator.latest_unseen_comment
        return {
            "new_comment_count": sum(pr.unseen_comment_count for pr in self.coordinator.pull_requests_with_new_comments),
            "pull_request_count": len(self.coordinator.pull_requests_with_new_comments),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.pull_requests_with_new_comments],
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
        return bool(self.coordinator.pull_requests_with_active_comments)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "pull_request_count": len(self.coordinator.pull_requests_with_active_comments),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.pull_requests_with_active_comments],
        }


class HasReadyPullRequestBinarySensor(AzureDevOpsTrackerBinarySensor):
    _attr_name = "Has ready pull request"
    _attr_icon = "mdi:check-decagram"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_has_ready_pull_request"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.ready_pull_requests)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "ready_pull_request_count": len(self.coordinator.ready_pull_requests),
            "pull_requests": [pr.as_dict() for pr in self.coordinator.ready_pull_requests],
        }


class AzureDevOpsTrackerPullRequestBinarySensor(AzureDevOpsTrackerBinarySensor):
    """Base class for binary sensors representing a single pull request."""

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


class PullRequestHasNewCommentBinarySensor(AzureDevOpsTrackerPullRequestBinarySensor):
    """Per-PR new comment flag."""

    _attr_icon = "mdi:comment-alert-outline"

    def __init__(self, coordinator: AzureDevOpsCoordinator, pull_request_id: int) -> None:
        super().__init__(coordinator, pull_request_id)
        self._attr_unique_id = f"{coordinator.project.id}_pull_request_{pull_request_id}_has_new_comment"

    @property
    def name(self) -> str:
        return f"PR {self.pull_request_id} has new comment"

    @property
    def is_on(self) -> bool:
        pull_request = self.pull_request
        return bool(pull_request and pull_request.has_new_comment)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        pull_request = self.pull_request
        if pull_request is None:
            return {}
        latest_comment = pull_request.latest_unseen_comment
        return {
            "pull_request_title": pull_request.title,
            "pull_request_url": pull_request.url,
            "unseen_comment_count": pull_request.unseen_comment_count,
            "latest_comment_author": latest_comment.author.display_name if latest_comment else None,
            "latest_comment_text": latest_comment.text if latest_comment else None,
            "latest_comment_timestamp": latest_comment.published_date if latest_comment else None,
            "latest_comment_thread_id": latest_comment.thread_id if latest_comment else None,
            "latest_comment_file_path": latest_comment.file_path if latest_comment else None,
        }


class PullRequestBuildFailedBinarySensor(AzureDevOpsTrackerPullRequestBinarySensor):
    """Per-PR build failed flag."""

    _attr_icon = "mdi:alert-outline"

    def __init__(self, coordinator: AzureDevOpsCoordinator, pull_request_id: int) -> None:
        super().__init__(coordinator, pull_request_id)
        self._attr_unique_id = f"{coordinator.project.id}_pull_request_{pull_request_id}_build_failed"

    @property
    def name(self) -> str:
        return f"PR {self.pull_request_id} build failed"

    @property
    def is_on(self) -> bool:
        pull_request = self.pull_request
        return bool(pull_request and pull_request.build_failed)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        pull_request = self.pull_request
        if pull_request is None:
            return {}
        return {
            "pull_request_title": pull_request.title,
            "pull_request_url": pull_request.url,
            "repository_name": pull_request.repository_name,
            "policies": [policy.as_dict() for policy in pull_request.policies],
        }


class PullRequestHasActiveCommentsBinarySensor(AzureDevOpsTrackerPullRequestBinarySensor):
    """Per-PR active comments flag."""

    _attr_icon = "mdi:comment-processing-outline"

    def __init__(self, coordinator: AzureDevOpsCoordinator, pull_request_id: int) -> None:
        super().__init__(coordinator, pull_request_id)
        self._attr_unique_id = f"{coordinator.project.id}_pull_request_{pull_request_id}_has_active_comments"

    @property
    def name(self) -> str:
        return f"PR {self.pull_request_id} has active comments"

    @property
    def is_on(self) -> bool:
        pull_request = self.pull_request
        return bool(pull_request and pull_request.has_active_comments)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        pull_request = self.pull_request
        if pull_request is None:
            return {}
        return {
            "pull_request_title": pull_request.title,
            "pull_request_url": pull_request.url,
            "active_comment_count": pull_request.active_comment_count,
            "active_comments": [comment.as_dict() for comment in pull_request.active_comments],
        }


class PullRequestReadyToCompleteBinarySensor(AzureDevOpsTrackerPullRequestBinarySensor):
    """Per-PR ready-to-complete flag."""

    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, coordinator: AzureDevOpsCoordinator, pull_request_id: int) -> None:
        super().__init__(coordinator, pull_request_id)
        self._attr_unique_id = (
            f"{coordinator.project.id}_pull_request_{pull_request_id}_ready_to_complete"
        )

    @property
    def name(self) -> str:
        return f"PR {self.pull_request_id} ready to complete"

    @property
    def is_on(self) -> bool:
        pull_request = self.pull_request
        return bool(pull_request and pull_request.ready_to_complete)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        pull_request = self.pull_request
        if pull_request is None:
            return {}
        return {
            "pull_request_title": pull_request.title,
            "pull_request_url": pull_request.url,
            "source_ref_name": pull_request.source_ref_name,
            "target_ref_name": pull_request.target_ref_name,
            "merge_status": pull_request.merge_status,
            "policies": [policy.as_dict() for policy in pull_request.policies],
        }
