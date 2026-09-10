# STAGE 3 — GITHUB DEPLOY v4.1

Deploy these files to the ROOT of the Yorkie Insights repository, preserving paths.

Critical source path expected by the workflow:
api/insights/latest.json

Do NOT upload this ZIP itself as the final repository content.
Its contents must exist as normal repository files/directories.

This stage intentionally does NOT configure secrets and does NOT claim production activation.

Required next gate after repository upload:
1. `.github/workflows/yorkie-insights-email.yml` exists in the repository.
2. `scripts/validate_payload.py` exists.
3. GitHub Actions recognizes the workflow.
4. No secret values are present in committed files.

Only after those checks pass should Gmail-related repository secrets be configured.
