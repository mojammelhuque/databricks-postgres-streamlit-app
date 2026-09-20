# Branching Strategy & CI/CD Pipeline

> How code flows from development to production in this repository.

---

## Branch Structure

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Feature    │  ──▶   │     Dev     │  ──▶   │    Main     │
│  Branches    │  PR    │  (Testing)  │  PR    │ (Production)│
│  feature/*   │        │             │        │             │
└─────────────┘         └─────────────┘         └─────────────┘
   Development           Integration              Production Deploy
```

### Branch Rules

| Branch | Purpose | Protection | Deploy |
|--------|---------|------------|--------|
| `main` | Production-ready code | Protected: require PR review, CI must pass | Auto-deploy on merge |
| `dev` | Integration & testing | Protected: CI must pass | No deploy |
| `feature/*` | Individual features | None | No deploy |

---

## CI/CD Pipeline Flow

### Stage 1: CI (Continuous Integration)

**Trigger**: Push to `dev` or PR opened to `main`

**Steps**:
1. Checkout code
2. Set up Python 3.11
3. Install dependencies
4. Lint with flake8
5. Validate Streamlit app imports (ast parsing)
6. Validate app.yaml structure
7. Check for hardcoded secrets

**Pass criteria**: All steps must pass with exit code 0.

### Stage 2: CD (Continuous Deployment)

**Trigger**: PR merged from `dev` to `main`

**Steps**:
1. Checkout code
2. Set up Python 3.11
3. Install Databricks CLI
4. Configure Databricks CLI with secrets
5. Deploy app to Databricks Apps
6. Generate deployment summary

**Required GitHub Secrets**:

| Secret Name | Description |
|-------------|-------------|
| `DATABRICKS_HOST` | Your Databricks workspace URL |
| `DATABRICKS_TOKEN` | Your Databricks personal access token |
| `DATABRICKS_APP_NAME` | The Databricks App name to deploy |

---

## Developer Workflow

### Step 1: Create a Feature Branch

```bash
git checkout dev
git pull origin dev
git checkout -b feature/add-new-dashboard
```

### Step 2: Make Changes and Commit

```bash
git add .
git commit -m "feat: add new production dashboard page"
```

### Step 3: Push and Create PR to Dev

```bash
git push origin feature/add-new-dashboard
# Create PR: feature/add-new-dashboard -> dev
```

### Step 4: Review and Merge to Dev

After CI passes on the PR, merge to `dev`:

```bash
git checkout dev
git pull origin dev
git merge feature/add-new-dashboard
git push origin dev
```

### Step 5: Create PR from Dev to Main

```bash
# Create PR: dev -> main
# CI runs again on the PR
# After review, merge the PR
# CD pipeline auto-deploys to production
```

---

## Branch Protection Rules (Recommended)

### Main Branch

- Require pull request before merging
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Require conversation resolution before merging
- Do not allow force pushes
- Do not allow deletions

### Dev Branch

- Require status checks to pass before merging
- Do not allow force pushes

### How to Set Up in GitHub

1. Go to: Settings > Branches > Add branch protection rule
2. Branch name pattern: `main`
3. Enable: Require pull request before merging (1 approval)
4. Enable: Require status checks to pass
5. Select required checks: `CI - Lint and Test`
6. Enable: Require branches to be up to date
7. Save changes
8. Repeat for `dev` branch (optional: skip approval requirement)

---

## GitHub Actions Workflow File

The CI/CD pipeline is defined in `.github/workflows/ci-cd.yml`.

### Workflow Triggers

| Event | Branch | Jobs Run |
|------|--------|----------|
| Push | `dev` | CI (lint, test, validate) |
| PR opened/updated | `main` | CI (lint, test, validate) |
| PR merged | `main` | CD (deploy to Databricks) |
| Manual dispatch | Any | CI + CD (selected environment) |

---

## Rollback Procedure

If a deployment fails or causes issues:

1. Revert the merge commit on `main`:
```bash
git checkout main
git revert <merge-commit-sha>
git push origin main
```

2. The revert triggers a new CD pipeline that deploys the previous version.

3. Alternatively, manually redeploy from the last known good commit:
```bash
# Using Databricks CLI
databricks apps deploy <app-name> --source-path ./app
```

---

## Environment Promotion Summary

```
Developer                Dev Branch              Main Branch              Production
   │                        │                       │                      │
   │  commit & push         │                       │                      │
   ├───────────────────────▶│                       │                      │
   │                        │  CI: lint & test      │                      │
   │                        ├──────────────────────▶│                      │
   │                        │  PR: dev -> main      │                      │
   │                        │  CI runs again        │                      │
   │                        │                       │  CD: deploy          │
   │                        │                       ├─────────────────────▶│
   │                        │                       │                      │  App live!
   │                        │                       │                      │
```