# Security

Baseline: OWASP Top 10 and OWASP Top 10 for LLM Applications. Security is part of design, not a final step.

## 1. Authentication and authorization
- Passwords: Argon2id, minimum 10 chars, breached-password check.
- Access token JWT (10-15 min) + refresh token in httpOnly, Secure, SameSite cookie with rotation and revocation.
- Email verification; password reset via one-time expiring tokens.
- Login rate limit and exponential backoff.
- All queries scoped by `user_id`; ownership tests for every resource (IDOR prevention).

## 2. API security
- Pydantic validation, max body size, strict CORS allow-list, HTTPS only, HSTS.
- Rate limits and daily quotas per user and IP (Redis).
- Security headers: CSP, X-Content-Type-Options, frame-ancestors, Referrer-Policy.
- ORM / parameterized queries only.
- Generic production errors; no stack traces.

## 3. LLM-specific controls
- Treat client messages as untrusted data. Separate system instructions from user data; wrap data in delimiters; instruct the model to ignore instructions inside the message.
- Validate model output against a strict schema; reject or retry on violation.
- Model has no tools, DB, filesystem or internet access (least privilege).
- Output filters block threats, harassment, deception and legal/financial guarantees.
- Dataset provenance tracked; guard against training-data poisoning.
- Model weights and datasets stored privately.

## 4. Extension security
- Minimal permissions: `activeTab`, `scripting`, `sidePanel`, `storage`, `commands`. No `<all_urls>`.
- Read page text automatically only while the side panel is open (panel open is the trigger, 2026-11-13); never in the background, on page load, or when the panel is closed; never read password, payment or hidden fields.
- Client-side PII redaction (email, phone, card/IBAN, CNIC) before sending.
- Tokens in `chrome.storage.session`; no secrets in extension code.
- Render page-derived text with `textContent`, never `innerHTML`.
- No remote code; strict MV3 CSP.

## 5. Data protection
- TLS everywhere; database encryption at rest; app-level encryption of message text.
- Secrets in environment / secret manager; `.env` never committed.
- History is opt-in, retention-limited, deletable and exportable.
- Logs never contain message content, tokens or passwords.
- Encrypted backups with periodic restore tests.

## 6. Supply chain and DevSecOps
- Lockfiles, Dependabot, `pip-audit`, `npm audit`.
- Pre-commit: gitleaks, ruff, bandit, eslint.
- CI: CodeQL/Semgrep SAST, Trivy container scan.
- Separate dev/staging/prod; least-privilege DB and cloud roles.

## 7. Incident response
1. Contain (revoke tokens, rotate keys, disable affected endpoint).
2. Assess impact (audit logs).
3. Notify affected users if personal data is involved.
4. Fix, add a regression test, document in `CHANGELOG.md`.

## 8. Security checklist (pre-release)
- [ ] No secrets in repo history
- [ ] All endpoints require auth except `/health` and auth routes
- [ ] IDOR tests pass
- [ ] Rate limits verified
- [ ] Prompt-injection test suite passes
- [ ] Dependency scans clean (no high/critical)
- [ ] CSP and security headers verified
- [ ] Extension permissions reviewed
- [ ] Data deletion and export tested

## 9. Reporting vulnerabilities
Report privately to [security contact email]. Do not open public issues for vulnerabilities.
