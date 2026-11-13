# Changelog
All notable changes are documented here. Format: Keep a Changelog, versioning: SemVer.

## [Unreleased]
### Added
- Initial project documentation (PRD, architecture, security, roadmap).
- Phase 0–2 (2026-11-13, staging only — not pushed): FastAPI baseline in
  `apps/api` (rule-based engine `prototype-0.1` ported from the live repo,
  LLM provider adapter Gemini/Groq with rule-based fallback, `POST
  /v1/suggest` + `POST /v1/analyze`, 48 pytest tests); `docs/LLM_CHOICE.md`;
  `ml/data/seed.jsonl` (60 examples, 6 per scenario) + stratified 80/10/10
  splits; `ml/evaluation/metrics.py`; `ml/training/train_qlora.py`
  (Qwen2.5-3B-Instruct QLoRA, NOT RUN — needs Colab T4 + full dataset).
  Web app and extension are placeholders (`apps/web/NOTE.md`,
  `apps/extension/NOTE.md`) until Phases 4–5.
- Auto-analyze + auto-suggest spec (2026-11-13, docs only — not implemented,
  not pushed): extension analyzes the screen/conversation by itself when the
  side panel opens and re-analyzes on new messages; suggestions appear
  automatically. Never auto-send / never auto-insert (new FR-15). Updated
  `docs/EXTENSION_SPEC.md`, `docs/API_SPEC.md`, `docs/SRS.md` (FR-08, FR-15),
  `docs/PRD.md`, `docs/SECURITY.md`.
- API contract aligned to `docs/openapi.yaml` (Option A, 2026-11-13,
  staging only — not pushed): request field `message` -> `text`
  (max 4,000 chars), `goal` now a free string (max 300, mapped to
  engine intents internally); replies are `{tone, text}` objects (3,
  distinct tones) + `suggestion_id` (uuid) + integer `score`; analyze
  returns spec fields (`scenario`, `face_threat`, `detected_strategy`,
  `issues`); strategies are the spec enum only (engine `avoidance` ->
  `off_record` at the boundary); JSON body cap lowered to 16 KB;
  auth/history/settings/feedback/export/account recorded as phased
  endpoints (not implemented, no stubs) in `docs/API_SPEC.md`; CI
  scoped to the API job only until Phase 4 (web job removed with a
  comment). LLM adapter prompt/output updated to the new reply shape.
  Tests grew 48 -> 60 (spec-shape, free-text goal, avoidance mapping,
  16 KB cap). Also fixed while aligning: `pip install -e .[dev]` now
  works (explicit `[tool.setuptools] packages` in `pyproject.toml` —
  setuptools previously refused the flat layout), and `ruff check` +
  `bandit -r app` pass clean.
