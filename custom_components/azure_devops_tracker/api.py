"""Azure DevOps REST client used by the custom integration."""

from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any

import aiohttp

from .const import (
    API_VERSION_BUILD,
    API_VERSION_CONNECTION_DATA,
    API_VERSION_CORE,
    API_VERSION_GIT,
    API_VERSION_POLICY,
    API_VERSION_PROFILE,
    API_VERSION_WIT,
)
from .models import (
    BuildInfo,
    CommentInfo,
    IdentityInfo,
    PipelineInfo,
    PolicyInfo,
    ProjectInfo,
    PullRequestInfo,
    WorkItemInfo,
)

BASE_URL = "https://dev.azure.com"
PROFILE_URL = "https://app.vssps.visualstudio.com"

_LOGGER = logging.getLogger(__name__)


class AzureDevOpsApiError(Exception):
    """Base API error."""


class AzureDevOpsAuthError(AzureDevOpsApiError):
    """Authentication failure."""


class AzureDevOpsClient:
    """Small async Azure DevOps REST client."""

    def __init__(self, session: aiohttp.ClientSession, pat: str) -> None:
        self._session = session
        self._auth_header = {
            "Authorization": aiohttp.BasicAuth("", pat).encode(),
            "Content-Type": "application/json",
        }

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform a JSON REST call."""
        _LOGGER.debug(
            "Azure DevOps request starting: method=%s url=%s params=%s has_json=%s",
            method,
            url,
            params,
            json_data is not None,
        )
        async with self._session.request(
            method,
            url,
            headers=self._auth_header,
            params=params,
            json=json_data,
        ) as response:
            if response.status in (401, 403):
                _LOGGER.debug(
                    "Azure DevOps authentication failed: method=%s url=%s status=%s params=%s",
                    method,
                    url,
                    response.status,
                    params,
                )
                raise AzureDevOpsAuthError("Authentication failed")
            if response.status >= 400:
                body = await response.text()
                body_preview = " ".join(body.split())[:200] if body else ""
                _LOGGER.debug(
                    "Azure DevOps request failed: method=%s url=%s status=%s params=%s body=%s",
                    method,
                    url,
                    response.status,
                    params,
                    body_preview,
                )
                raise AzureDevOpsApiError(
                    f"Azure DevOps request failed: {response.status} for {url}"
                    f"{f' - {body_preview}' if body_preview else ''}"
                )

            data = await response.json(content_type=None)
            if not isinstance(data, dict):
                _LOGGER.debug(
                    "Azure DevOps returned unexpected payload type %s for url=%s",
                    type(data).__name__,
                    url,
                )
                raise AzureDevOpsApiError("Azure DevOps returned an unexpected payload")
            _LOGGER.debug(
                "Azure DevOps request succeeded: method=%s url=%s status=%s top_level_keys=%s",
                method,
                url,
                response.status,
                sorted(data.keys()),
            )
            return data

    async def validate_organization(self, organization: str) -> None:
        """Validate the PAT against an organization."""
        _LOGGER.debug("Validating Azure DevOps organization '%s' with supplied PAT", organization)
        await self._request_json(
            "GET",
            f"{BASE_URL}/{organization}/_apis/projects",
            params={"api-version": API_VERSION_CORE, "$top": 1},
        )

    async def get_current_user(self, organization: str) -> IdentityInfo:
        """Return the signed-in profile."""
        try:
            _LOGGER.debug("Resolving current Azure DevOps user via profile host for organization '%s'", organization)
            data = await self._request_json(
                "GET",
                f"{PROFILE_URL}/_apis/profile/profiles/me",
                params={"api-version": API_VERSION_PROFILE, "details": "true"},
            )
            identity = IdentityInfo(
                id=data.get("id"),
                display_name=data.get("displayName"),
                unique_name=data.get("emailAddress"),
            )
            _LOGGER.debug("Resolved current Azure DevOps user via profile host: %s", identity.as_dict())
            return identity
        except AzureDevOpsAuthError:
            # Some PATs work for project-scoped APIs but not the profile host.
            # Fall back to connection data on dev.azure.com so the integration
            # can still load instead of failing the whole config entry.
            _LOGGER.debug(
                "Profile host rejected PAT for organization '%s'; falling back to connectionData",
                organization,
            )
            data = await self._request_json(
                "GET",
                f"{BASE_URL}/{organization}/_apis/connectionData",
                params={
                    "api-version": API_VERSION_CONNECTION_DATA,
                    "connectOptions": "1",
                    "lastChangeId": "-1",
                    "lastChangeId64": "-1",
                },
            )
            authenticated_user = data.get("authenticatedUser") or {}
            identity = IdentityInfo(
                id=authenticated_user.get("id") or authenticated_user.get("descriptor"),
                display_name=authenticated_user.get("providerDisplayName")
                or authenticated_user.get("customDisplayName")
                or authenticated_user.get("displayName"),
                unique_name=authenticated_user.get("uniqueName")
                or authenticated_user.get("subjectDescriptor"),
            )
            _LOGGER.debug("Resolved current Azure DevOps user via connectionData fallback: %s", identity.as_dict())
            return identity

    async def list_projects(self, organization: str) -> list[ProjectInfo]:
        """Return visible projects for an organization."""
        data = await self._request_json(
            "GET",
            f"{BASE_URL}/{organization}/_apis/projects",
            params={"api-version": API_VERSION_CORE, "$top": 500},
        )
        projects = [
            ProjectInfo(
                id=item["id"],
                name=item["name"],
                description=item.get("description"),
                url=item.get("url"),
                state=item.get("state"),
                visibility=item.get("visibility"),
            )
            for item in data.get("value", [])
        ]
        _LOGGER.debug("Loaded %s Azure DevOps projects for organization '%s'", len(projects), organization)
        return projects

    async def list_pipelines(self, organization: str, project: str) -> list[PipelineInfo]:
        """Return build definitions for a project."""
        data = await self._request_json(
            "GET",
            f"{BASE_URL}/{organization}/{project}/_apis/build/definitions",
            params={"api-version": API_VERSION_BUILD, "$top": 500},
        )
        pipelines = [
            PipelineInfo(
                definition_id=item["id"],
                name=item["name"],
                path=item.get("path"),
                queue_status=item.get("queueStatus"),
                url=item.get("url"),
            )
            for item in data.get("value", [])
        ]
        _LOGGER.debug(
            "Loaded %s pipeline definitions for Azure DevOps project '%s'",
            len(pipelines),
            project,
        )
        return pipelines

    async def list_builds(self, organization: str, project: str) -> list[BuildInfo]:
        """Return recent builds."""
        data = await self._request_json(
            "GET",
            f"{BASE_URL}/{organization}/{project}/_apis/build/builds",
            params={
                "api-version": API_VERSION_BUILD,
                "$top": 100,
                "queryOrder": "queueTimeDescending",
                "maxBuildsPerDefinition": 1,
            },
        )
        builds: list[BuildInfo] = []
        for item in data.get("value", []):
            requested_for = item.get("requestedFor") or {}
            definition = item.get("definition") or {}
            links = item.get("_links") or {}
            web = links.get("web") or {}
            builds.append(
                BuildInfo(
                    build_id=item["id"],
                    definition_id=definition.get("id"),
                    definition_name=definition.get("name"),
                    build_number=item.get("buildNumber"),
                    status=item.get("status"),
                    result=item.get("result"),
                    source_branch=item.get("sourceBranch"),
                    source_version=item.get("sourceVersion"),
                    queue_time=item.get("queueTime"),
                    start_time=item.get("startTime"),
                    finish_time=item.get("finishTime"),
                    requested_for=requested_for.get("displayName"),
                    url=web.get("href"),
                )
            )
        _LOGGER.debug("Loaded %s builds for Azure DevOps project '%s'", len(builds), project)
        return builds

    async def list_pull_requests(self, organization: str, project: str) -> list[PullRequestInfo]:
        """Return active pull requests for a project."""
        data = await self._request_json(
            "GET",
            f"{BASE_URL}/{organization}/{project}/_apis/git/pullrequests",
            params={"api-version": API_VERSION_GIT, "searchCriteria.status": "active", "$top": 200},
        )

        pull_requests: list[PullRequestInfo] = []
        for item in data.get("value", []):
            repository = item.get("repository") or {}
            author = self._parse_identity(item.get("createdBy"))
            reviewers = [self._parse_identity(reviewer) for reviewer in item.get("reviewers", [])]
            pull_requests.append(
                PullRequestInfo(
                    pull_request_id=item["pullRequestId"],
                    title=item.get("title") or f"PR {item['pullRequestId']}",
                    status=item.get("status"),
                    merge_status=item.get("mergeStatus"),
                    is_draft=item.get("isDraft", False),
                    url=item.get("url"),
                    created_date=item.get("creationDate"),
                    source_ref_name=item.get("sourceRefName"),
                    target_ref_name=item.get("targetRefName"),
                    repository_id=repository.get("id"),
                    repository_name=repository.get("name"),
                    author=author,
                    reviewers=reviewers,
                )
            )
        _LOGGER.debug("Loaded %s pull requests for Azure DevOps project '%s'", len(pull_requests), project)
        return pull_requests

    async def list_pull_request_comments(
        self,
        organization: str,
        project: str,
        repository_id: str,
        pull_request_id: int,
    ) -> list[CommentInfo]:
        """Return text comments for a pull request."""
        data = await self._request_json(
            "GET",
            f"{BASE_URL}/{organization}/{project}/_apis/git/repositories/{repository_id}/pullRequests/{pull_request_id}/threads",
            params={"api-version": API_VERSION_GIT},
        )
        comments: list[CommentInfo] = []
        for thread in data.get("value", []):
            thread_id = thread.get("id")
            thread_status = thread.get("status")
            thread_context = thread.get("threadContext") or {}
            file_path = thread_context.get("filePath")
            for comment in thread.get("comments", []):
                comments.append(
                    CommentInfo(
                        comment_id=comment.get("id", 0),
                        thread_id=thread_id,
                        author=self._parse_identity(comment.get("author")),
                        text=comment.get("content"),
                        published_date=comment.get("publishedDate"),
                        url=None,
                        file_path=file_path,
                        is_reply=bool(comment.get("parentCommentId")),
                        comment_type=comment.get("commentType"),
                        is_deleted=comment.get("isDeleted", False),
                        thread_status=thread_status,
                    )
                )
        _LOGGER.debug(
            "Loaded %s comments/threads entries for pull request %s in project '%s'",
            len(comments),
            pull_request_id,
            project,
        )
        return comments

    async def list_policy_evaluations(
        self,
        organization: str,
        project: str,
        project_id: str,
        pull_request_id: int,
    ) -> list[PolicyInfo]:
        """Return PR policy evaluations."""
        artifact_id = f"vstfs:///CodeReview/CodeReviewId/{project_id}/{pull_request_id}"
        data = await self._request_json(
            "GET",
            f"{BASE_URL}/{organization}/{project}/_apis/policy/evaluations",
            params={
                "api-version": API_VERSION_POLICY,
                "artifactId": artifact_id,
                "includeNotApplicable": "false",
            },
        )
        policies: list[PolicyInfo] = []
        for item in data.get("value", []):
            configuration = item.get("configuration") or {}
            policy_type = configuration.get("type") or {}
            policies.append(
                PolicyInfo(
                    evaluation_id=item.get("evaluationId", ""),
                    display_name=policy_type.get("displayName"),
                    status=item.get("status"),
                    is_blocking=configuration.get("isBlocking", False),
                )
            )
        _LOGGER.debug(
            "Loaded %s policy evaluations for pull request %s in project '%s'",
            len(policies),
            pull_request_id,
            project,
        )
        return policies

    async def list_work_items(self, organization: str, project: str) -> list[WorkItemInfo]:
        """Return active work items using a WIQL query."""
        wiql = (
            "SELECT [System.Id] "
            "FROM WorkItems "
            f"WHERE [System.TeamProject] = '{project}' "
            "AND [System.State] <> 'Done' "
            "AND [System.State] <> 'Closed' "
            "AND [System.State] <> 'Removed'"
        )
        wiql_data = await self._request_json(
            "POST",
            f"{BASE_URL}/{organization}/{project}/_apis/wit/wiql",
            params={"api-version": API_VERSION_WIT},
            json_data={"query": wiql},
        )
        ids = [str(item["id"]) for item in wiql_data.get("workItems", [])]
        if not ids:
            return []

        work_items: list[WorkItemInfo] = []
        for chunk in self._chunk(ids, 200):
            data = await self._request_json(
                "GET",
                f"{BASE_URL}/{organization}/{project}/_apis/wit/workitems",
                params={
                    "api-version": API_VERSION_WIT,
                    "ids": ",".join(chunk),
                    "errorPolicy": "omit",
                },
            )
            for item in data.get("value", []):
                fields = item.get("fields") or {}
                assigned_to = fields.get("System.AssignedTo") or {}
                work_items.append(
                    WorkItemInfo(
                        work_item_id=item["id"],
                        title=fields.get("System.Title"),
                        work_item_type=fields.get("System.WorkItemType"),
                        state=fields.get("System.State"),
                        assigned_to=assigned_to.get("displayName") if isinstance(assigned_to, dict) else None,
                        changed_date=fields.get("System.ChangedDate"),
                        url=item.get("url"),
                    )
                )
        _LOGGER.debug("Loaded %s work items for Azure DevOps project '%s'", len(work_items), project)
        return work_items

    @staticmethod
    def _parse_identity(payload: dict[str, Any] | None) -> IdentityInfo:
        """Parse an Azure DevOps identity payload."""
        payload = payload or {}
        return IdentityInfo(
            id=payload.get("id"),
            display_name=payload.get("displayName"),
            unique_name=payload.get("uniqueName") or payload.get("emailAddress"),
            vote=payload.get("vote"),
        )

    @staticmethod
    def _chunk(values: Iterable[str], size: int) -> list[list[str]]:
        """Return string chunks."""
        values_list = list(values)
        return [values_list[index : index + size] for index in range(0, len(values_list), size)]
