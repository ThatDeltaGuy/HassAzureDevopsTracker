"""Event entities for Azure DevOps Tracker."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    EVENT_AUTHORED_PR_BUILD_FAILED,
    EVENT_AUTHORED_PR_READY_TO_COMPLETE,
    EVENT_NEW_AUTHORED_PR_COMMENT,
    EVENT_NEW_PULL_REQUEST_PUBLISHED,
    EVENT_NEW_REVIEWED_PR_COMMENT,
    EVENT_REVIEWED_PR_BUILD_FAILED,
    EVENT_REVIEWED_PR_READY_TO_COMPLETE,
)
from .coordinator import AzureDevOpsTrackerConfigEntry
from .entity import AzureDevOpsTrackerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AzureDevOpsTrackerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Azure DevOps Tracker event entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            AzureDevOpsTrackerProjectEvent(coordinator, EVENT_NEW_PULL_REQUEST_PUBLISHED, "New pull request published", "mdi:source-pull"),
            AzureDevOpsTrackerProjectEvent(coordinator, EVENT_NEW_AUTHORED_PR_COMMENT, "New comment on authored pull requests", "mdi:comment-outline"),
            AzureDevOpsTrackerProjectEvent(coordinator, EVENT_NEW_REVIEWED_PR_COMMENT, "New comment on reviewed pull requests", "mdi:comment-outline"),
            AzureDevOpsTrackerProjectEvent(coordinator, EVENT_AUTHORED_PR_BUILD_FAILED, "Failed build on authored pull requests", "mdi:alert-circle-outline"),
            AzureDevOpsTrackerProjectEvent(coordinator, EVENT_REVIEWED_PR_BUILD_FAILED, "Failed build on reviewed pull requests", "mdi:alert-circle-outline"),
            AzureDevOpsTrackerProjectEvent(coordinator, EVENT_AUTHORED_PR_READY_TO_COMPLETE, "Authored pull request ready to complete", "mdi:check-circle-outline"),
            AzureDevOpsTrackerProjectEvent(coordinator, EVENT_REVIEWED_PR_READY_TO_COMPLETE, "Reviewed pull request ready to complete", "mdi:check-circle-outline"),
        ]
    )


class AzureDevOpsTrackerProjectEvent(AzureDevOpsTrackerEntity, EventEntity):
    """Project event entity that mirrors coordinator transitions."""

    def __init__(self, coordinator, event_type: str, name: str, icon: str) -> None:
        super().__init__(coordinator)
        self._event_type = event_type
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{coordinator.project.id}_event_{event_type}"
        self._attr_event_types = [event_type]
        self._remove_listener = None

    async def async_added_to_hass(self) -> None:
        """Register for coordinator events."""
        await super().async_added_to_hass()

        @callback
        def _handle_event(event_type: str, payload: dict) -> None:
            if event_type != self._event_type:
                return
            self._trigger_event(event_type, payload)
            self.async_write_ha_state()

        self._remove_listener = self.coordinator.async_add_event_listener(_handle_event)

    async def async_will_remove_from_hass(self) -> None:
        """Remove the event listener."""
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
