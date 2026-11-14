# Manual Dataset Guide — Saylient LLM

Apna dataset banane ke liye is file (`manual_dataset_template.csv`) ki copy mein rows add karo. Har row = 1 example. Jab tayyar ho, CSV mujhe bhej do — main ise training data mein mila dunga.

## Columns (har row mein sab bharo)

| Column | Kya likhna hai |
|---|---|
| `input` | Asli jaisa freelancer/client message (jaise client ne likha ho, ya jaisa tum likhna chahte ho) |
| `intent` | Neeche di gayi list mein se 1 (message ka maqsad) |
| `tone` | polite / warm / firm_polite / apologetic / formal / casual |
| `strategy` | negative_politeness / positive_politeness / off_record / bald_on_record |
| `sentiment` | neutral / frustrated / happy / worried / grateful |
| `formality` | 0 se 1 tak number (0 = bilkul casual, 1 = bilkul formal) |
| `face_threat_level` | low / medium / high (message kitna sensitive hai) |
| `relationship` | new_client / regular_client / difficult_client |
| `polite_rewrite` | Us message ka polite version (jaise Saylient likhega) |
| `explanation` | 1 line: ye rewrite kyun polite hai |

## Intent list (sirf ye 11 use karo)

payment_request, deadline_negotiation, scope_boundary, revision_request,
late_delivery_apology, rate_discussion, follow_up, feedback_handling,
question_how_to_ask, greeting, other

## Strategy (Brown & Levinson, sirf ye 4)

- `negative_politeness` — respect + distance ("Could you please...", "Sorry to bother...")
- `positive_politeness` — friendliness + common ground ("Glad to...", "Thanks so much!")
- `off_record` — hint, seedha na kaho ("A few more days would help...")
- `bald_on_record` — seedha aur saaf, bina ghumao ("This is my third follow-up...")

## Rules

1. Real messages likho — apni wording, apne clients jaisi situations.
2. Har intent par examples banao, sirf payment par nahi.
3. Question wale examples bhi add karo (jaise "how do I ask for payment politely?") — intent `question_how_to_ask`.
4. Koi password, email, ya asli client ka personal data mat likho.
5. Jitne marzi rows — 50 bhi theek, 500 bhi theek. Quality quantity se zyada important hai.
