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

1. Open the repository on GitHub.
2. Select **Actions** → **Deploy TechPulse to AWS**.
3. Select environment `dev`, region `ap-south-1`, and action `plan`.
4. Run the workflow and inspect the uploaded Terraform plan artifact.
5. If the plan is expected, run the workflow again with action `apply`.
6. Check the workflow summary/logs for the frontend URL and API health result.

The workflow creates a versioned, encrypted, public-access-blocked S3 bucket for Terraform state, then initializes Terraform with S3 native state locking. State is separated by environment.

## Important limitations

- This workflow provisions AWS resources and may incur charges. The plan must be reviewed before applying.
- The current Terraform foundation still uses a shared Lambda execution role. Treat this as a dev bootstrap, not production-ready IAM.
- The default AI model ID and SES sender are blank; AI analysis and email notifications require separate configuration and verification.
- Cognito is configured for admin-created users only; create pilot users through the Cognito console or a separately approved admin workflow.
- Do not use the workflow for `prod` until per-function IAM roles, alarms, DLQ monitoring, source validation, live integration tests, and a reviewed deployment role policy are complete.
- Do not commit plan files, state files, AWS credentials, or notification secrets.
