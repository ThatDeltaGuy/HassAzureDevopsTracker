"""Diagnostics support for Azure DevOps Tracker."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_PAT
from .coordinator import AzureDevOpsTrackerConfigEntry

TO_REDACT = {CONF_PAT}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: AzureDevOpsTrackerConfigEntry,
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "project": {
            "id": coordinator.project.id,
            "name": coordinator.project.name,
            "description": coordinator.project.description,
            "url": coordinator.project.url,
            "state": coordinator.project.state,
            "visibility": coordinator.project.visibility,
        },
        "summary": {
            "pull_request_count": len(coordinator.data.pull_requests),
            "pipeline_count": len(coordinator.data.pipelines),
            "build_count": len(coordinator.data.builds),
            "work_item_count": len(coordinator.data.work_items),
            "ready_pull_request_count": len(coordinator.ready_pull_requests),
            "pull_requests_with_new_comments": len(coordinator.pull_requests_with_new_comments),
        },
    }
