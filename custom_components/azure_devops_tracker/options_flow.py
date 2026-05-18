"""Options flow for Azure DevOps Tracker."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.helpers.selector import BooleanSelector, NumberSelector, NumberSelectorConfig

from .const import (
    DEFAULT_ENABLE_BUILDS,
    DEFAULT_ENABLE_PR_POLICIES,
    DEFAULT_ENABLE_PULL_REQUEST_COMMENTS,
    DEFAULT_ENABLE_PULL_REQUESTS,
    DEFAULT_ENABLE_WORK_ITEMS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
    OPTION_ENABLE_BUILDS,
    OPTION_ENABLE_PR_POLICIES,
    OPTION_ENABLE_PULL_REQUEST_COMMENTS,
    OPTION_ENABLE_PULL_REQUESTS,
    OPTION_ENABLE_WORK_ITEMS,
    OPTION_SCAN_INTERVAL,
)


class AzureDevOpsTrackerOptionsFlow(OptionsFlow):
    """Manage Azure DevOps Tracker options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Handle the options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    OPTION_ENABLE_BUILDS,
                    default=options.get(OPTION_ENABLE_BUILDS, DEFAULT_ENABLE_BUILDS),
                ): BooleanSelector(),
                vol.Required(
                    OPTION_ENABLE_WORK_ITEMS,
                    default=options.get(OPTION_ENABLE_WORK_ITEMS, DEFAULT_ENABLE_WORK_ITEMS),
                ): BooleanSelector(),
                vol.Required(
                    OPTION_ENABLE_PULL_REQUESTS,
                    default=options.get(OPTION_ENABLE_PULL_REQUESTS, DEFAULT_ENABLE_PULL_REQUESTS),
                ): BooleanSelector(),
                vol.Required(
                    OPTION_ENABLE_PULL_REQUEST_COMMENTS,
                    default=options.get(
                        OPTION_ENABLE_PULL_REQUEST_COMMENTS,
                        DEFAULT_ENABLE_PULL_REQUEST_COMMENTS,
                    ),
                ): BooleanSelector(),
                vol.Required(
                    OPTION_ENABLE_PR_POLICIES,
                    default=options.get(OPTION_ENABLE_PR_POLICIES, DEFAULT_ENABLE_PR_POLICIES),
                ): BooleanSelector(),
                vol.Required(
                    OPTION_SCAN_INTERVAL,
                    default=options.get(OPTION_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL_SECONDS,
                        max=MAX_SCAN_INTERVAL_SECONDS,
                        step=30,
                        mode="box",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
