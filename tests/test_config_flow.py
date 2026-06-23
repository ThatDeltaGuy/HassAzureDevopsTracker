"""Tests for the Azure DevOps Tracker config flow."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import custom_components.azure_devops_tracker.config_flow as config_flow_module
from custom_components.azure_devops_tracker.config_flow import AzureDevOpsTrackerConfigFlow
from custom_components.azure_devops_tracker.const import (
    CONF_ORGANIZATION,
    CONF_PAT,
    CONF_PROJECT_ID,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
    OPTION_ENABLE_BUILDS,
    OPTION_ENABLE_PR_POLICIES,
    OPTION_ENABLE_PULL_REQUEST_COMMENTS,
    OPTION_ENABLE_PULL_REQUESTS,
    OPTION_ENABLE_WORK_ITEMS,
    OPTION_SCAN_INTERVAL,
)
from custom_components.azure_devops_tracker.models import ProjectInfo


class _FakeClient:
    def __init__(self, _session, pat: str) -> None:
        self.pat = pat

    async def validate_organization(self, organization: str) -> None:
        self.organization = organization

    async def list_projects(self, organization: str) -> list[ProjectInfo]:
        return [
            ProjectInfo(
                id="project-1",
                name="Project One",
                description=None,
                url=None,
                state=None,
                visibility=None,
            )
        ]


class _InvalidAuthClient(_FakeClient):
    async def validate_organization(self, organization: str) -> None:
        raise config_flow_module.AzureDevOpsAuthError


def test_user_step_rejects_blank_credentials() -> None:
    """Blank organization should not advance the flow."""
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [])
    )

    result = asyncio.run(
        flow.async_step_user({CONF_ORGANIZATION: "  ", CONF_PAT: "   "})
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "required_field"}


def test_credentials_step_rejects_blank_pat_without_reuse() -> None:
    """Blank PAT without a reuse selection should not advance the flow."""
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [])
    )
    flow._organization = "org"

    result = asyncio.run(flow.async_step_credentials({CONF_PAT: ""}))

    assert result["type"] == "form"
    assert result["errors"] == {"base": "required_field"}


def test_project_step_rejects_unknown_project_id() -> None:
    """The selected project id should be validated before entry creation."""
    flow = AzureDevOpsTrackerConfigFlow()
    flow._organization = "org"
    flow._pat = "pat"
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [])
    )
    flow._projects = [
        ProjectInfo(id="project-1", name="Project One", description=None, url=None, state=None, visibility=None)
    ]

    result = asyncio.run(
        flow.async_step_project(
            {
                CONF_PROJECT_ID: "missing-project",
                OPTION_ENABLE_BUILDS: True,
                OPTION_ENABLE_WORK_ITEMS: True,
                OPTION_ENABLE_PULL_REQUESTS: True,
                OPTION_ENABLE_PULL_REQUEST_COMMENTS: True,
                OPTION_ENABLE_PR_POLICIES: True,
                OPTION_SCAN_INTERVAL: 120,
            }
        )
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "project_not_found"}


def test_project_step_clamps_scan_interval() -> None:
    """The poll interval should be constrained to supported bounds."""
    flow = AzureDevOpsTrackerConfigFlow()
    flow._organization = "org"
    flow._pat = "pat"
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [])
    )
    flow._projects = [
        ProjectInfo(id="project-1", name="Project One", description=None, url=None, state=None, visibility=None)
    ]

    low_result = asyncio.run(
        flow.async_step_project(
            {
                CONF_PROJECT_ID: "project-1",
                OPTION_ENABLE_BUILDS: True,
                OPTION_ENABLE_WORK_ITEMS: True,
                OPTION_ENABLE_PULL_REQUESTS: True,
                OPTION_ENABLE_PULL_REQUEST_COMMENTS: True,
                OPTION_ENABLE_PR_POLICIES: True,
                OPTION_SCAN_INTERVAL: 1,
            }
        )
    )
    high_result = asyncio.run(
        flow.async_step_project(
            {
                CONF_PROJECT_ID: "project-1",
                OPTION_ENABLE_BUILDS: True,
                OPTION_ENABLE_WORK_ITEMS: True,
                OPTION_ENABLE_PULL_REQUESTS: True,
                OPTION_ENABLE_PULL_REQUEST_COMMENTS: True,
                OPTION_ENABLE_PR_POLICIES: True,
                OPTION_SCAN_INTERVAL: 99999,
            }
        )
    )

    assert low_result["type"] == "create_entry"
    assert low_result["options"][OPTION_SCAN_INTERVAL] == MIN_SCAN_INTERVAL_SECONDS
    assert high_result["options"][OPTION_SCAN_INTERVAL] == MAX_SCAN_INTERVAL_SECONDS


def test_user_step_reuses_pat_from_existing_entry(monkeypatch) -> None:
    """An existing entry PAT can be reused when the field is left blank."""
    monkeypatch.setattr(config_flow_module, "AzureDevOpsClient", _FakeClient)

    existing_entry = SimpleNamespace(
        entry_id="entry-1",
        title="org-one/Project One",
        data={
            CONF_ORGANIZATION: "org-one",
            CONF_PAT: "existing-pat",
        },
    )
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [existing_entry])
    )
    flow._organization = "org-one"
    flow._organization_from_existing = True

    result = asyncio.run(
        flow.async_step_credentials(
            {
                CONF_PAT: "",
                config_flow_module.CONF_REUSE_PERSONAL_ACCESS_TOKEN: "entry-1",
            }
        )
    )

    assert result["type"] == "form"
    assert result["step_id"] == "project"
    assert flow._pat == "existing-pat"


def test_user_step_does_not_prefill_organization_from_existing_entry() -> None:
    """Existing organizations should not prefill the organization text field automatically."""
    existing_entry = SimpleNamespace(
        entry_id="entry-1",
        title="org-one/Project One",
        data={CONF_ORGANIZATION: "org-one", CONF_PAT: "existing-pat"},
    )
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [existing_entry])
    )

    result = asyncio.run(flow.async_step_user())

    organization_key = next(
        key for key in result["data_schema"].schema if getattr(key, "schema", None) == CONF_ORGANIZATION
    )
    assert organization_key.default() == ""


def test_user_step_uses_existing_organization_when_text_input_blank(monkeypatch) -> None:
    """Selecting an existing organization should advance to the credentials step."""
    existing_entry = SimpleNamespace(
        entry_id="entry-1",
        title="org-one/Project One",
        data={CONF_ORGANIZATION: "org-one", CONF_PAT: "existing-pat"},
    )
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [existing_entry])
    )

    result = asyncio.run(
        flow.async_step_user(
            {
                config_flow_module.CONF_EXISTING_ORGANIZATION: "org-one",
                CONF_ORGANIZATION: "",
            }
        )
    )

    assert result["type"] == "form"
    assert result["step_id"] == "credentials"
    assert flow._organization == "org-one"
    assert flow._pat is None


def test_selecting_existing_organization_prefills_organization_input() -> None:
    """Choosing an existing organization should store it for the next step."""
    existing_entry = SimpleNamespace(
        entry_id="entry-1",
        title="org-one/Project One",
        data={CONF_ORGANIZATION: "org-one", CONF_PAT: "existing-pat"},
    )
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [existing_entry])
    )

    result = asyncio.run(
        flow.async_step_user(
            {
                config_flow_module.CONF_EXISTING_ORGANIZATION: "org-one",
                CONF_ORGANIZATION: "",
            }
        )
    )

    assert result["step_id"] == "credentials"
    assert flow._organization == "org-one"
    assert flow._organization_from_existing is True


def test_selecting_reuse_entry_prefills_pat_placeholder(monkeypatch) -> None:
    """Choosing a PAT reuse entry should allow reuse without typing a PAT."""
    monkeypatch.setattr(config_flow_module, "AzureDevOpsClient", _FakeClient)

    existing_entry = SimpleNamespace(
        entry_id="entry-1",
        title="org-one/Project One",
        data={CONF_ORGANIZATION: "org-one", CONF_PAT: "existing-pat"},
    )
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [existing_entry])
    )
    flow._organization = "org-one"
    flow._organization_from_existing = True

    result = asyncio.run(
        flow.async_step_credentials(
            {
                CONF_PAT: "",
                config_flow_module.CONF_REUSE_PERSONAL_ACCESS_TOKEN: "entry-1",
            }
        )
    )

    assert result["step_id"] == "project"
    assert flow._pat == "existing-pat"


def test_reuse_credentials_options_are_filtered_by_selected_organization() -> None:
    """Credential reuse options should only show entries for the selected organization."""
    existing_entries = [
        SimpleNamespace(
            entry_id="entry-1",
            title="org-one/Project One",
            data={CONF_ORGANIZATION: "org-one", CONF_PAT: "pat-1"},
        ),
        SimpleNamespace(
            entry_id="entry-2",
            title="org-two/Project Two",
            data={CONF_ORGANIZATION: "org-two", CONF_PAT: "pat-2"},
        ),
    ]
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: existing_entries)
    )
    flow._organization = "org-one"
    flow._organization_from_existing = True

    schema = flow._credentials_step_schema()
    reuse_key = next(
        key
        for key in schema.schema
        if getattr(key, "schema", None)
        == config_flow_module.CONF_REUSE_PERSONAL_ACCESS_TOKEN
    )
    reuse_selector = schema.schema[reuse_key]
    options = reuse_selector.config.kwargs["options"]

    assert options == [
        {"value": "", "label": ""},
        {"value": "entry-1", "label": "org-one/Project One"},
    ]


def test_reuse_credentials_options_are_empty_without_organization_context() -> None:
    """Without an organization context, the PAT reuse dropdown should be empty."""
    existing_entries = [
        SimpleNamespace(
            entry_id="entry-1",
            title="org-one/Project One",
            data={CONF_ORGANIZATION: "org-one", CONF_PAT: "pat-1"},
        )
    ]
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: existing_entries)
    )

    flow._organization_from_existing = True
    schema = flow._credentials_step_schema()
    reuse_key = next(
        key
        for key in schema.schema
        if getattr(key, "schema", None)
        == config_flow_module.CONF_REUSE_PERSONAL_ACCESS_TOKEN
    )
    reuse_selector = schema.schema[reuse_key]

    assert reuse_selector.config.kwargs["options"] == [{"value": "", "label": ""}]


def test_existing_organization_dropdown_includes_blank_option_first() -> None:
    """Existing organization selector should allow a blank choice for manual entry."""
    existing_entries = [
        SimpleNamespace(
            entry_id="entry-1",
            title="org-one/Project One",
            data={CONF_ORGANIZATION: "org-one", CONF_PAT: "pat-1"},
        )
    ]
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: existing_entries)
    )

    schema = flow._user_step_schema()
    org_key = next(
        key
        for key in schema.schema
        if getattr(key, "schema", None) == config_flow_module.CONF_EXISTING_ORGANIZATION
    )
    org_selector = schema.schema[org_key]

    assert org_selector.config.kwargs["options"][0] == {"value": "", "label": ""}


def test_reuse_selection_clears_when_organization_changes() -> None:
    """Changing organization context should clear an incompatible reuse selection."""
    existing_entries = [
        SimpleNamespace(
            entry_id="entry-1",
            title="org-one/Project One",
            data={CONF_ORGANIZATION: "org-one", CONF_PAT: "pat-1"},
        ),
        SimpleNamespace(
            entry_id="entry-2",
            title="org-two/Project Two",
            data={CONF_ORGANIZATION: "org-two", CONF_PAT: "pat-2"},
        ),
    ]
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: existing_entries)
    )
    flow._organization = "org-one"
    flow._selected_reuse_entry = "entry-2"

    flow._credentials_step_schema()

    assert flow._selected_reuse_entry == ""


def test_clearing_existing_organization_clears_text_input_default() -> None:
    """If an existing organization is cleared, the related text input should render blank."""
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [])
    )
    flow._organization_input = ""
    flow._selected_existing_organization = ""

    result = asyncio.run(flow.async_step_user({CONF_ORGANIZATION: "", CONF_PAT: ""}))

    organization_key = next(
        key for key in result["data_schema"].schema if getattr(key, "schema", None) == CONF_ORGANIZATION
    )
    assert organization_key.default() == ""


def test_clearing_reuse_credentials_only_clears_pat_input() -> None:
    """Clearing PAT reuse should not clear organization state."""
    existing_entry = SimpleNamespace(
        entry_id="entry-1",
        title="org-one/Project One",
        data={CONF_ORGANIZATION: "org-one", CONF_PAT: "existing-pat"},
    )
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [existing_entry])
    )
    flow._organization = "org-one"
    flow._organization_from_existing = True
    flow._selected_reuse_entry = "entry-1"
    flow._pat_input = "typed-pat"

    result = asyncio.run(
        flow.async_step_credentials(
            {
                CONF_PAT: "",
                config_flow_module.CONF_REUSE_PERSONAL_ACCESS_TOKEN: "",
            }
        )
    )

    assert result["type"] == "form"
    assert flow._organization == "org-one"
    assert flow._selected_reuse_entry == ""
    assert flow._pat_input == ""


def test_manual_organization_hides_reuse_dropdown_on_credentials_step() -> None:
    """Manually entered organizations should not offer PAT reuse dropdown options."""
    existing_entries = [
        SimpleNamespace(
            entry_id="entry-1",
            title="org-one/Project One",
            data={CONF_ORGANIZATION: "org-one", CONF_PAT: "pat-1"},
        )
    ]
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: existing_entries)
    )
    flow._organization = "org-manual"
    flow._organization_from_existing = False

    schema = flow._credentials_step_schema()

    assert all(
        getattr(key, "schema", None) != config_flow_module.CONF_REUSE_PERSONAL_ACCESS_TOKEN
        for key in schema.schema
    )


def test_first_entry_uses_single_step_with_pat(monkeypatch) -> None:
    """When no entries exist, the first step should accept PAT directly."""
    monkeypatch.setattr(config_flow_module, "AzureDevOpsClient", _FakeClient)
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [])
    )

    result = asyncio.run(
        flow.async_step_user(
            {
                CONF_ORGANIZATION: "org-one",
                CONF_PAT: "first-pat",
            }
        )
    )

    assert result["type"] == "form"
    assert result["step_id"] == "project"
    assert flow._pat == "first-pat"


def test_clearing_organization_context_clears_reuse_and_pat_input() -> None:
    """Clearing organization context should reset state before credentials step."""
    existing_entry = SimpleNamespace(
        entry_id="entry-1",
        title="org-one/Project One",
        data={CONF_ORGANIZATION: "org-one", CONF_PAT: "existing-pat"},
    )
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [existing_entry])
    )
    flow._selected_existing_organization = "org-one"
    flow._organization_input = "org-one"
    flow._selected_reuse_entry = "entry-1"
    flow._pat_input = "some-user-input"

    result = asyncio.run(
        flow.async_step_user(
            {
                config_flow_module.CONF_EXISTING_ORGANIZATION: "",
                CONF_ORGANIZATION: "",
            }
        )
    )

    assert result["type"] == "form"
    assert flow._organization_input == ""
    assert flow._selected_reuse_entry == ""
    assert flow._pat_input == ""


def test_reauth_confirm_updates_existing_entry(monkeypatch) -> None:
    """Reauth should update the existing entry PAT instead of creating a new entry."""
    monkeypatch.setattr(config_flow_module, "AzureDevOpsClient", _FakeClient)

    existing_entry = SimpleNamespace(
        entry_id="entry-1",
        title="org-one/Project One",
        unique_id="org-one_project-1",
        data={
            CONF_ORGANIZATION: "org-one",
            CONF_PROJECT_ID: "project-1",
            CONF_PAT: "expired-pat",
        },
    )
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [existing_entry])
    )
    flow._test_reauth_entry = existing_entry

    result = asyncio.run(flow.async_step_reauth_confirm({CONF_PAT: "fresh-pat"}))

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert result["entry"] is existing_entry
    assert result["data_updates"] == {CONF_PAT: "fresh-pat"}


def test_reauth_confirm_rejects_invalid_pat(monkeypatch) -> None:
    """Reauth should surface invalid_auth when the replacement PAT fails validation."""
    monkeypatch.setattr(config_flow_module, "AzureDevOpsClient", _InvalidAuthClient)

    existing_entry = SimpleNamespace(
        entry_id="entry-1",
        title="org-one/Project One",
        unique_id="org-one_project-1",
        data={
            CONF_ORGANIZATION: "org-one",
            CONF_PROJECT_ID: "project-1",
            CONF_PAT: "expired-pat",
        },
    )
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [existing_entry])
    )
    flow._test_reauth_entry = existing_entry

    result = asyncio.run(flow.async_step_reauth_confirm({CONF_PAT: "bad-pat"}))

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}


def test_reconfigure_updates_existing_entry_pat(monkeypatch) -> None:
    """Reconfigure should update the targeted entry PAT in place."""
    monkeypatch.setattr(config_flow_module, "AzureDevOpsClient", _FakeClient)

    existing_entry = SimpleNamespace(
        entry_id="entry-1",
        title="org-one/Project One",
        unique_id="org-one_project-1",
        data={
            CONF_ORGANIZATION: "org-one",
            CONF_PROJECT_ID: "project-1",
            CONF_PAT: "old-pat",
        },
    )
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [existing_entry])
    )
    flow._test_reconfigure_entry = existing_entry

    result = asyncio.run(flow.async_step_reconfigure({CONF_PAT: "rotated-pat"}))

    assert result["type"] == "abort"
    assert result["entry"] is existing_entry
    assert result["data_updates"] == {CONF_PAT: "rotated-pat"}


def test_reconfigure_rejects_blank_pat() -> None:
    """Reconfigure should require a replacement PAT."""
    existing_entry = SimpleNamespace(
        entry_id="entry-1",
        title="org-one/Project One",
        unique_id="org-one_project-1",
        data={
            CONF_ORGANIZATION: "org-one",
            CONF_PROJECT_ID: "project-1",
            CONF_PAT: "old-pat",
        },
    )
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [existing_entry])
    )
    flow._test_reconfigure_entry = existing_entry

    result = asyncio.run(flow.async_step_reconfigure({CONF_PAT: "   "}))

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "required_field"}
