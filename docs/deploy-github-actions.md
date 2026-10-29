# Deploy TechPulse through GitHub Actions

TechPulse has two deployment workflows. Both use GitHub OIDC to assume an AWS IAM role; do not store long-lived AWS access keys in GitHub.

| Workflow | Trigger | What it does |
|---|---|---|
| **Deploy TechPulse code** (`deploy-code.yml`) | A pull request merged into `main` (or a manual run) | Runs lint and tests on the merged commit, publishes Lambda code and the frontend to the existing `dev` environment, and checks API health. Never runs `terraform apply`. |
| **Provision TechPulse infrastructure** (`deploy-aws.yml`) | Manual only | `terraform apply` for a new environment, or `destroy`. Apply refuses an environment that already exists unless `existing_environment_change` is enabled. |

## Day-to-day flow

1. Push changes to the `dev` branch. CI runs on every push.
2. Open a pull request from `dev` into `main` and wait for CI to pass.
3. Merge the pull request. **Deploy TechPulse code** runs automatically.
4. Check the run: it reports pending Terraform changes as a warning (they are not applied), publishes all five Lambda functions, deploys the frontend, and verifies `/health`.

If the run warns that Terraform changes are pending (for example, a changed IAM policy or Lambda environment variable), review them and apply them deliberately with the infrastructure workflow and the override.

## Set up a new environment

1. Select **Actions** → **Provision TechPulse infrastructure** → **Run workflow**.
2. Choose action `apply`, the environment, and region `ap-south-1`. Leave `existing_environment_change` off.
3. The workflow bootstraps the encrypted, versioned Terraform state bucket, plans and applies in the same run, publishes code and the frontend, and checks health. Read the plan in the run log.

The `workflow_dispatch` button only appears for workflows on the default branch.

## One-time AWS and GitHub setup

- The OIDC provider must exist in the AWS account (`https://token.actions.githubusercontent.com`, audience `sts.amazonaws.com`).
- Save the deployment role ARN as the GitHub secret `AWS_DEPLOY_ROLE_ARN`. Both workflows run in the GitHub environment `dev`, so the role trust policy must allow the subject `repo:KarthikNarsapur/TechPulse:environment:dev`.
- Frontend deploys need `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.
- Protect `main` (**Settings → Branches → Add rule**): require a pull request before merging and require the CI checks to pass, so code only reaches AWS through a reviewed merge.

## Important limitations

- Only the `dev` environment is wired into continuous deployment.
- The Terraform foundation still uses a shared Lambda execution role. Treat this as a dev bootstrap, not production-ready IAM.
- SES and the workspace relevance provider require separate configuration and verification; see `CLAUDE.md`.
- Do not commit plan files, state files, AWS credentials, or notification secrets.
