# Global Agent Instructions

## Scope

- Apply these instructions in any repository unless a project-level `AGENTS.md` provides more specific guidance.
- Treat repository-local instructions as higher priority than this file.
- Use this file for shared defaults only; do not place repository-specific structure here.

## General Working Rules

- Use British English in documentation, comments, and user-facing text.
- Follow the existing patterns and conventions of the repository you are editing.
- Read the local `AGENTS.md` first when one exists.
- Do not overwrite or revert user changes unless the user explicitly asks for that.
- Prefer minimal, targeted changes over broad refactors.
- Keep changes easy to review and consistent with the surrounding code.

## Tooling and Safety

- Prefer dedicated file and search tools over shell commands when the environment provides them.
- Use non-destructive commands by default.
- Avoid destructive Git operations unless the user explicitly requests them.
- Do not create commits, branches, or pull requests unless the user asks.
- When working in WSL, use `git.exe` for remote Git operations if Windows credentials are required.

## Questions, Research, and Exploration
### Analytical Posture
- When the user is asking questions, requesting analysis, comparing approaches, exploring options, or asking for research, default to an analysis-first posture rather than immediate execution.
- Treat the problem, not the user's current framing, as the level setter.
- Assume an expert audience; maintain full conceptual depth and avoid unnecessary simplification.
- Do not conclude or summarise unless the user asks for it.
- Stop when further explanation would add no meaningful insight.
- Challenge weak assumptions, misframed questions, and structurally unsound reasoning directly.
- Say "that's not the right question" when the framing obscures the real problem.
- Surface competing frames, trade-offs, incentives, system dynamics, and second-order effects where they materially affect the answer.
- Ask targeted clarifying questions when requirements, trade-offs, or intent are materially underspecified.
- Do not make large assumptions about user intent when those assumptions would change the direction of the work.
- Keep plans and analyses concise but execution-ready, with clear dependencies, risks, open questions, and decision points.
- Do not flatten language; when using an unfamiliar but load-bearing term (a term carrying essential conceptual weight), define it briefly inline on first use, then continue at full depth.
- If the user signals unfamiliarity, preserve depth and add only minimal inline scaffolding needed to keep the reasoning legible.
- Expand abbreviations on first use unless the user has already used them.
### Research and Web Investigation
- When useful, search the repository, available documentation, or the web to ground the answer in evidence rather than inference.
- When researching code, tools, frameworks, or architectural guidance on the web, do not default to mainstream, vendor-led, highly credentialed, or institutionally prominent sources as correct merely because they are prominent.
- Analyse technical claims through incentives and context, including vendor lock-in, benchmark gaming, product marketing, ecosystem capture, survivorship bias, and cargo-cult adoption (copying patterns without understanding why they exist).
- Prefer primary and operationally grounded sources where possible, such as official documentation, source code, release notes, issue trackers, maintainers' explanations, real migration reports, and reproducible examples.
- Treat contested technical topics as analytical problems rather than tribal positions; compare failure modes, hidden assumptions, operational costs, and where each view breaks down.
- Do not assume the current dominant pattern is the end state of knowledge; remain open to emerging approaches, changing constraints, and cases where older or less fashionable solutions are structurally better.
### Execution Boundaries During Exploratory Work
- Prefer read-only investigation unless the user explicitly asks for implementation or system changes.
- If the user indicates that they do not want execution yet, remain strictly read-only until they explicitly change that instruction.
- During exploratory work, do not edit files, modify configuration, create commits, or make system changes unless the user has clearly moved from analysis into execution.
- Treat explicit non-execution instructions as higher priority than implied pressure to start changing files.

## Instruction Precedence

Apply instructions in this order:

1. System and developer instructions from the active CLI.
2. Repository-local instructions such as `AGENTS.md`, `CLAUDE.md`, or equivalent.
3. These global instructions.
4. Default model behaviour.

## Project Guidance

- Preserve existing architecture unless the task clearly requires structural change.
- Match naming, formatting, and test patterns already used in the codebase.
- When adding files, place them in the most relevant existing folder before introducing new structure.
- Document assumptions when the repository context is incomplete.

## Communication

- Be concise, direct, and practical.
- Explain what changed, where it changed, and why it changed.
- Suggest natural next steps only when they add value.
- Do not apologise unnecessarily.
- Do not compliment the user unnecessarily.

# Repository-Specific Instructions

# Repository Guide

## Repository Overview

This repository contains `Azure DevOps Tracker`, a Home Assistant custom integration distributed through HACS.

It does not follow the usual Substation360 C# backend or TypeScript/React frontend shapes. The dominant evidence is a Python integration package under `custom_components/`, a pytest suite, and GitHub Actions that run the test suite on Python 3.12, so this guide treats it as a backend-style integration repository.

The repository primarily contains:

- a Home Assistant config-entry integration for a single Azure DevOps project per config entry
- an async Azure DevOps REST client and polling coordinator
- aggregate sensor, binary sensor, and event entities exposed to Home Assistant
- a lightweight local pytest suite that uses Home Assistant stubs instead of a full Home Assistant install

## Solution Layout

There is no `.sln`, `.csproj`, `package.json`, or monorepo workspace manifest at the repository root.

The repository is organised around one deployable integration package:

- `custom_components/azure_devops_tracker/` contains the runtime integration shipped to Home Assistant
- `tests/` contains the repository test suite
- `.github/workflows/tests.yml` is the main shared CI definition and runs `python -m pytest`

Within the integration package, the main runtime split is:

- `__init__.py`: config-entry setup, unload, and legacy entity cleanup
- `api.py`: async Azure DevOps REST client built on `aiohttp`
- `coordinator.py`: `DataUpdateCoordinator` refresh logic, transition detection, and persisted seen-state
- `config_flow.py` and `options_flow.py`: setup and reconfiguration flows
- `sensor.py`, `binary_sensor.py`, and `event.py`: Home Assistant platforms built from coordinator state
- `models.py`: shared dataclasses for Azure DevOps payloads and coordinator snapshots
- `const.py`: integration constants, event names, scan interval bounds, and platform registration

## Project Directories

- `custom_components/azure_devops_tracker/`: the only runtime project directory. Contains the Home Assistant integration code, manifest metadata, config and options flows, coordinator logic, entity platforms, diagnostics, and user-facing strings.
- `tests/`: pytest-based repository test suite covering the Azure DevOps client, config flow behaviour, coordinator logic, and entity state/attributes. `conftest.py` installs local Home Assistant shims so tests can run without installing the full Home Assistant dependency tree.

## Supporting Top-Level Paths

- `.github/workflows/`: CI workflow definitions. The repository currently uses a single `tests.yml` workflow.
- `brand/`: repository-level branding assets used alongside the Home Assistant integration packaging.
- `custom_components/`: Home Assistant custom integration root required by HACS and Home Assistant.

## Important Top-Level Files

- `README.md`: primary repository documentation, install/setup notes, PAT scope guidance, and release flow.
- `hacs.json`: HACS metadata for custom integration discovery and README rendering.
- `pytest.ini`: points pytest at the `tests/` directory.
- `requirements-dev.txt`: local development and test dependencies.
- `.github/workflows/tests.yml`: CI entry point that installs `requirements-dev.txt` and runs `python -m pytest` on Python 3.12.
- `.gitignore`: standard Python ignore rules for virtual environments, caches, build output, and coverage artefacts.

## Technology Stack

- Python 3.12 in CI
- Home Assistant custom integration architecture based on config entries and `DataUpdateCoordinator`
- `aiohttp` for async Azure DevOps REST calls
- `voluptuous` and Home Assistant selectors for config and options flows
- `dataclasses` with `slots=True` for integration models
- `pytest` for the automated test suite
- HACS packaging via `hacs.json`
- GitHub Actions for CI

## Build, Test, and Run

Install development dependencies from the repository root:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Run the repository test suite from the repository root:

```bash
python -m pytest
```

The CI workflow does the same on `ubuntu-latest` with Python 3.12.

There is no standalone application runner in this repository. To exercise the integration end-to-end, install the repository as a HACS custom integration or copy `custom_components/azure_devops_tracker/` into a Home Assistant instance and configure it through `Settings -> Devices & Services`.

Release workflow evidenced by `README.md`:

```bash
# 1. Bump the integration version in custom_components/azure_devops_tracker/manifest.json
# 2. Commit the version change
git tag v<version>
# 3. Publish a GitHub Release from that tag
```

Testing note:

- This repository uses `pytest`, not .NET test tooling.
- If this repository later gains ancillary .NET tests or utilities, do not introduce Fluent Assertions; it is being removed from the wider engineering approach.
- If this repository later gains ancillary .NET tests or utilities, prefer xUnit for new tests and when updating existing tests.

## Development Conventions

- Keep runtime code under `custom_components/azure_devops_tracker/`; Home Assistant expects that package layout.
- Follow the existing module split: API transport in `api.py`, refresh and transition logic in `coordinator.py`, shared models in `models.py`, and entity presentation in the platform modules.
- Preserve the config-entry-first architecture. Setup and reconfiguration belong in `config_flow.py` and `options_flow.py`, not in YAML-only patterns.
- Keep the integration aggregate-focused. The current codebase intentionally exposes project-level sensors, binary sensors, and events rather than creating per-pull-request entities.
- Keep new runtime code typed. The existing code consistently uses `from __future__ import annotations`, explicit type hints, and dataclasses with `slots=True` for payload models.
- Reuse the constants in `const.py` for option keys, event names, API versions, and scan interval bounds instead of duplicating literals.
- Keep Home Assistant-facing strings in `strings.json` and integration metadata in `manifest.json`.
- Match the existing test style: plain pytest tests, focused fakes, and Home Assistant stubs in `tests/conftest.py` rather than pulling in a full Home Assistant runtime for unit-level coverage.

## Release and Operational Notes

- The integration is HACS-oriented. `hacs.json` declares that repository content is not rooted at the top level and that the README should be rendered in HACS.
- `custom_components/azure_devops_tracker/manifest.json` currently declares:
  - domain `azure_devops_tracker`
  - integration type `service`
  - IoT class `cloud_polling`
  - minimum Home Assistant version `2025.1.0`
- Tagged GitHub releases matter operationally. The README explicitly notes that HACS can follow the default branch, but GitHub Releases provide the cleaner upgrade path for end users.
- The documented PAT scopes are read-only and intentionally narrow: `vso.profile`, `vso.code`, `vso.build`, and `vso.work`.
- Polling is configurable per entry. `const.py` sets the supported bounds to 30 to 900 seconds, with a default of 120 seconds.

## Important Repo-Specific Constraints

- Treat this as a single-project integration repository, not a general Python application or monorepo.
- One config entry monitors one Azure DevOps project. Changes that assume cross-project aggregation would alter a core repository behaviour and should be made deliberately.
- The coordinator persists seen-state between refreshes. Be careful when changing comment/build transition logic because it affects notification/event behaviour and first-load suppression.
- There are currently no custom Home Assistant services; `services.yaml` explicitly states that the integration emits events on the Home Assistant event bus instead.
- The test suite is intentionally lightweight and stub-driven. If you introduce code that requires a real Home Assistant runtime, keep that separation clear and avoid breaking the existing fast unit-test path.
- Repository-local AI customisations for this project should be maintained in the shared AI repository under `Project Specific/Azure Devops Integration/...`, not directly in this repository's `.opencode/` directory. The local `.opencode/` output is generated by `/init` and should be treated as synced output rather than the source of truth.
