# Roadmap (16 weeks)

| Phase | Weeks | Goals | Deliverables |
|---|---|---|---|
| 0. Setup | 1 | Repo, CI skeleton, doc templates, scope approval | Repo, PRD approved |
| 1. Theory + dataset design | 2-3 | Scenario taxonomy, strategy labels, annotation guide | `DATASET_SPEC.md` final, first 300 examples |
| 2. Baseline + backend | 3-5 | FastAPI, PostgreSQL, auth, rate limiting; prompted baseline + rules engine | API skeleton, baseline B1/B2 |
| 3. Dataset + fine-tuning | 5-8 | Dataset 1,500+, QLoRA training, quantization, inference service | `saylient-v0.1` model |
| 4. Web app | 6-9 | Landing redesign, dashboard, history, settings, templates, legal pages | Web app MVP |
| 5. Extension | 8-11 | MV3, shortcut, side panel, extractor, redaction, auth, API link | Extension MVP |
| 6. Hardening + testing | 11-13 | Threat model review, OWASP checks, IDOR/injection tests, e2e | Security report, test report |
| 7. Evaluation | 13-15 | Automatic metrics, linguist + user study, SUS | Evaluation results |
| 8. Deploy + defense | 15-16 | Production deploy, final report, demo, slides | Final report, demo video |

## Milestones
- **M1 (W3):** taxonomy + 300 examples + baseline running
- **M2 (W8):** fine-tuned model served behind the API
- **M3 (W11):** web app + extension working end to end
- **M4 (W13):** security checklist complete
- **M5 (W16):** final defense

## Weekly routine
Monday planning, mid-week check-in with supervisor/linguists, Friday demo + risk review (`RISK_REGISTER.md`).

## Definition of done
Code reviewed and merged, tests pass, docs updated, no secrets, security checklist items touched are re-verified.

## Backlog (v2)
Screenshot + vision analysis, Roman Urdu/Urdu input, more platforms, mobile app, personalization.
