"""Azure DevOps Tracker integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import PLATFORMS
from .coordinator import AzureDevOpsCoordinator, AzureDevOpsTrackerConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: AzureDevOpsTrackerConfigEntry) -> bool:
    """Set up Azure DevOps Tracker from a config entry."""
    await _async_cleanup_legacy_pull_request_entities(hass, entry)
    coordinator = AzureDevOpsCoordinator(hass, entry)
    await coordinator.async_load_seen_state()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_cleanup_legacy_pull_request_entities(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove old per-PR entities created by earlier versions."""
    entity_registry = er.async_get(hass)
    prefixes = (
        f"{entry.data['project_id']}_pull_request_",
    )
    for entity_entry in list(entity_registry.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id:
            continue
        unique_id = entity_entry.unique_id or ""
        if any(unique_id.startswith(prefix) for prefix in prefixes):
            entity_registry.async_remove(entity_entry.entity_id)
