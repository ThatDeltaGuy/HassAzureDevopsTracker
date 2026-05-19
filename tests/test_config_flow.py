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


def test_user_step_rejects_blank_credentials() -> None:
    """Blank org or PAT should not attempt API access."""
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: [])
    )

    result = asyncio.run(
        flow.async_step_user({CONF_ORGANIZATION: "  ", CONF_PAT: "   "})
    )

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

    result = asyncio.run(
        flow.async_step_user(
            {
                CONF_ORGANIZATION: "org-one",
                CONF_PAT: config_flow_module.PAT_REUSE_SENTINEL,
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
    """Selecting an existing organization should work without typing it again."""
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

    result = asyncio.run(
        flow.async_step_user(
            {
                config_flow_module.CONF_EXISTING_ORGANIZATION: "org-one",
                CONF_ORGANIZATION: "",
                CONF_PAT: config_flow_module.PAT_REUSE_SENTINEL,
                config_flow_module.CONF_REUSE_PERSONAL_ACCESS_TOKEN: "entry-1",
            }
        )
    )

    assert result["type"] == "form"
    assert result["step_id"] == "project"
    assert flow._organization == "org-one"
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
    flow._selected_existing_organization = "org-one"

    schema = flow._user_step_schema()
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

    schema = flow._user_step_schema()
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
    flow._selected_existing_organization = "org-one"
    flow._selected_reuse_entry = "entry-2"

    flow._user_step_schema()

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
    flow._selected_existing_organization = "org-one"
    flow._organization_input = "org-one"
    flow._selected_reuse_entry = "entry-1"
    flow._pat_input = ""

    result = asyncio.run(
        flow.async_step_user(
            {
                config_flow_module.CONF_EXISTING_ORGANIZATION: "org-one",
                CONF_ORGANIZATION: "org-one",
                CONF_PAT: "",
                config_flow_module.CONF_REUSE_PERSONAL_ACCESS_TOKEN: "",
            }
        )
    )

    assert result["type"] == "form"
    assert flow._organization_input == "org-one"
    assert flow._selected_reuse_entry == ""
    assert flow._pat_input == ""


def test_clearing_organization_context_clears_reuse_and_pat_input() -> None:
    """Clearing organization context should also clear PAT reuse state."""
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
                CONF_PAT: "",
                config_flow_module.CONF_REUSE_PERSONAL_ACCESS_TOKEN: "entry-1",
            }
        )
    )

    assert result["type"] == "form"
    assert flow._organization_input == ""
    assert flow._selected_reuse_entry == ""
    assert flow._pat_input == ""
