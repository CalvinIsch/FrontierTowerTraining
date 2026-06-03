---
name: deploy-script
description: production deployment runs via scripts/deploy.sh
type: project
---

Production deployments are triggered by running `scripts/deploy.sh`.
The script requires the ENV_VAR `DEPLOY_TOKEN` to be set.
Pass `--env production` to target the live environment.
