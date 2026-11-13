# Product Requirements Document (PRD): SaylientAI

Version 0.1 | Status: Draft | Owner: [Team Lead]

## 1. Problem
Freelancers often send replies that sound blunt, anxious or unprofessional when dealing with payment delays, scope creep, deadlines and disputes. This damages client relationships and income. Generic tools (grammar checkers, general chatbots) do not model politeness or face-threat in freelancer-client scenarios.

## 2. Vision
"Say It Right. Every Time." A theory-guided assistant that suggests context-appropriate replies and explains why they work, available inside the web app and, more conveniently, as a browser extension side panel.

## 3. Users
- **Primary:** freelancers (design, development, writing, VA) who communicate on Gmail, LinkedIn, Upwork, Fiverr, WhatsApp Web.
- **Secondary:** non-native English speakers who want professional tone.
- **Evaluator:** linguistics supervisor reviewing output quality.

## 4. Goals
1. Useful reply suggestion within 3 s (GPU) / 5 s (CPU demo).
2. Every suggestion includes strategy label, short explanation and politeness score.
3. One-shortcut extension flow: no tab switching, side panel only.
4. Measurable improvement over a generic prompted LLM baseline.
5. Privacy by design: user controls what is sent and stored.

## 5. Non-goals (v1)
- Auto-sending messages (user always reviews and sends manually).
- Voice, calls, mobile app.
- Screenshot / vision analysis (planned v2).
- Languages other than English output.

## 6. Features
**MVP**
- Signup/login, email verification, password reset.
- Input a message or describe a situation; scenario auto-detection.
- 3 reply options by tone (Polite, Friendly, Firm, Formal) + explanation + score.
- Copy, regenerate, feedback (thumbs + reason).
- Extension: shortcut (Ctrl+Shift+S), side panel, selected/visible text analysis.
- Opt-in history; delete history; delete account; export data.

**v1**
- Templates library (late payment, revision limit, scope change, follow-up).
- Insert reply into compose box after user confirmation.
- Dashboard with usage and scenario stats.
- Personal tone preferences.

**v2**
- Screenshot + vision analysis, more platforms, Urdu/Roman Urdu input.

## 7. User stories
- As a freelancer, I want a polite reply to a rude client message so the relationship survives.
- As a freelancer, I want to press a shortcut and see suggestions beside the page so I do not switch tabs.
- As a user, I want to know what data is sent and how long it is stored.

## 8. Acceptance criteria
- Shortcut opens side panel in under 1 s.
- Page text is read automatically while the side panel is open (panel open is the trigger — no Analyze click needed); never in the background or when the panel is closed. Suggestions appear automatically; sending/inserting always needs the user's click.
- Every response contains `strategy`, `explanation`, `score`, `replies[]`.
- Empty or invalid input returns a clear error, never a crash.
- A user can never see another user's data.

## 9. Success metrics
| Metric | Target |
|---|---|
| Linguist rating (politeness, clarity, appropriateness) | >= 4.0 / 5 |
| Improvement over baseline | >= 15% |
| Strategy classification macro-F1 | >= 0.75 |
| SUS usability score (10-15 users) | >= 70 |
| p95 latency | <= 3 s GPU / 5 s CPU |

## 10. Assumptions and dependencies
- Collaboration with English Linguistics team for theory and evaluation.
- GPU access (Colab/Kaggle) for fine-tuning.
- Chrome-based browsers for the extension.

## 11. Open questions
- Final base model size (1.5B vs 3B) based on GPU budget.
- Hosting choice for the inference service.
- Whether history storage is enabled by default (current decision: off).
