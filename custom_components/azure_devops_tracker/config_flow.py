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

CONF_EXISTING_ORGANIZATION = "existing_organization"
CONF_REUSE_PERSONAL_ACCESS_TOKEN = "reuse_personal_access_token"


class AzureDevOpsTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Azure DevOps Tracker config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        self._organization: str | None = None
        self._pat: str | None = None
        self._projects: list[ProjectInfo] = []
        self._organization_input: str = ""
        self._selected_existing_organization: str = ""
        self._selected_reuse_entry: str = ""
        self._pat_input: str = ""
        self._organization_from_existing = False

    def _existing_entries(self):
        """Return existing integration entries."""
        return list(self.hass.config_entries.async_entries(DOMAIN))

    def _existing_organizations(self) -> list[str]:
        """Return unique organizations from existing entries."""
        organizations = {
            entry.data.get(CONF_ORGANIZATION)
            for entry in self._existing_entries()
            if entry.data.get(CONF_ORGANIZATION)
        }
        return sorted(organizations)

    def _entries_for_organization(self, organization: str | None) -> list[Any]:
        """Return existing entries matching the provided organization."""
        if not organization:
            return []
        normalized = organization.casefold()
        return [
            entry
            for entry in self._existing_entries()
            if (entry.data.get(CONF_ORGANIZATION) or "").casefold() == normalized
        ]

    def _get_reuse_entry(self, entry_id: str | None):
        """Return an existing entry selected for reuse."""
        if not entry_id:
            return None
        for entry in self._existing_entries():
            if entry.entry_id == entry_id:
                return entry
        return None

    def _user_step_schema(self) -> vol.Schema:
        """Build the first setup step schema."""
        existing_entries = self._existing_entries()
        existing_organizations = self._existing_organizations()
        schema: dict[Any, Any] = {}

        if existing_organizations:
            schema[
                vol.Optional(
                    CONF_EXISTING_ORGANIZATION,
                    default=self._selected_existing_organization or "",
                )
            ] = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": "", "label": ""},
                    ]
                    + [
                        {"value": organization, "label": organization}
                        for organization in existing_organizations
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )

        organization_key: Any = (
            vol.Optional(CONF_ORGANIZATION, default=self._organization_input)
            if existing_entries
            else vol.Required(CONF_ORGANIZATION, default=self._organization_input)
        )
        schema[organization_key] = TextSelector()

        if not existing_entries:
            schema[
                vol.Required(CONF_PAT, default=self._pat_input)
            ] = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

        return vol.Schema(schema)

    def _credentials_step_schema(self) -> vol.Schema:
        """Build the PAT selection schema for the chosen organization."""
        filtered_entries = self._entries_for_organization(self._organization)
        selected_reuse_entry = self._get_reuse_entry(self._selected_reuse_entry)
        if (
            selected_reuse_entry is not None
            and selected_reuse_entry not in filtered_entries
        ):
            self._selected_reuse_entry = ""

        schema: dict[Any, Any] = {}
        if self._organization_from_existing:
            schema[
                vol.Optional(
                    CONF_REUSE_PERSONAL_ACCESS_TOKEN,
                    default=self._selected_reuse_entry or "",
                )
            ] = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": "", "label": ""},
                    ]
                    + [
                        {"value": entry.entry_id, "label": entry.title}
                        for entry in filtered_entries
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        schema[
            vol.Optional(CONF_PAT, default=self._pat_input)
        ] = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
        return vol.Schema(schema)

    def _get_project(self, project_id: str) -> ProjectInfo | None:
        """Return a configured project by id."""
        for project in self._projects:
            if project.id == project_id:
                return project
        return None

    async def _async_validate_pat(
        self,
        organization: str,
        pat: str,
        *,
        required_project_id: str | None = None,
    ) -> str | None:
        """Validate a PAT and optionally confirm the configured project is visible."""
        client = AzureDevOpsClient(async_get_clientsession(self.hass), pat)
        try:
            await client.validate_organization(organization)
            self._projects = await client.list_projects(organization)
        except AzureDevOpsAuthError:
            return "invalid_auth"
        except Exception:
            return "cannot_connect"

        if not self._projects:
            return "no_projects"

        if required_project_id and self._get_project(required_project_id) is None:
            return "project_not_found"

        return None

    async def _async_update_existing_entry_pat(self, entry, pat: str):
        """Update the targeted config entry with a replacement PAT."""
        await self.async_set_unique_id(f"{entry.data[CONF_ORGANIZATION]}_{entry.data[CONF_PROJECT_ID]}")
        self._abort_if_unique_id_mismatch()
        return self.async_update_reload_and_abort(
            entry,
            data_updates={CONF_PAT: pat},
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Step 1: organization selection, or full setup when no entries exist."""
        errors: dict[str, str] = {}
        existing_entries = self._existing_entries()
        if user_input is not None:
            selected_organization = user_input.get(CONF_EXISTING_ORGANIZATION, "").strip()
            entered_organization = user_input.get(CONF_ORGANIZATION, "").strip()

            self._selected_existing_organization = selected_organization
            self._organization_from_existing = bool(selected_organization and not entered_organization)
            self._organization_input = entered_organization
            self._organization = entered_organization or selected_organization or None

            self._selected_reuse_entry = ""
            self._pat_input = ""
            self._pat = None

            if not self._organization:
                errors["base"] = "required_field"
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._user_step_schema(),
                    errors=errors,
                )

            if not existing_entries:
                entered_pat = user_input.get(CONF_PAT, "").strip()
                self._pat_input = entered_pat
                self._pat = entered_pat or None
                if not self._pat:
                    errors["base"] = "required_field"
                    return self.async_show_form(
                        step_id="user",
                        data_schema=self._user_step_schema(),
                        errors=errors,
                    )

                error = await self._async_validate_pat(self._organization, self._pat)
                if error:
                    errors["base"] = error

                if not errors:
                    return await self.async_step_project()

                return self.async_show_form(
                    step_id="user",
                    data_schema=self._user_step_schema(),
                    errors=errors,
                )

            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_step_schema(),
            errors=errors,
        )

    async def async_step_credentials(self, user_input: dict[str, Any] | None = None):
        """Step 2: PAT selection or reuse."""
        errors: dict[str, str] = {}
        if user_input is not None:
            selected_reuse_entry = user_input.get(CONF_REUSE_PERSONAL_ACCESS_TOKEN, "").strip()
            valid_reuse_entries = self._entries_for_organization(self._organization)
            if selected_reuse_entry and not any(
                entry.entry_id == selected_reuse_entry for entry in valid_reuse_entries
            ):
                selected_reuse_entry = ""

            self._selected_reuse_entry = selected_reuse_entry
            reuse_entry = self._get_reuse_entry(selected_reuse_entry)
            entered_pat = user_input.get(CONF_PAT, "").strip()
            self._pat_input = entered_pat
            self._pat = entered_pat or (
                reuse_entry.data.get(CONF_PAT) if reuse_entry is not None else None
            )

            if not self._pat:
                errors["base"] = "required_field"
                return self.async_show_form(
                    step_id="credentials",
                    data_schema=self._credentials_step_schema(),
                    errors=errors,
                )

            error = await self._async_validate_pat(self._organization, self._pat)
            if error:
                errors["base"] = error

            if not errors:
                return await self.async_step_project()

        return self.async_show_form(
            step_id="credentials",
            data_schema=self._credentials_step_schema(),
            errors=errors,
        )

    async def async_step_project(self, user_input: dict[str, Any] | None = None):
        """Step 3: project selection and feature toggles."""
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

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        """Start reauthentication for an existing config entry."""
        self._organization = entry_data[CONF_ORGANIZATION]
        self._pat = None
        self._pat_input = ""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        """Prompt for a replacement PAT after an auth failure."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            entered_pat = user_input.get(CONF_PAT, "").strip()
            self._pat_input = entered_pat
            if not entered_pat:
                errors["base"] = "required_field"
            else:
                error = await self._async_validate_pat(
                    entry.data[CONF_ORGANIZATION],
                    entered_pat,
                    required_project_id=entry.data[CONF_PROJECT_ID],
                )
                if error:
                    errors["base"] = error
                else:
                    return await self._async_update_existing_entry_pat(entry, entered_pat)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PAT, default=self._pat_input): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Allow manual PAT rotation for an existing config entry."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            entered_pat = user_input.get(CONF_PAT, "").strip()
            self._pat_input = entered_pat
            if not entered_pat:
                errors["base"] = "required_field"
            else:
                error = await self._async_validate_pat(
                    entry.data[CONF_ORGANIZATION],
                    entered_pat,
                    required_project_id=entry.data[CONF_PROJECT_ID],
                )
                if error:
                    errors["base"] = error
                else:
                    return await self._async_update_existing_entry_pat(entry, entered_pat)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PAT, default=self._pat_input): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create the options flow."""
        return AzureDevOpsTrackerOptionsFlow(config_entry)
