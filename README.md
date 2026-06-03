# Azure Devops Integration

`Azure DevOps Tracker` is a HACS custom integration for Home Assistant that monitors a single Azure DevOps project per config entry.

## Install With HACS

1. In Home Assistant, open `HACS`.
2. Open the menu in the top-right and choose `Custom repositories`.
3. Paste the GitHub repository URL for this project.
4. Set the category to `Integration`.
5. Add the repository.
6. Open the repository inside HACS and click `Download`.
7. Restart Home Assistant after the download completes.

## Add The Integration

1. In Home Assistant, go to `Settings` -> `Devices & Services`.
2. Click `Add Integration`.
3. Search for `Azure DevOps Tracker`.
4. Enter your Azure DevOps organization and PAT.
5. Choose the project from the dropdown.
6. Enable or disable the feature areas you want.
7. Finish setup and let the first refresh complete.

## Update With HACS

- Open `HACS` -> `Integrations`.
- Open `Azure DevOps Tracker`.
- Install the latest version when updates are available.
- Restart Home Assistant after updating.

## Releases And Versioning

HACS can install this integration directly from the default branch, but tagged GitHub releases give users a cleaner upgrade experience.

Recommended release flow:

1. Merge the intended release commit onto the `release` branch.
2. Update `custom_components/azure_devops_tracker/manifest.json` and bump the `version` field on `release`.
3. Run the `Release` GitHub Actions workflow from the `release` branch.
4. Provide the version number without the leading `v`, for example `0.1.0`.
5. The workflow runs the test suite, creates the tag `v<version>`, builds `azure-devops-tracker.zip`, and publishes the GitHub Release.

Notes:

- HACS uses GitHub Releases when they exist and will show recent release versions in the UI.
- If no GitHub Releases exist, HACS falls back to the repository default branch.
- Tags are created by the workflow and are only allowed from the `release` branch in this repository process.
- GitHub Releases are the part HACS uses to present installable versions nicely.
- The `manifest.json` version should match the released version so Home Assistant can track the installed custom integration version correctly.

Current v0.1 scaffold includes:

- PAT + organization setup flow
- project dropdown loaded from Azure DevOps
- reconfigurable feature toggles
- aggregate sensors for authored/reviewed PRs, project builds, pipelines, and work items
- aggregate binary sensors for authored/reviewed PR attention states
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

## Comment Attributes

The split `has_new_comment` binary sensors expose the latest detected new comment in attributes:

- `latest_comment_author`
- `latest_comment_text`
- `latest_comment_timestamp`
- `latest_comment_thread_id`
- `latest_comment_url`
- `latest_comment_file_path`

The `azure_devops_new_pr_comment` event includes the same information in the event payload, along with PR and repository metadata.

`New comments` are comments first detected by the integration within the last 15 minutes. This includes replies under existing PR comment threads.

`Active comments` are human comments on PR threads whose thread status is still active.

## Entity Model

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

Notes on scope:

- `authored` PR entities only include PRs created by the authenticated user.
- `reviewed` PR entities only include PRs where the authenticated user is a reviewer and not the author.
- Home Assistant events only fire for authored PRs.
- Per-PR entities are no longer created.

## Notes

- This first pass is intentionally project-scoped and aggregate-focused.
- It tracks PRs created by the authenticated user or where the authenticated user is a reviewer.
- Existing comments are marked as seen on first load to avoid a notification storm.

## Remaining Work

- tests
- richer PR-specific entities if you want them later
