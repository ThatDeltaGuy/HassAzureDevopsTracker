"""Base entity for Azure DevOps Tracker."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AzureDevOpsCoordinator


class AzureDevOpsTrackerEntity(CoordinatorEntity[AzureDevOpsCoordinator]):
    """Base class for Azure DevOps Tracker entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AzureDevOpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.organization, coordinator.project.id)},
            manufacturer=coordinator.organization,
            name=coordinator.project.name,
        )
