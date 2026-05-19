"""Config flow for Azure DevOps Tracker."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import AzureDevOpsAuthError, AzureDevOpsClient
from .const import (
    CONF_ORGANIZATION,
    CONF_PAT,
    CONF_PROJECT_ID,
    CONF_PROJECT_NAME,
    DEFAULT_ENABLE_BUILDS,
    DEFAULT_ENABLE_PR_POLICIES,
    DEFAULT_ENABLE_PULL_REQUEST_COMMENTS,
    DEFAULT_ENABLE_PULL_REQUESTS,
    DEFAULT_ENABLE_WORK_ITEMS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
    OPTION_ENABLE_BUILDS,
    OPTION_ENABLE_PR_POLICIES,
    OPTION_ENABLE_PULL_REQUEST_COMMENTS,
    OPTION_ENABLE_PULL_REQUESTS,
    OPTION_ENABLE_WORK_ITEMS,
    OPTION_SCAN_INTERVAL,
)
from .models import ProjectInfo
from .options_flow import AzureDevOpsTrackerOptionsFlow

CONF_REUSE_ENTRY = "reuse_entry"


class AzureDevOpsTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Azure DevOps Tracker config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        self._organization: str | None = None
        self._pat: str | None = None
        self._projects: list[ProjectInfo] = []

    def _existing_entries(self):
        """Return existing integration entries."""
        return list(self.hass.config_entries.async_entries(DOMAIN))

    def _get_reuse_entry(self, entry_id: str | None):
        """Return an existing entry selected for reuse."""
        if not entry_id:
            return None
        for entry in self._existing_entries():
            if entry.entry_id == entry_id:
                return entry
        return None

    def _user_step_schema(self) -> vol.Schema:
        """Build the first-step schema, including reuse options when available."""
        existing_entries = self._existing_entries()
        schema: dict[Any, Any] = {}

        if existing_entries:
            schema[
                vol.Optional(CONF_REUSE_ENTRY)
            ] = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": entry.entry_id, "label": entry.title}
                        for entry in existing_entries
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )

        default_organization = self._organization
        if default_organization is None and existing_entries:
            default_organization = existing_entries[0].data.get(CONF_ORGANIZATION, "")

        schema[
            vol.Required(CONF_ORGANIZATION, default=default_organization or "")
        ] = TextSelector()

        pat_key: Any = (
            vol.Optional(CONF_PAT)
            if existing_entries
            else vol.Required(CONF_PAT)
        )
        schema[pat_key] = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

        return vol.Schema(schema)

    def _get_project(self, project_id: str) -> ProjectInfo | None:
        """Return a configured project by id."""
        for project in self._projects:
            if project.id == project_id:
                return project
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Step 1: PAT and organization."""
        errors: dict[str, str] = {}
        if user_input is not None:
            reuse_entry = self._get_reuse_entry(user_input.get(CONF_REUSE_ENTRY))
            self._organization = user_input[CONF_ORGANIZATION].strip()
            entered_pat = user_input.get(CONF_PAT, "").strip()
            self._pat = entered_pat or (
                reuse_entry.data.get(CONF_PAT) if reuse_entry is not None else None
            )

            if not self._organization or not self._pat:
                errors["base"] = "required_field"
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._user_step_schema(),
                    errors=errors,
                )

            client = AzureDevOpsClient(async_get_clientsession(self.hass), self._pat)
            try:
                await client.validate_organization(self._organization)
                self._projects = await client.list_projects(self._organization)
            except AzureDevOpsAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"

            if not errors and not self._projects:
                errors["base"] = "no_projects"

            if not errors:
                return await self.async_step_project()

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_step_schema(),
            errors=errors,
        )

    async def async_step_project(self, user_input: dict[str, Any] | None = None):
        """Step 2: project selection and feature toggles."""
        errors: dict[str, str] = {}
        if user_input is not None:
            project_id = user_input[CONF_PROJECT_ID]
            project = self._get_project(project_id)
            if project is None:
                errors["base"] = "project_not_found"
            else:
                await self.async_set_unique_id(f"{self._organization}_{project.id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{self._organization}/{project.name}",
                    data={
                        CONF_ORGANIZATION: self._organization,
                        CONF_PROJECT_ID: project.id,
                        CONF_PROJECT_NAME: project.name,
                        CONF_PAT: self._pat,
                    },
                    options={
                        OPTION_ENABLE_BUILDS: user_input[OPTION_ENABLE_BUILDS],
                        OPTION_ENABLE_WORK_ITEMS: user_input[OPTION_ENABLE_WORK_ITEMS],
                        OPTION_ENABLE_PULL_REQUESTS: user_input[OPTION_ENABLE_PULL_REQUESTS],
                        OPTION_ENABLE_PULL_REQUEST_COMMENTS: user_input[OPTION_ENABLE_PULL_REQUEST_COMMENTS],
                        OPTION_ENABLE_PR_POLICIES: user_input[OPTION_ENABLE_PR_POLICIES],
                        OPTION_SCAN_INTERVAL: min(
                            MAX_SCAN_INTERVAL_SECONDS,
                            max(MIN_SCAN_INTERVAL_SECONDS, int(user_input[OPTION_SCAN_INTERVAL])),
                        ),
                    },
                )

        project_options = [
            {"value": project.id, "label": project.name}
            for project in sorted(self._projects, key=lambda item: item.name.casefold())
        ]
        return self.async_show_form(
            step_id="project",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROJECT_ID): SelectSelector(
                        SelectSelectorConfig(options=project_options, mode=SelectSelectorMode.DROPDOWN)
                    ),
                    vol.Required(OPTION_ENABLE_BUILDS, default=DEFAULT_ENABLE_BUILDS): BooleanSelector(),
                    vol.Required(OPTION_ENABLE_WORK_ITEMS, default=DEFAULT_ENABLE_WORK_ITEMS): BooleanSelector(),
                    vol.Required(OPTION_ENABLE_PULL_REQUESTS, default=DEFAULT_ENABLE_PULL_REQUESTS): BooleanSelector(),
                    vol.Required(
                        OPTION_ENABLE_PULL_REQUEST_COMMENTS,
                        default=DEFAULT_ENABLE_PULL_REQUEST_COMMENTS,
                    ): BooleanSelector(),
                    vol.Required(OPTION_ENABLE_PR_POLICIES, default=DEFAULT_ENABLE_PR_POLICIES): BooleanSelector(),
                    vol.Required(OPTION_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_SECONDS): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL_SECONDS,
                            max=MAX_SCAN_INTERVAL_SECONDS,
                            step=30,
                            mode="box",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create the options flow."""
        return AzureDevOpsTrackerOptionsFlow(config_entry)
