# CNA Bootstrap Findings: GitHub App and Docker Hub

Date: 2026-06-21
Repository: saulpatinojr/Work-Cloud_Network_Assessment

## Summary

The initializer previously skipped GitHub App creation when the repository already had both `GH_APP_ID` and `GH_APP_PRIVATE_KEY` configured as GitHub Secrets.

That behavior has been changed. The script now assumes no valid GitHub App exists, creates a new GitHub App, and updates `GH_APP_ID` and `GH_APP_PRIVATE_KEY` with the newly generated credentials.

## GitHub App Findings

- Existing `GH_APP_ID` and `GH_APP_PRIVATE_KEY` no longer suppress app creation.
- Existing GitHub App secrets are treated as stale bootstrap state and are replaced after a new app is created.
- The script opens the GitHub App manifest creation flow and creates a new app named `CNA Assessment Tool`.
- If GitHub reports that the app name is taken, the existing app must be deleted in GitHub Developer Settings before rerunning the script.

## Docker Hub Findings

- The active Docker Hub contract is `DOCKERHUB_NAMESPACE` plus `DOCKERHUB_TOKEN`.
- `DOCKERHUB_NAMESPACE` is stored as a GitHub Variable.
- `DOCKERHUB_TOKEN` is stored as a GitHub Secret.
- The Docker token is expected to be an organization access token with repository read/write access.
- The old Docker username secret path has been removed from active workflow and script logic.
- The initializer removes the legacy Docker username secret if it exists.

## Workflow Safety

- The script asks interactively before enabling or dispatching workflow `000-bootstrap-backend.yml`.
- If the user answers no, workflow `000` is not enabled or dispatched.
- Other deployment workflows should remain disabled until explicitly enabled.
- No workflow was dispatched by this report.
- No changes were pushed by this report before this commit request.

## Recommended Next Step

Step 1: Decide whether to run workflow `000-bootstrap-backend.yml`.

The script now asks this interactively:

`Step 1: Run workflow 000-bootstrap-backend.yml for '<environment>' now? [y/N]`

If approved, run only workflow `000-bootstrap-backend.yml` for the selected environment. Do not enable or dispatch deployment workflows `100`, `200`, or `210` until the bootstrap state and secrets are confirmed.

## Validation Completed

- PowerShell parse validation passed for `scripts/Initialize-CnaGitHubSecrets.ps1`.
- Workflow YAML parsing passed.
- Terraform formatting check passed.
- Docker Hub username contract scan passed after removal from active configuration.
