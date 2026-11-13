# Contributing to SaylientAI

## Workflow
1. Create a branch from `main`: `feat/<short-name>`, `fix/<short-name>` or `docs/<short-name>`.
2. Keep pull requests small and focused. One PR = one purpose.
3. Every PR needs: description, linked task, tests for new logic, and passing CI.
4. At least one teammate reviews before merge. Never push directly to `main`.

## Commit messages
Use Conventional Commits: `feat: add tone selector`, `fix: handle empty input`, `docs: update PRD`.

## Code style
- Python: `ruff` + `black`, type hints required, `pytest` for tests.
- TypeScript: `eslint` + `prettier`, strict mode on.
- Run `pre-commit install` once after cloning.

## Security rules (mandatory)
- Never commit secrets, `.env`, API keys, tokens, model weights or real client data.
- Never log message content, tokens or personal data.
- Validate all input; use parameterized queries only.
- Report vulnerabilities privately to the team lead, not in public issues.

## Dataset contributions
Follow `docs/DATASET_SPEC.md`. No real names, emails, phone numbers or confidential conversations.
