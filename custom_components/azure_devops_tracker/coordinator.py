"""Coordinator for Azure DevOps Tracker."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AzureDevOpsApiError, AzureDevOpsAuthError, AzureDevOpsClient
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
    EVENT_NEW_PR_COMMENT,
    EVENT_PR_BUILD_FAILED,
    EVENT_PR_READY_TO_COMPLETE,
    HUMAN_COMMENT_TYPE,
    OPTION_ENABLE_BUILDS,
    OPTION_ENABLE_PR_POLICIES,
    OPTION_ENABLE_PULL_REQUEST_COMMENTS,
    OPTION_ENABLE_PULL_REQUESTS,
    OPTION_ENABLE_WORK_ITEMS,
    OPTION_SCAN_INTERVAL,
    STORE_KEY,
    STORE_VERSION,
)
from .models import CommentInfo, CoordinatorData, IdentityInfo, ProjectInfo, PullRequestInfo

_LOGGER = logging.getLogger(__name__)

type AzureDevOpsTrackerConfigEntry = ConfigEntry["AzureDevOpsCoordinator"]


class AzureDevOpsCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Central data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: AzureDevOpsTrackerConfigEntry) -> None:
        self.entry = entry
        self.organization = entry.data[CONF_ORGANIZATION]
        self.project = ProjectInfo(
            id=entry.data[CONF_PROJECT_ID],
            name=entry.data[CONF_PROJECT_NAME],
            description=None,
            url=None,
            state=None,
            visibility=None,
        )
        self.client = AzureDevOpsClient(async_get_clientsession(hass), entry.data[CONF_PAT])
        self.store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, f"{STORE_KEY}_{entry.entry_id}")
        self._seen_state: dict[str, Any] = {}
        self._initialized = False
        self._event_listeners: set[Callable[[str, dict[str, Any]], None]] = set()

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.scan_interval_seconds),
        )

    @property
    def scan_interval_seconds(self) -> int:
        """Return the configured poll interval."""
        return int(self.entry.options.get(OPTION_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS))

    @property
    def enable_builds(self) -> bool:
        return bool(self.entry.options.get(OPTION_ENABLE_BUILDS, DEFAULT_ENABLE_BUILDS))

    @property
    def enable_work_items(self) -> bool:
        return bool(self.entry.options.get(OPTION_ENABLE_WORK_ITEMS, DEFAULT_ENABLE_WORK_ITEMS))

    @property
    def enable_pull_requests(self) -> bool:
        return bool(self.entry.options.get(OPTION_ENABLE_PULL_REQUESTS, DEFAULT_ENABLE_PULL_REQUESTS))

    @property
    def enable_pr_comments(self) -> bool:
        return bool(
            self.entry.options.get(
                OPTION_ENABLE_PULL_REQUEST_COMMENTS,
                DEFAULT_ENABLE_PULL_REQUEST_COMMENTS,
            )
        )

    @property
    def enable_pr_policies(self) -> bool:
        return bool(self.entry.options.get(OPTION_ENABLE_PR_POLICIES, DEFAULT_ENABLE_PR_POLICIES))

    async def async_load_seen_state(self) -> None:
        """Load stored seen-state once before the first refresh."""
        self._seen_state = await self.store.async_load() or {}

    @callback
    def async_add_event_listener(
        self, listener: Callable[[str, dict[str, Any]], None]
    ) -> Callable[[], None]:
        """Register an in-memory event listener."""
        self._event_listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._event_listeners.discard(listener)

        return remove_listener

    @callback
    def _dispatch_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Send an event to Home Assistant and local event entities."""
        self.hass.bus.async_fire(event_type, payload)
        for listener in tuple(self._event_listeners):
            listener(event_type, payload)

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch a full project snapshot."""
        try:
            _LOGGER.debug(
                "Starting Azure DevOps refresh for organization='%s' configured_project='%s' options={builds=%s, work_items=%s, prs=%s, comments=%s, policies=%s}",
                self.organization,
                self.project.name,
                self.enable_builds,
                self.enable_work_items,
                self.enable_pull_requests,
                self.enable_pr_comments,
                self.enable_pr_policies,
            )
            current_user = await self.client.get_current_user(self.organization)
            project = await self._resolve_project()

            pipelines = await self.client.list_pipelines(self.organization, project.name) if self.enable_builds else []
            builds = await self.client.list_builds(self.organization, project.name) if self.enable_builds else []
            work_items = await self.client.list_work_items(self.organization, project.name) if self.enable_work_items else []
            pull_requests = await self._load_pull_requests(current_user, project)

            data = CoordinatorData(
                organization=self.organization,
                project=project,
                current_user=current_user,
                pipelines=pipelines,
                builds=builds,
                work_items=work_items,
                pull_requests=pull_requests,
            )

            await self._process_transitions(data)
            self.update_interval = timedelta(seconds=self.scan_interval_seconds)
            _LOGGER.debug(
                "Completed Azure DevOps refresh for project '%s': pipelines=%s builds=%s work_items=%s matched_prs=%s",
                project.name,
                len(pipelines),
                len(builds),
                len(work_items),
                len(pull_requests),
            )
            return data
        except AzureDevOpsAuthError as err:
            _LOGGER.debug(
                "Azure DevOps authentication failed during refresh for organization='%s' project='%s': %s",
                self.organization,
                self.project.name,
                err,
            )
            raise ConfigEntryAuthFailed from err
        except AzureDevOpsApiError as err:
            _LOGGER.debug(
                "Azure DevOps API failure during refresh for organization='%s' project='%s': %s",
                self.organization,
                self.project.name,
                err,
            )
            raise UpdateFailed(str(err)) from err

    async def _resolve_project(self) -> ProjectInfo:
        """Resolve the configured project info from the API."""
        projects = await self.client.list_projects(self.organization)
        for project in projects:
            if project.id == self.project.id:
                self.project = project
                _LOGGER.debug("Resolved configured Azure DevOps project: %s", project)
                return project

        raise UpdateFailed(f"Configured project {self.project.id} is no longer visible")

    async def _load_pull_requests(
        self,
        current_user: IdentityInfo,
        project: ProjectInfo,
    ) -> list[PullRequestInfo]:
        """Load and enrich relevant pull requests."""
        if not self.enable_pull_requests:
            return []

        pull_requests = await self.client.list_pull_requests(self.organization, project.name)
        relevant_prs: list[PullRequestInfo] = []

        current_user_id = current_user.id.casefold() if current_user.id else None
        current_user_name = current_user.unique_name.casefold() if current_user.unique_name else None
        current_user_display_name = (
            current_user.display_name.casefold() if current_user.display_name else None
        )

        _LOGGER.debug(
            "Evaluating %s pull requests for project '%s' using current user %s",
            len(pull_requests),
            project.name,
            current_user.as_dict(),
        )

        for pr in pull_requests:
            is_author = self._identity_matches(
                pr.author,
                current_user_id,
                current_user_name,
                current_user_display_name,
            )
            is_reviewer = any(
                self._identity_matches(
                    reviewer,
                    current_user_id,
                    current_user_name,
                    current_user_display_name,
                )
                for reviewer in pr.reviewers
            )
            if not is_author and not is_reviewer:
                _LOGGER.debug(
                    "Skipping PR %s for current user; author=%s reviewers=%s",
                    pr.pull_request_id,
                    pr.author.as_dict(),
                    [reviewer.as_dict() for reviewer in pr.reviewers],
                )
                continue

            if self.enable_pr_comments and pr.repository_id:
                comments = await self.client.list_pull_request_comments(
                    self.organization,
                    project.name,
                    pr.repository_id,
                    pr.pull_request_id,
                )
                pr.latest_comment, pr.latest_unseen_comment, pr.unseen_comment_count = self._classify_comments(
                    comments,
                    current_user_id,
                    bootstrap=not self._initialized,
                    pr_key=str(pr.pull_request_id),
                )
                pr.has_new_comment = pr.latest_unseen_comment is not None

            if self.enable_pr_policies:
                pr.policies = await self.client.list_policy_evaluations(
                    self.organization,
                    project.name,
                    project.id,
                    pr.pull_request_id,
                )
                pr.build_failed = any(
                    policy.status in {"rejected", "broken"}
                    and (policy.display_name or "").lower().find("build") >= 0
                    for policy in pr.policies
                )
                blocking_policies = [policy for policy in pr.policies if policy.is_blocking]
                policies_ok = all(policy.status == "approved" for policy in blocking_policies)
                pr.ready_to_complete = (
                    pr.status == "active"
                    and not pr.is_draft
                    and pr.merge_status not in {"conflicts", "failure", "rejectedByPolicy"}
                    and not pr.build_failed
                    and policies_ok
                )

            relevant_prs.append(pr)

        _LOGGER.debug(
            "Matched %s pull requests for current user in project '%s'",
            len(relevant_prs),
            project.name,
        )

        return relevant_prs

    def _classify_comments(
        self,
        comments: list[CommentInfo],
        current_user_id: str | None,
        *,
        bootstrap: bool,
        pr_key: str,
    ) -> tuple[CommentInfo | None, CommentInfo | None, int]:
        """Return the latest comment and unseen human comment details."""
        sorted_comments = sorted(
            comments,
            key=lambda item: (item.published_date or "", item.comment_id),
        )
        latest_comment = sorted_comments[-1] if sorted_comments else None

        seen_comment_ids = set(self._seen_state.get("comments", {}).get(pr_key, []))
        if bootstrap and pr_key not in self._seen_state.get("comments", {}):
            seen_comment_ids = {
                comment.comment_id
                for comment in sorted_comments
                if comment.author.id and comment.author.id.casefold() != current_user_id
            }

        unseen_comments: list[CommentInfo] = []
        persisted_seen = set(seen_comment_ids)
        for comment in sorted_comments:
            if comment.is_deleted or comment.comment_type != HUMAN_COMMENT_TYPE:
                persisted_seen.add(comment.comment_id)
                continue
            if comment.author.id and comment.author.id.casefold() == current_user_id:
                persisted_seen.add(comment.comment_id)
                continue
            if not comment.text or comment.comment_id in seen_comment_ids:
                persisted_seen.add(comment.comment_id)
                continue
            unseen_comments.append(comment)
            persisted_seen.add(comment.comment_id)

        self._seen_state.setdefault("comments", {})[pr_key] = sorted(persisted_seen)
        latest_unseen = unseen_comments[-1] if unseen_comments else None
        return latest_comment, latest_unseen, len(unseen_comments)

    async def _process_transitions(self, data: CoordinatorData) -> None:
        """Persist seen state and emit transition events."""
        previous_build_failures: dict[str, bool] = self._seen_state.get("pr_build_failed", {})
        previous_ready: dict[str, bool] = self._seen_state.get("pr_ready", {})

        for pr in data.pull_requests:
            pr_key = str(pr.pull_request_id)
            if self._initialized and pr.latest_unseen_comment is not None:
                payload = {
                    "organization": data.organization,
                    "project_id": data.project.id,
                    "project_name": data.project.name,
                    "pull_request_id": pr.pull_request_id,
                    "pull_request_title": pr.title,
                    "pull_request_url": pr.url,
                    "repository_id": pr.repository_id,
                    "repository_name": pr.repository_name,
                    **pr.latest_unseen_comment.as_dict(),
                }
                self._dispatch_event(EVENT_NEW_PR_COMMENT, payload)

            if self._initialized and not previous_build_failures.get(pr_key, False) and pr.build_failed:
                self._dispatch_event(
                    EVENT_PR_BUILD_FAILED,
                    {
                        "organization": data.organization,
                        "project_name": data.project.name,
                        "pull_request_id": pr.pull_request_id,
                        "pull_request_title": pr.title,
                        "pull_request_url": pr.url,
                        "repository_name": pr.repository_name,
                        "policies": [policy.as_dict() for policy in pr.policies],
                    },
                )

            if self._initialized and not previous_ready.get(pr_key, False) and pr.ready_to_complete:
                self._dispatch_event(
                    EVENT_PR_READY_TO_COMPLETE,
                    {
                        "organization": data.organization,
                        "project_name": data.project.name,
                        "pull_request_id": pr.pull_request_id,
                        "pull_request_title": pr.title,
                        "pull_request_url": pr.url,
                        "repository_name": pr.repository_name,
                        "source_ref_name": pr.source_ref_name,
                        "target_ref_name": pr.target_ref_name,
                    },
                )

            self._seen_state.setdefault("pr_build_failed", {})[pr_key] = pr.build_failed
            self._seen_state.setdefault("pr_ready", {})[pr_key] = pr.ready_to_complete

        await self.store.async_save(self._seen_state)
        self._initialized = True

    @staticmethod
    def _identity_matches(
        identity: IdentityInfo,
        current_user_id: str | None,
        current_user_name: str | None,
        current_user_display_name: str | None,
    ) -> bool:
        """Return whether an identity matches the current user."""
        if identity.id and current_user_id and identity.id.casefold() == current_user_id:
            return True
        if identity.unique_name and current_user_name and identity.unique_name.casefold() == current_user_name:
            return True
        if (
            identity.display_name
            and current_user_display_name
            and identity.display_name.casefold() == current_user_display_name
        ):
            return True
        return False

    @property
    def pull_requests_with_new_comments(self) -> list[PullRequestInfo]:
        return [pr for pr in self.data.pull_requests if pr.has_new_comment]

    @property
    def ready_pull_requests(self) -> list[PullRequestInfo]:
        return [pr for pr in self.data.pull_requests if pr.ready_to_complete]

    @property
    def failed_builds(self) -> list[Any]:
        return [build for build in self.data.builds if build.result in {"failed", "partiallySucceeded"}]

    @property
    def work_items_by_type(self) -> dict[str, int]:
        counts = Counter(item.work_item_type or "Unknown" for item in self.data.work_items)
        return dict(counts)

    @property
    def work_items_by_state(self) -> dict[str, int]:
        counts = Counter(item.state or "Unknown" for item in self.data.work_items)
        return dict(counts)

    @property
    def latest_unseen_comment(self) -> CommentInfo | None:
        comments = [pr.latest_unseen_comment for pr in self.pull_requests_with_new_comments if pr.latest_unseen_comment]
        if not comments:
            return None
        return sorted(comments, key=lambda item: (item.published_date or "", item.comment_id))[-1]

    def get_pull_request(self, pull_request_id: int) -> PullRequestInfo | None:
        """Return a pull request by its id."""
        for pull_request in self.data.pull_requests:
            if pull_request.pull_request_id == pull_request_id:
                return pull_request
        return None
