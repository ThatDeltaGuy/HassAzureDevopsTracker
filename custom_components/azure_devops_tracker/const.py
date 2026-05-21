"""Constants for Azure DevOps Tracker."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "azure_devops_tracker"

CONF_ORGANIZATION = "organization"
CONF_PROJECT_ID = "project_id"
CONF_PROJECT_NAME = "project_name"
CONF_PAT = "personal_access_token"

OPTION_ENABLE_BUILDS = "enable_builds"
OPTION_ENABLE_WORK_ITEMS = "enable_work_items"
OPTION_ENABLE_PULL_REQUESTS = "enable_pull_requests"
OPTION_ENABLE_PULL_REQUEST_COMMENTS = "enable_pull_request_comments"
OPTION_ENABLE_PR_POLICIES = "enable_pr_policies"
OPTION_SCAN_INTERVAL = "scan_interval_seconds"

DEFAULT_ENABLE_BUILDS = True
DEFAULT_ENABLE_WORK_ITEMS = True
DEFAULT_ENABLE_PULL_REQUESTS = True
DEFAULT_ENABLE_PULL_REQUEST_COMMENTS = True
DEFAULT_ENABLE_PR_POLICIES = True
DEFAULT_SCAN_INTERVAL_SECONDS = 120

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.EVENT]

DEFAULT_SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS)
NEW_COMMENT_WINDOW = timedelta(minutes=15)
MIN_SCAN_INTERVAL_SECONDS = 30
MAX_SCAN_INTERVAL_SECONDS = 900

STORE_VERSION = 1
STORE_KEY = f"{DOMAIN}_seen_state"

EVENT_NEW_AUTHORED_PR_COMMENT = "azure_devops_new_comment_on_authored_pull_requests"
EVENT_NEW_REVIEWED_PR_COMMENT = "azure_devops_new_comment_on_reviewed_pull_requests"
EVENT_AUTHORED_PR_BUILD_FAILED = "azure_devops_failed_build_on_authored_pull_requests"
EVENT_REVIEWED_PR_BUILD_FAILED = "azure_devops_failed_build_on_reviewed_pull_requests"
EVENT_AUTHORED_PR_READY_TO_COMPLETE = "azure_devops_authored_pull_request_ready_to_complete"
EVENT_REVIEWED_PR_READY_TO_COMPLETE = "azure_devops_reviewed_pull_request_ready_to_complete"
EVENT_NEW_PULL_REQUEST_PUBLISHED = "azure_devops_new_pull_request_published"

HUMAN_COMMENT_TYPE = "text"

API_VERSION_CORE = "7.1"
API_VERSION_BUILD = "7.1"
API_VERSION_CONNECTION_DATA = "7.1-preview.1"
API_VERSION_GIT = "7.1"
API_VERSION_WIT = "7.1"
API_VERSION_POLICY = "7.1-preview.1"
API_VERSION_PROFILE = "7.1"
