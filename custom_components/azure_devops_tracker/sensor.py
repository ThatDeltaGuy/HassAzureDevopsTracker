"""Sensor platform for Azure DevOps Tracker."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
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
        AuthoredOpenPullRequestsSensor(coordinator),
        ReviewedOpenPullRequestsSensor(coordinator),
        FailedBuildCountSensor(coordinator),
        ActiveWorkItemCountSensor(coordinator),
        PipelineCountSensor(coordinator),
    ]
    async_add_entities(entities)


class AzureDevOpsTrackerSensor(AzureDevOpsTrackerEntity, SensorEntity):
    """Shared Azure DevOps Tracker sensor behavior."""

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return None


class AuthoredOpenPullRequestsSensor(AzureDevOpsTrackerSensor):
    _attr_name = "Authored open pull requests"
    _attr_icon = "mdi:source-pull"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_authored_open_pull_request_count"

    @property
    def native_value(self) -> StateType:
        return len(self.coordinator.authored_pull_requests)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "project_name": self.coordinator.project.name,
            "project_id": self.coordinator.project.id,
            "pull_requests": [pr.as_dict() for pr in self.coordinator.authored_pull_requests],
            "pull_request_summary": [
                self._format_pull_request_summary(pr)
                for pr in self.coordinator.authored_pull_requests
            ],
            "new_comment_count": sum(pr.new_comment_count for pr in self.coordinator.authored_pull_requests),
            "active_comment_count": sum(pr.active_comment_count for pr in self.coordinator.authored_pull_requests),
            "ready_to_complete_count": len(self.coordinator.authored_ready_pull_requests),
            "failed_build_count": len([pr for pr in self.coordinator.authored_pull_requests if pr.build_failed]),
        }

    @staticmethod
    def _format_pull_request_summary(pr) -> str:
        return (
            f"PR {pr.pull_request_id} | {pr.title} | new: {pr.new_comment_count} | "
            f"active: {pr.active_comment_count} | ready: {'yes' if pr.ready_to_complete else 'no'} | "
            f"build failed: {'yes' if pr.build_failed else 'no'}"
        )

class ReviewedOpenPullRequestsSensor(AzureDevOpsTrackerSensor):
    _attr_name = "Reviewed open pull requests"
    _attr_icon = "mdi:account-eye"

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project.id}_reviewed_open_pull_request_count"

    @property
    def native_value(self) -> StateType:
        return len(self.coordinator.reviewed_pull_requests)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "project_name": self.coordinator.project.name,
            "project_id": self.coordinator.project.id,
            "pull_requests": [pr.as_dict() for pr in self.coordinator.reviewed_pull_requests],
            "pull_request_summary": [
                AuthoredOpenPullRequestsSensor._format_pull_request_summary(pr)
                for pr in self.coordinator.reviewed_pull_requests
            ],
            "new_comment_count": sum(pr.new_comment_count for pr in self.coordinator.reviewed_pull_requests),
            "active_comment_count": sum(pr.active_comment_count for pr in self.coordinator.reviewed_pull_requests),
            "ready_to_complete_count": len(self.coordinator.reviewed_ready_pull_requests),
            "failed_build_count": len([pr for pr in self.coordinator.reviewed_pull_requests if pr.build_failed]),
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
