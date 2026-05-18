# Azure Devops Integration

`Azure DevOps Tracker` is a HACS custom integration for Home Assistant that monitors a single Azure DevOps project per config entry.

Current v0.1 scaffold includes:

- PAT + organization setup flow
- project dropdown loaded from Azure DevOps
- reconfigurable feature toggles
- aggregate sensors for PRs, comments, builds, pipelines, and work items
- per-PR sensors and binary sensors for tracked pull requests
- binary sensors for `has_new_comment`, `has_failed_build`, and `has_ready_pull_request`
- Home Assistant events for:
  - `azure_devops_new_pr_comment`
  - `azure_devops_pr_build_failed`
  - `azure_devops_pr_ready_to_complete`

## Repository Layout

```text
custom_components/azure_devops_tracker/
```

## Setup Behavior

1. Enter Azure DevOps organization and PAT.
2. Integration validates access.
3. Projects are loaded into a dropdown.
4. Select one project.
5. Enable or disable builds, work items, PRs, PR comments, and PR policies.

## Recommended PAT Scopes

- `vso.profile`
- `vso.code`
- `vso.build`
- `vso.work`

## Comment Attributes

The `binary_sensor.has_new_comment` entity exposes the latest unseen comment in attributes:

- `latest_comment_author`
- `latest_comment_text`
- `latest_comment_timestamp`
- `latest_comment_thread_id`
- `latest_comment_url`
- `latest_comment_file_path`

The `azure_devops_new_pr_comment` event includes the same information in the event payload, along with PR and repository metadata.

## Entity Model

Aggregate entities:

- sensor: open pull requests
- sensor: ready pull requests
- sensor: pull requests with new comments
- sensor: failed builds
- sensor: active work items
- sensor: pipelines
- binary sensor: has new comment
- binary sensor: has failed build
- binary sensor: has ready pull request

Per-PR entities for each tracked PR:

- sensor: `PR <id> state`
- sensor: `PR <id> unseen comments`
- binary sensor: `PR <id> has new comment`
- binary sensor: `PR <id> build failed`
- binary sensor: `PR <id> ready to complete`

The per-PR entities are created dynamically for PRs that match the current scope: created by you or where you are a reviewer.

## Notes

- This first pass is intentionally project-scoped and aggregate-focused.
- It tracks PRs created by you or where you are a reviewer.
- Existing comments are marked as seen on first load to avoid a notification storm.

## Remaining Work

- tests
- richer PR-specific entities if you want them later
