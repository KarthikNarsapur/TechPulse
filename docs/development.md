# Local Development

## Prerequisites

- Python 3.12
- Node.js 22+
- Terraform 1.8+ (for infrastructure validation)
- AWS credentials only if testing against a real AWS sandbox

## Backend

From the repository root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.api:app --reload --port 8000
```

The initial API exposes `/health` and `/api/v1/technologies`. The feed storage integration is an incremental work item; the API currently reports that storage is not configured rather than pretending to return persisted records.

Run tests:

```bash
pytest ../tests
ruff check app ../tests
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL=http://127.0.0.1:8000` when running against local API. Without it, the UI uses a preview state and will not display real updates.

## Terraform validation

```bash
terraform -chdir=infrastructure/terraform init -backend=false
terraform -chdir=infrastructure/terraform validate
terraform -chdir=infrastructure/terraform fmt -check
```

A deployment package must be built before apply. Never run Terraform apply against production without reviewing the plan, environment values, IAM permissions, API authorizer, and source verification state.
