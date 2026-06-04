# Azure Devops Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]

[![License][license-shield]][license]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]

`Azure DevOps Tracker` is a HACS custom integration for Home Assistant that monitors a single Azure DevOps project per config entry.

## Install With HACS

1. Download [HACS](https://hacs.xyz/docs/setup/download) if you have not installed it already.
2. In Home Assistant, open `HACS`.

### Add Custom Repository

See: https://hacs.xyz/docs/faq/custom_repositories/

1. Click the three dots in the top-right corner.
2. Select `Custom repositories`.
3. Add the URL to this repository: `https://github.com/ThatDeltaGuy/Azure-Devops-Integration`
4. Select `Integration`.
5. Click `Add`.

### Download Integration
1. Open `HACS`.
2. Search for `Azure DevOps Tracker`.
3. Open the repository and click `Download`.
4. Restart Home Assistant after the download completes.

### Add The Integration

1.  [![Add Integration][add-integration-badge]][add-integration] or in the Home Assistant UI go to `Settings -> Devices & Services`, click `Add Integration`, and search for `Azure DevOps Tracker`.
2. Enter your Azure DevOps organization and PAT.
3. Choose the project from the dropdown.
4. Enable or disable the feature areas you want.
5. Finish setup and let the first refresh complete.

## Update With HACS

- Open `HACS`.
- Search for `Azure DevOps Tracker`.
- Open the repository.
- Install the latest version when updates are available.
- Restart Home Assistant after updating.

Updates will also show up in you home assistant settings under updates.

More information on using the HACS repository dashboard: https://hacs.xyz/docs/use/repositories/dashboard/

## Setup Behavior

1. Enter Azure DevOps organization and PAT.
2. Integration validates access.
3. Projects are loaded into a dropdown.
4. Select one project.
5. Enable or disable builds, work items, PRs, PR comments, and PR policies.

## Recommended PAT Scopes

- `Profile: Read` (`vso.profile`)
- `Code: Read` (`vso.code`)
- `Build: Read` (`vso.build`)
- `Work Items: Read` (`vso.work`)

These cover the current feature set:

- `Profile: Read`
  - used to identify the authenticated user for "my PRs" filtering
- `Code: Read`
  - used for pull requests, reviewers, repositories, and PR comment threads
- `Build: Read`
  - used for pipelines and builds
- `Work Items: Read`
  - used for work item queries and work item details

If only part of the integration is being used, the PAT can be reduced:

- PRs and PR comments only:
  - `Profile: Read`
  - `Code: Read`
- builds only:
  - `Build: Read`
- work items only:
  - `Work Items: Read`

For most installs, the safest practical approach is to create a dedicated PAT for Home Assistant with only the four read scopes above.

---

## What You Get In Home Assistant

The integration is intentionally project-scoped and aggregate-focused. It gives you a project dashboard view of the things that usually need attention, rather than creating one entity per pull request.

### Sensors

- `Authored open pull requests`: how many open PRs you created, plus summary attributes listing those PRs and whether they have new comments, active comments, failed builds, or are ready to complete.
- `Reviewed open pull requests`: how many open PRs you are reviewing, with the same summary detail as above.
- `Failed builds`: a count of failed or partially succeeded builds, with build details in the attributes.
- `Active work items`: a count of active work items in the selected Azure DevOps project, including type and state breakdowns.
- `Assigned active work items`: a count of active work items assigned to you, again with type and state breakdowns.
- `Pipelines`: a count of pipeline definitions in the selected project, plus recent build information in the attributes.

### Binary Sensors

- `Has new comment on authored pull requests`: turns on for 15 minutes after new human comments are detected on your PRs.
- `Has new comment on reviewed pull requests`: the same, but for PRs you are reviewing.
- `Has active comments on authored pull requests`: turns on when your PRs still have active discussion threads.
- `Has active comments on reviewed pull requests`: the same, but for PRs you are reviewing.
- `Has failed build on authored pull requests`: turns on when one of your PRs has a failed build policy.
- `Has failed build on reviewed pull requests`: the same, but for PRs you are reviewing.
- `Has authored pull request ready to complete`: turns on when one of your PRs appears ready to complete.
- `Has reviewed pull request ready to complete`: turns on when a PR you are reviewing appears ready to complete.

### Events

The integration also emits Home Assistant events you can use in automations:

- `azure_devops_new_pull_request_published`: a newly published PR you are reviewing has become visible with a passing build policy.
- `azure_devops_new_comment_on_authored_pull_requests`: a new human comment was detected on one of your PRs.
- `azure_devops_new_comment_on_reviewed_pull_requests`: a new human comment was detected on a PR you are reviewing.
- `azure_devops_failed_build_on_authored_pull_requests`: one of your PRs has moved into a failed build state.
- `azure_devops_failed_build_on_reviewed_pull_requests`: a PR you are reviewing has moved into a failed build state.
- `azure_devops_authored_pull_request_ready_to_complete`: one of your PRs has become ready to complete.
- `azure_devops_reviewed_pull_request_ready_to_complete`: a PR you are reviewing has become ready to complete.
- `azure_devops_review_reset_on_reviewed_pull_requests`: your review vote on someone else’s PR changed back to `0`.

These event types are useful for notifications, dashboards, and automation flows.

### Attributes

The integration exposes most of its useful drill-down data in entity attributes and event payloads so you can build dashboards, notifications, and automations without needing per-PR entities.

#### Sensor Attributes

- `Authored open pull requests` and `Reviewed open pull requests` include:
  - `project_name`
  - `project_id`
  - `pull_requests`: full PR summaries
  - `pull_request_summary`: compact human-readable summary lines
  - `new_comment_count`
  - `active_comment_count`
  - `ready_to_complete_count`
  - `failed_build_count`
- `Failed builds` includes:
  - `failed_builds`: the current failed or partially succeeded builds
- `Active work items` includes:
  - `work_items_by_type`
  - `work_items_by_state`
  - `work_items`: full work item summaries
  - `work_item_summary`: compact human-readable summary lines
  - flattened counts such as `count_bug`, `count_task`, or similar based on the work item types present
- `Assigned active work items` includes:
  - `work_items_by_type`
  - `work_items_by_state`
  - `work_items`
  - `work_item_summary`
  - flattened counts such as `count_bug`, `count_task`, or similar based on the work item types present
- `Pipelines` includes:
  - `pipelines`: the pipeline definitions in the selected project
  - `latest_builds`: the most recent build for each loaded definition

#### Has New Comment Attributes

The split `has_new_comment` binary sensors expose the latest detected new comment in attributes:

- `latest_comment_author`
- `latest_comment_text`
- `latest_comment_timestamp`
- `latest_comment_thread_id`
- `latest_comment_url`
- `latest_comment_file_path`

The `azure_devops_new_comment_on_authored_pull_requests` and `azure_devops_new_comment_on_reviewed_pull_requests` events include the same information in the event payload, along with PR and repository metadata.

`New comments` are comments first detected by the integration within the last 15 minutes. This includes replies under existing PR comment threads.

`Active comments` are human comments on PR threads whose thread status is still active.

#### Has Active Comment Attributes

The split `has_active_comments` binary sensors expose:

- `pull_request_count`: how many PRs currently have active comment threads
- `pull_requests`: the PR summaries for those PRs

#### Has Failed Build Attributes

The split `has_failed_build` binary sensors expose:

- `failed_build_count`: how many PRs are currently in a failed build state
- `pull_requests`: the PR summaries for those PRs

#### Ready to Complete Attributes

The split `ready_to_complete` binary sensors expose:

- `ready_pull_request_count`: how many PRs currently appear ready to complete
- `pull_requests`: the PR summaries for those PRs

#### Event Attributes

All PR-related events include enough metadata to identify the project, repository, and pull request involved.

- `azure_devops_new_pull_request_published` includes:
  - `organization`
  - `project_id`
  - `project_name`
  - `pull_request_id`
  - `pull_request_title`
  - `pull_request_url`
  - `repository_id`
  - `repository_name`
  - `source_ref_name`
  - `target_ref_name`
  - `policies`
- `azure_devops_new_comment_on_authored_pull_requests` and `azure_devops_new_comment_on_reviewed_pull_requests` include:
  - `organization`
  - `project_id`
  - `project_name`
  - `pull_request_id`
  - `pull_request_title`
  - `pull_request_url`
  - `repository_id`
  - `repository_name`
  - the full latest new comment payload:
    - `comment_id`
    - `thread_id`
    - `author_id`
    - `author_name`
    - `author_unique_name`
    - `text`
    - `published_date`
    - `url`
    - `file_path`
    - `is_reply`
    - `comment_type`
    - `is_deleted`
    - `thread_status`
- `azure_devops_failed_build_on_authored_pull_requests` and `azure_devops_failed_build_on_reviewed_pull_requests` include:
  - `organization`
  - `project_name`
  - `pull_request_id`
  - `pull_request_title`
  - `pull_request_url`
  - `repository_name`
  - `policies`
- `azure_devops_authored_pull_request_ready_to_complete` and `azure_devops_reviewed_pull_request_ready_to_complete` include:
  - `organization`
  - `project_name`
  - `pull_request_id`
  - `pull_request_title`
  - `pull_request_url`
  - `repository_name`
  - `source_ref_name`
  - `target_ref_name`
- `azure_devops_review_reset_on_reviewed_pull_requests` includes:
  - `organization`
  - `project_id`
  - `project_name`
  - `pull_request_id`
  - `pull_request_title`
  - `pull_request_url`
  - `repository_id`
  - `repository_name`
  - `source_ref_name`
  - `target_ref_name`
  - `previous_vote`
  - `current_vote`

---

## Technical Reference

Sensors:

- sensor: authored open pull requests
- sensor: reviewed open pull requests
- sensor: failed builds
- sensor: active work items
- sensor: assigned active work items
- sensor: pipelines

Binary sensors:

- binary sensor: has new comment on authored pull requests
- binary sensor: has new comment on reviewed pull requests
- binary sensor: has active comments on authored pull requests
- binary sensor: has active comments on reviewed pull requests
- binary sensor: has failed build on authored pull requests
- binary sensor: has failed build on reviewed pull requests
- binary sensor: has authored pull request ready to complete
- binary sensor: has reviewed pull request ready to complete

Events:

- event: new pull request published
- event: new comment on authored pull requests
- event: new comment on reviewed pull requests
- event: failed build on authored pull requests
- event: failed build on reviewed pull requests
- event: authored pull request ready to complete
- event: reviewed pull request ready to complete
- event: review reset on reviewed pull requests

Notes on scope:

- `authored` PR entities only include PRs created by the authenticated user.
- `reviewed` PR entities only include PRs where the authenticated user is a reviewer and not the author.
- Home Assistant events only fire for authored PRs.
- Per-PR entities are no longer created.

## Notes

- This first pass is intentionally project-scoped and aggregate-focused.
- It tracks PRs created by the authenticated user or where the authenticated user is a reviewer.
- Existing comments are marked as seen on first load to avoid a notification storm.

## Releases And Versioning

HACS installs this integration from GitHub Releases. The default branch is hidden from HACS, so tagged releases are the supported installation path.

Recommended release flow:

1. Merge the intended release commit onto the `release` branch.
2. Update `custom_components/azure_devops_tracker/manifest.json` and bump the `version` field on `release`.
3. Run the `Release` GitHub Actions workflow from the `release` branch.
4. Provide the version number without the leading `v`, for example `0.3.0`.
5. The workflow runs the test suite, creates the tag `v<version>`, builds `azure-devops-tracker.zip`, and publishes the GitHub Release.

Notes:

- HACS uses GitHub Releases when they exist and will show recent release versions in the UI.
- HACS is configured to hide the default branch and use the release asset `azure-devops-tracker.zip`.
- Tags are created by the workflow and are only allowed from the `release` branch in this repository process.
- GitHub Releases are the part HACS uses to present installable versions nicely.
- The `manifest.json` version should match the released version so Home Assistant can track the installed custom integration version correctly.

Current v0.3 scaffold includes:

- PAT + organization setup flow
- project dropdown loaded from Azure DevOps
- reconfigurable feature toggles
- aggregate sensors for authored/reviewed PRs, project builds, pipelines, and work items
- aggregate binary sensors for authored/reviewed PR attention states
- Home Assistant events for PR publication, comments, build failures, ready-to-complete transitions, and review resets

## Repository Layout

```text
custom_components/azure_devops_tracker/
```


[commits-shield]: https://img.shields.io/github/commit-activity/w/ThatDeltaGuy/Azure-Devops-Integration?style=for-the-badge
[commits]: https://github.com/ThatDeltaGuy/Azure-Devops-Integration/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license]: https://github.com/ThatDeltaGuy/Azure-Devops-Integration/blob/main/LICENSE.md
[license-shield]: https://img.shields.io/github/license/ThatDeltaGuy/Azure-Devops-Integration.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40ThatDeltaGuy-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/ThatDeltaGuy/Azure-Devops-Integration.svg?style=for-the-badge
[releases]: https://github.com/ThatDeltaGuy/Azure-Devops-Integration/releases
[user_profile]: https://github.com/ThatDeltaGuy
[add-integration]: https://my.home-assistant.io/redirect/config_flow_start?domain=azure_devops_tracker
[add-integration-badge]: https://my.home-assistant.io/badges/config_flow_start.svg
