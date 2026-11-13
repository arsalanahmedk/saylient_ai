# Threat Model

Method: STRIDE on the data flow in `ARCHITECTURE.md`.

## Assets
User accounts and tokens, message content, history, model weights, dataset, API keys, service tokens.

## Trust boundaries
Browser/page content (untrusted) -> extension -> API -> inference service -> database.

## Threats and mitigations
| ID | Threat | Category | Mitigation |
|---|---|---|---|
| T1 | Stolen access token reused | Spoofing | Short expiry, refresh rotation, revocation on logout |
| T2 | Credential stuffing / brute force | Spoofing | Rate limits, backoff, breached-password check |
| T3 | User reads another user's history (IDOR) | Info disclosure | `user_id` scoping, automated ownership tests |
| T4 | Malicious page text injects instructions into the model | Tampering | Data/instruction separation, delimiters, output schema validation |
| T5 | Model leaks system prompt or data | Info disclosure | No secrets in prompts, output filters, no cross-user context |
| T6 | Direct access to inference service | Elevation | Private network, service token, firewall |
| T7 | XSS via rendered page text in side panel | Tampering | `textContent` only, strict CSP |
| T8 | Malicious extension update / supply chain | Tampering | Lockfiles, audits, 2FA on store and repo accounts |
| T9 | DB breach exposes messages | Info disclosure | App-level encryption, minimal retention, key rotation |
| T10 | Abuse / spam / cost exhaustion | DoS | Quotas, captcha on signup, timeouts, max tokens |
| T11 | Training-data poisoning | Tampering | Source tracking, review, frozen test set |
| T12 | Sensitive field captured by extension | Info disclosure | Skip password/payment inputs, PII redaction, explicit trigger |
| T13 | Log leakage of content | Info disclosure | Content-free structured logs, Sentry scrubbing |
| T14 | Replay of extension token from another origin | Spoofing | Origin checks, short TTL, token bound to extension ID |

## Residual risks
Novel prompt-injection techniques, model hallucination of facts. Mitigated by user review before sending and continuous testing.

## Review cadence
Revisit before each release and after any architecture change.
