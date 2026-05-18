"""Azure DevOps Tracker integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import AzureDevOpsCoordinator, AzureDevOpsTrackerConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: AzureDevOpsTrackerConfigEntry) -> bool:
    """Set up Azure DevOps Tracker from a config entry."""
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
