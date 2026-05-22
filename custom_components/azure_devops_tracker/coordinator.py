"""Coordinator for Azure DevOps Tracker."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import logging
import re
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
    EVENT_AUTHORED_PR_BUILD_FAILED,
    EVENT_AUTHORED_PR_READY_TO_COMPLETE,
    EVENT_NEW_AUTHORED_PR_COMMENT,
    EVENT_NEW_PULL_REQUEST_PUBLISHED,
    EVENT_NEW_REVIEWED_PR_COMMENT,
    EVENT_REVIEWED_PR_BUILD_FAILED,
    EVENT_REVIEWED_PR_READY_TO_COMPLETE,
    HUMAN_COMMENT_TYPE,
    NEW_COMMENT_WINDOW,
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
            pull_requests, external_pull_requests = await self._load_pull_requests(
                current_user, project
            )

            data = CoordinatorData(
                organization=self.organization,
                project=project,
                current_user=current_user,
                pipelines=pipelines,
                builds=builds,
                work_items=work_items,
                pull_requests=pull_requests,
                external_pull_requests=external_pull_requests,
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
    ) -> tuple[list[PullRequestInfo], list[PullRequestInfo]]:
        """Load and enrich relevant pull requests."""
        if not self.enable_pull_requests:
            return [], []

        pull_requests = await self.client.list_pull_requests(self.organization, project.name)
        relevant_prs: list[PullRequestInfo] = []
        external_prs: list[PullRequestInfo] = []

        current_user_aliases = self._identity_aliases(current_user)
        current_user_id = current_user.id.casefold() if current_user.id else None

        _LOGGER.debug(
            "Evaluating %s pull requests for project '%s' using current user %s",
            len(pull_requests),
            project.name,
            current_user.as_dict(),
        )

        for pr in pull_requests:
            is_author = self._identity_matches(
                pr.author,
                current_user_aliases,
            )
            is_reviewer = any(
                self._identity_matches(
                    reviewer,
                    current_user_aliases,
                )
                for reviewer in pr.reviewers
            )
            pr.is_authored_by_current_user = is_author
            pr.is_reviewed_by_current_user = is_reviewer and not is_author

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

            if not is_author:
                external_prs.append(pr)

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
                pr.latest_comment, pr.latest_new_comment, pr.new_comment_count = self._classify_comments(
                    comments,
                    current_user_aliases,
                    bootstrap=not self._initialized,
                    pr_key=self._pull_request_tracking_key(pr),
                    bootstrap_cutoff=self.entry.created_at,
                    now=datetime.now(timezone.utc),
                )
                pr.active_comments = self._active_comments(comments)
                pr.active_comment_count = len(pr.active_comments)
                pr.has_active_comments = pr.active_comment_count > 0
                pr.has_new_comment = pr.latest_new_comment is not None

            relevant_prs.append(pr)

        _LOGGER.debug(
            "Matched %s pull requests for current user in project '%s'",
            len(relevant_prs),
            project.name,
        )

        if pull_requests and not relevant_prs:
            _LOGGER.warning(
                "Azure DevOps returned %s active pull requests for project '%s' but none matched the resolved user identity. Current user=%s aliases=%s sample_prs=%s",
                len(pull_requests),
                project.name,
                current_user.as_dict(),
                sorted(current_user_aliases),
                [
                    {
                        "pull_request_id": pr.pull_request_id,
                        "author": pr.author.as_dict(),
                        "author_aliases": sorted(self._identity_aliases(pr.author)),
                        "reviewers": [reviewer.as_dict() for reviewer in pr.reviewers],
                    }
                    for pr in pull_requests[:5]
                ],
            )

        return relevant_prs, external_prs

    def _classify_comments(
        self,
        comments: list[CommentInfo],
        current_user_aliases: set[str],
        *,
        bootstrap: bool,
        pr_key: str,
        bootstrap_cutoff: datetime | None,
        now: datetime,
    ) -> tuple[CommentInfo | None, CommentInfo | None, int]:
        """Return the latest comment and new human comment details."""
        sorted_comments = sorted(
            comments,
            key=lambda item: (item.published_date or "", item.comment_id),
        )
        latest_comment = sorted_comments[-1] if sorted_comments else None

        stored_comments = self._seen_state.get("comments", {}).get(pr_key, {})
        tracked_comments = self._normalize_tracked_comments(stored_comments)
        if bootstrap and pr_key not in self._seen_state.get("comments", {}):
            tracked_comments = {
                self._comment_tracking_key(comment): self._bootstrap_seen_timestamp(
                    comment,
                    current_user_aliases,
                    bootstrap_cutoff,
                )
                for comment in sorted_comments
                if self._should_mark_seen_on_bootstrap(comment, current_user_aliases, bootstrap_cutoff)
            }

        new_comments: list[CommentInfo] = []
        for comment in sorted_comments:
            if comment.is_deleted or comment.comment_type != HUMAN_COMMENT_TYPE:
                _LOGGER.debug(
                    "Ignoring PR comment thread=%s comment=%s because deleted=%s type=%s",
                    comment.thread_id,
                    comment.comment_id,
                    comment.is_deleted,
                    comment.comment_type,
                )
                continue
            if self._identity_matches(comment.author, current_user_aliases):
                _LOGGER.debug(
                    "Ignoring PR comment thread=%s comment=%s because author matches current user: %s",
                    comment.thread_id,
                    comment.comment_id,
                    comment.author.as_dict(),
                )
                continue
            if not comment.text:
                _LOGGER.debug(
                    "Ignoring PR comment thread=%s comment=%s because it has no text",
                    comment.thread_id,
                    comment.comment_id,
                )
                continue
            comment_key = self._comment_tracking_key(comment)
            # Legacy stored state used plain comment ids, which are only unique
            # within a thread. Fall back once so existing entries migrate cleanly.
            detected_at = tracked_comments.get(comment_key) or tracked_comments.get(
                str(comment.comment_id)
            )
            if detected_at is None:
                detected_at = now.isoformat()
                _LOGGER.debug(
                    "Detected new PR comment for pr_key=%s thread=%s comment=%s at %s",
                    pr_key,
                    comment.thread_id,
                    comment.comment_id,
                    detected_at,
                )

            _LOGGER.debug(
                "Tracking PR comment for pr_key=%s thread=%s comment=%s seen_at=%s published_at=%s",
                pr_key,
                comment.thread_id,
                comment.comment_id,
                detected_at,
                comment.published_date,
            )

            tracked_comments[comment_key] = detected_at

            detected_at_dt = self._parse_comment_datetime(detected_at)
            if detected_at_dt is not None and now - detected_at_dt <= NEW_COMMENT_WINDOW:
                new_comments.append(comment)

        latest_new = new_comments[-1] if new_comments else None
        _LOGGER.debug(
            "Classified PR comments for pr_key=%s: total=%s latest=%s latest_new=%s new_count=%s bootstrap=%s",
            pr_key,
            len(sorted_comments),
            f"{latest_comment.thread_id}:{latest_comment.comment_id}" if latest_comment else None,
            f"{latest_new.thread_id}:{latest_new.comment_id}" if latest_new else None,
            len(new_comments),
            bootstrap,
        )
        self._seen_state.setdefault("comments", {})[pr_key] = {
            comment_key: detected_at
            for comment_key, detected_at in tracked_comments.items()
        }
        return latest_comment, latest_new, len(new_comments)

    @staticmethod
    def _normalize_tracked_comments(stored_comments: Any) -> dict[str, str]:
        """Normalize stored comment tracking state from older formats."""
        if isinstance(stored_comments, dict):
            normalized: dict[str, str] = {}
            for comment_key, detected_at in stored_comments.items():
                normalized[str(comment_key)] = str(detected_at)
            return normalized
        if isinstance(stored_comments, list):
            return {
                str(comment_id): "1970-01-01T00:00:00+00:00"
                for comment_id in stored_comments
            }
        return {}

    @staticmethod
    def _comment_tracking_key(comment: CommentInfo) -> str:
        """Return a stable key for a comment across PR threads."""
        return f"{comment.thread_id}:{comment.comment_id}"

    @classmethod
    def _should_mark_seen_on_bootstrap(
        cls,
        comment: CommentInfo,
        current_user_aliases: set[str],
        bootstrap_cutoff: datetime | None,
    ) -> bool:
        """Return whether a comment should be treated as already seen on first load."""
        if cls._identity_matches(comment.author, current_user_aliases):
            return True
        if bootstrap_cutoff is None:
            return True
        published_at = cls._parse_comment_datetime(comment.published_date)
        if published_at is None:
            return True
        return published_at <= bootstrap_cutoff.astimezone(timezone.utc)

    @classmethod
    def _bootstrap_seen_timestamp(
        cls,
        comment: CommentInfo,
        current_user_aliases: set[str],
        bootstrap_cutoff: datetime | None,
    ) -> str:
        """Return a stored timestamp for comments marked seen during bootstrap."""
        if cls._identity_matches(comment.author, current_user_aliases):
            published_at = cls._parse_comment_datetime(comment.published_date)
            if published_at is not None:
                return published_at.isoformat()
        return "1970-01-01T00:00:00+00:00"

    @staticmethod
    def _parse_comment_datetime(value: str | None) -> datetime | None:
        """Parse Azure DevOps datetime strings for comment comparison."""
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    @staticmethod
    def _active_comments(comments: list[CommentInfo]) -> list[CommentInfo]:
        """Return user comments belonging to active discussion threads."""
        return [
            comment
            for comment in comments
            if not comment.is_deleted
            and comment.comment_type == HUMAN_COMMENT_TYPE
            and comment.thread_status == "active"
            and comment.text
        ]

    @staticmethod
    def _pull_request_tracking_key(pr: PullRequestInfo) -> str:
        """Return a stable key for PR state across repositories."""
        repository_key = pr.repository_id or "unknown-repository"
        return f"{repository_key}:{pr.pull_request_id}"

    async def _process_transitions(self, data: CoordinatorData) -> None:
        """Persist seen state and emit transition events."""
        previous_build_failures: dict[str, bool] = self._seen_state.get("pr_build_failed", {})
        previous_ready: dict[str, bool] = self._seen_state.get("pr_ready", {})
        published_pull_request_notifications: set[str] = {
            str(pr_id)
            for pr_id in self._seen_state.get("published_pull_request_notifications", [])
        }

        for pr in data.external_pull_requests:
            pr_key = self._pull_request_tracking_key(pr)
            if not self._initialized:
                published_pull_request_notifications.add(pr_key)
                continue
            if pr_key not in published_pull_request_notifications and self._has_passing_build(pr):
                _LOGGER.debug(
                    "Emitting published PR event for repo=%s pr=%s key=%s",
                    pr.repository_name,
                    pr.pull_request_id,
                    pr_key,
                )
                self._dispatch_event(
                    EVENT_NEW_PULL_REQUEST_PUBLISHED,
                    {
                        "organization": data.organization,
                        "project_id": data.project.id,
                        "project_name": data.project.name,
                        "pull_request_id": pr.pull_request_id,
                        "pull_request_title": pr.title,
                        "pull_request_url": pr.url,
                        "repository_id": pr.repository_id,
                        "repository_name": pr.repository_name,
                        "source_ref_name": pr.source_ref_name,
                        "target_ref_name": pr.target_ref_name,
                        "policies": [policy.as_dict() for policy in pr.policies],
                    },
                )
                published_pull_request_notifications.add(pr_key)

        for pr in data.pull_requests:
            pr_key = self._pull_request_tracking_key(pr)
            if self._initialized and pr.latest_new_comment is not None:
                event_type = (
                    EVENT_NEW_AUTHORED_PR_COMMENT
                    if pr.is_authored_by_current_user
                    else EVENT_NEW_REVIEWED_PR_COMMENT
                )
                _LOGGER.debug(
                    "Emitting comment event %s for repo=%s pr=%s thread=%s comment=%s key=%s",
                    event_type,
                    pr.repository_name,
                    pr.pull_request_id,
                    pr.latest_new_comment.thread_id,
                    pr.latest_new_comment.comment_id,
                    pr_key,
                )
                payload = {
                    "organization": data.organization,
                    "project_id": data.project.id,
                    "project_name": data.project.name,
                    "pull_request_id": pr.pull_request_id,
                    "pull_request_title": pr.title,
                    "pull_request_url": pr.url,
                    "repository_id": pr.repository_id,
                    "repository_name": pr.repository_name,
                    **pr.latest_new_comment.as_dict(),
                }
                self._dispatch_event(event_type, payload)

            if self._initialized and not previous_build_failures.get(pr_key, False) and pr.build_failed:
                event_type = (
                    EVENT_AUTHORED_PR_BUILD_FAILED
                    if pr.is_authored_by_current_user
                    else EVENT_REVIEWED_PR_BUILD_FAILED
                )
                _LOGGER.debug(
                    "Emitting build-failed event %s for repo=%s pr=%s key=%s",
                    event_type,
                    pr.repository_name,
                    pr.pull_request_id,
                    pr_key,
                )
                self._dispatch_event(
                    event_type,
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
                event_type = (
                    EVENT_AUTHORED_PR_READY_TO_COMPLETE
                    if pr.is_authored_by_current_user
                    else EVENT_REVIEWED_PR_READY_TO_COMPLETE
                )
                _LOGGER.debug(
                    "Emitting ready-to-complete event %s for repo=%s pr=%s key=%s",
                    event_type,
                    pr.repository_name,
                    pr.pull_request_id,
                    pr_key,
                )
                self._dispatch_event(
                    event_type,
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
            if pr.is_authored_by_current_user:
                published_pull_request_notifications.add(pr_key)

        self._seen_state["published_pull_request_notifications"] = sorted(
            published_pull_request_notifications
        )
        await self.store.async_save(self._seen_state)
        self._initialized = True

    @staticmethod
    def _has_passing_build(pr: PullRequestInfo) -> bool:
        """Return whether the pull request has an approved build policy."""
        build_policies = [
            policy
            for policy in pr.policies
            if policy.display_name and "build" in policy.display_name.casefold()
        ]
        if not build_policies:
            return False
        return any(policy.status == "approved" for policy in build_policies)

    @staticmethod
    def _normalize_identity_value(value: str | None) -> str | None:
        """Normalize an identity string to improve matching across ADO endpoints."""
        if not value:
            return None
        normalized = value.casefold().strip()
        if "\\" in normalized:
            normalized = normalized.split("\\")[-1]
        if "@" in normalized:
            local_part = normalized.split("@", 1)[0]
            compact_local_part = re.sub(r"[^a-z0-9]", "", local_part)
            if compact_local_part:
                return compact_local_part
        compact = re.sub(r"[^a-z0-9]", "", normalized)
        return compact or None

    @classmethod
    def _identity_aliases(cls, identity: IdentityInfo) -> set[str]:
        """Return all normalized aliases for an identity."""
        aliases = set()
        for value in (identity.id, identity.unique_name, identity.display_name):
            normalized = cls._normalize_identity_value(value)
            if normalized:
                aliases.add(normalized)
        return aliases

    @classmethod
    def _identity_matches(
        cls,
        identity: IdentityInfo,
        current_user_aliases: set[str],
    ) -> bool:
        """Return whether an identity matches the current user."""
        if not current_user_aliases:
            return False
        return bool(cls._identity_aliases(identity) & current_user_aliases)

    @property
    def pull_requests_with_new_comments(self) -> list[PullRequestInfo]:
        return [pr for pr in self.data.pull_requests if pr.has_new_comment]

    @property
    def authored_pull_requests(self) -> list[PullRequestInfo]:
        return [pr for pr in self.data.pull_requests if pr.is_authored_by_current_user]

    @property
    def reviewed_pull_requests(self) -> list[PullRequestInfo]:
        return [pr for pr in self.data.pull_requests if pr.is_reviewed_by_current_user]

    @property
    def authored_ready_pull_requests(self) -> list[PullRequestInfo]:
        return [pr for pr in self.authored_pull_requests if pr.ready_to_complete]

    @property
    def reviewed_ready_pull_requests(self) -> list[PullRequestInfo]:
        return [pr for pr in self.reviewed_pull_requests if pr.ready_to_complete]

    @property
    def authored_pull_requests_with_new_comments(self) -> list[PullRequestInfo]:
        return [pr for pr in self.authored_pull_requests if pr.has_new_comment]

    @property
    def reviewed_pull_requests_with_new_comments(self) -> list[PullRequestInfo]:
        return [pr for pr in self.reviewed_pull_requests if pr.has_new_comment]

    @property
    def authored_pull_requests_with_active_comments(self) -> list[PullRequestInfo]:
        return [pr for pr in self.authored_pull_requests if pr.has_active_comments]

    @property
    def reviewed_pull_requests_with_active_comments(self) -> list[PullRequestInfo]:
        return [pr for pr in self.reviewed_pull_requests if pr.has_active_comments]

    @property
    def authored_pull_requests_with_failed_builds(self) -> list[PullRequestInfo]:
        return [pr for pr in self.authored_pull_requests if pr.build_failed]

    @property
    def reviewed_pull_requests_with_failed_builds(self) -> list[PullRequestInfo]:
        return [pr for pr in self.reviewed_pull_requests if pr.build_failed]

    @property
    def ready_pull_requests(self) -> list[PullRequestInfo]:
        return [pr for pr in self.data.pull_requests if pr.ready_to_complete]

    @property
    def pull_requests_with_active_comments(self) -> list[PullRequestInfo]:
        return [pr for pr in self.data.pull_requests if pr.has_active_comments]

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
    def current_user_aliases(self) -> set[str]:
        current_user = self.data.current_user
        if current_user is None:
            return set()
        return self._identity_aliases(current_user)

    @property
    def assigned_work_items(self) -> list[Any]:
        aliases = self.current_user_aliases
        assigned: list[Any] = []
        for item in self.data.work_items:
            normalized = self._normalize_identity_value(item.assigned_to)
            if normalized and normalized in aliases:
                assigned.append(item)
        return assigned

    @staticmethod
    def _work_items_by_type(items: list[Any]) -> dict[str, int]:
        counts = Counter(item.work_item_type or "Unknown" for item in items)
        return dict(counts)

    @staticmethod
    def _work_items_by_state(items: list[Any]) -> dict[str, int]:
        counts = Counter(item.state or "Unknown" for item in items)
        return dict(counts)

    @property
    def assigned_work_items_by_type(self) -> dict[str, int]:
        return self._work_items_by_type(self.assigned_work_items)

    @property
    def assigned_work_items_by_state(self) -> dict[str, int]:
        return self._work_items_by_state(self.assigned_work_items)

    @property
    def latest_new_comment(self) -> CommentInfo | None:
        comments = [pr.latest_new_comment for pr in self.pull_requests_with_new_comments if pr.latest_new_comment]
        if not comments:
            return None
        return sorted(comments, key=lambda item: (item.published_date or "", item.comment_id))[-1]

    @property
    def latest_authored_new_comment(self) -> CommentInfo | None:
        comments = [
            pr.latest_new_comment
            for pr in self.authored_pull_requests_with_new_comments
            if pr.latest_new_comment
        ]
        if not comments:
            return None
        return sorted(comments, key=lambda item: (item.published_date or "", item.comment_id))[-1]

    @property
    def latest_reviewed_new_comment(self) -> CommentInfo | None:
        comments = [
            pr.latest_new_comment
            for pr in self.reviewed_pull_requests_with_new_comments
            if pr.latest_new_comment
        ]
        if not comments:
            return None
        return sorted(comments, key=lambda item: (item.published_date or "", item.comment_id))[-1]

    def get_pull_request(self, pull_request_id: int) -> PullRequestInfo | None:
        """Return a pull request by its id."""
        for pull_request in self.data.pull_requests:
            if pull_request.pull_request_id == pull_request_id:
                return pull_request
        return None
