"""Tests for the Azure DevOps Tracker config flow."""

from __future__ import annotations

from types import SimpleNamespace

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


def test_user_step_rejects_blank_credentials() -> None:
    """Blank org or PAT should not attempt API access."""
    flow = AzureDevOpsTrackerConfigFlow()
    flow.hass = SimpleNamespace()

    result = __import__("asyncio").run(
        flow.async_step_user({CONF_ORGANIZATION: "  ", CONF_PAT: "   "})
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "required_field"}


def test_project_step_rejects_unknown_project_id() -> None:
    """The selected project id should be validated before entry creation."""
    flow = AzureDevOpsTrackerConfigFlow()
    flow._organization = "org"
    flow._pat = "pat"
    flow._projects = [
        ProjectInfo(id="project-1", name="Project One", description=None, url=None, state=None, visibility=None)
    ]

    result = __import__("asyncio").run(
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
    flow._projects = [
        ProjectInfo(id="project-1", name="Project One", description=None, url=None, state=None, visibility=None)
    ]

    low_result = __import__("asyncio").run(
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
    high_result = __import__("asyncio").run(
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
