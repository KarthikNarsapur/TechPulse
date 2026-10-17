# Deploy TechPulse through GitHub Actions

This deployment path does not require a local checkout. It is manually triggered from GitHub Actions and uses GitHub OIDC to assume an AWS IAM role; do not store long-lived AWS access keys in GitHub.

## One-time AWS setup

An AWS administrator must create an IAM role for GitHub Actions and configure its trust policy for this repository. The role ARN must be saved as the GitHub Actions secret `AWS_DEPLOY_ROLE_ARN`.

The OIDC provider must exist in the AWS account:
- Provider URL: `https://token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`

Restrict the role trust policy to this repository and the intended branch, for example:
- `repo:KarthikNarsapur/TechPulse:ref:refs/heads/feat/serverless-foundation`

For a production setup, use a protected GitHub Environment and a dedicated AWS role per environment. The deployment role needs permissions to bootstrap and manage the encrypted/versioned S3 Terraform state bucket, create/update the Terraform-managed AWS resources, publish Lambda code, upload frontend assets, and invalidate CloudFront. Start with a reviewed policy; avoid attaching AdministratorAccess as a permanent solution.

## Run a deployment

The `workflow_dispatch` workflow must exist on the repository's default branch before GitHub exposes the manual **Run workflow** button. Merge the workflow change into the default branch first; then select the deployment branch in the Actions UI.

1. Open the repository on GitHub.
2. Select **Actions** → **Deploy TechPulse to AWS**.
3. Select the deployment branch, environment `dev`, region `ap-south-1`, and action `plan`.
4. Run the workflow and inspect the uploaded Terraform plan artifact. Copy the run ID from that workflow run's URL.
5. Run the workflow again with action `apply` and enter the reviewed plan run ID in `plan_run_id`. This applies the saved plan from that run rather than silently generating a different plan.
6. Check the workflow logs for the frontend URL and API health result.

The workflow creates a versioned, encrypted, public-access-blocked S3 bucket for Terraform state, then initializes Terraform with S3 native state locking. State is separated by environment.

## Important limitations

- This workflow provisions AWS resources and may incur charges. The plan must be reviewed before applying.
- The current Terraform foundation still uses a shared Lambda execution role. Treat this as a dev bootstrap, not production-ready IAM.
- The default AI model ID and SES sender are blank; AI analysis and email notifications require separate configuration and verification.
- Cognito is configured for admin-created users only; create pilot users through the Cognito console or a separately approved admin workflow.
- Do not use the workflow for `prod` until per-function IAM roles, alarms, DLQ monitoring, source validation, live integration tests, and a reviewed deployment role policy are complete.
- Do not commit plan files, state files, AWS credentials, or notification secrets.
