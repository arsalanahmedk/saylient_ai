# Dataset — Saylient v2 (Phase 3)

Two datasets live here. The **v1 seed** (`seed.jsonl`, 60 examples, old
schema) is kept for history and for the rule-engine baseline. The
**v2 dataset** is the training set for Arsalan's own fine-tuned
politeness LLM: **49,995 examples** built from 500 hand-written seeds
plus deterministic combinatorial expansion.

## v2 files

| File | Rows | Description |
|---|---|---|
| `seeds_v2.jsonl` | 500 | Hand-written seed examples, new schema. Every intent ~45 examples (question_how_to_ask: 50). |
| `generate_dataset.py` | — | Deterministic generator (seed 42): 110 hand-written template rows (10 per intent) × slot pools (48 names, 22 amounts, 13 day counts, 20 project types, 59 invoice numbers, 12 context clauses) × strategy-weighted sampling. |
| `splits_v2/train.jsonl` | 42,493 | 85% of the full set, stratified by intent. |
| `splits_v2/valid.jsonl` | 3,751 | 7.5%, stratified by intent. |
| `splits_v2/test.jsonl` | 3,751 | 7.5%, stratified by intent. **Never used in training** — not for fitting, not for prompt selection, not for checkpoint choice. |

Regenerate (deterministic — same seed, same output):

```bash
python ml/data/generate_dataset.py --total 50000 --seed 42
```

## v2 schema (one JSON object per line)

```json
{
  "input": "Invoice #1048 is 12 days overdue. I need to chase the payment without sounding rude.",
  "intent": "payment_request",
  "tone": "polite",
  "strategy": "negative_politeness",
  "sentiment": "neutral",
  "formality": 0.7,
  "face_threat_level": "high",
  "relationship": "regular_client",
  "polite_rewrite": "Hi Sarah, I hope you are doing well. I wanted to follow up on invoice #1048 ...",
  "explanation": "Hedged request plus an offer of help softens a high-imposition payment chase."
}
```

| Field | Values |
|---|---|
| `input` | The freelancer's situation, in their own words — a realistic freelancer↔client message, or a question about how to phrase something (see `question_how_to_ask`). |
| `intent` | `payment_request` \| `deadline_negotiation` \| `scope_boundary` \| `revision_request` \| `late_delivery_apology` \| `rate_discussion` \| `follow_up` \| `feedback_handling` \| `question_how_to_ask` \| `greeting` \| `other` |
| `tone` | `polite` \| `firm_polite` \| `warm` \| `formal` \| `casual` \| `apologetic` \| `assertive` |
| `strategy` | Brown & Levinson (1987): `positive_politeness` \| `negative_politeness` \| `bald_on_record` \| `off_record` |
| `sentiment` | `positive` \| `neutral` \| `negative` \| `frustrated` |
| `formality` | 0–1 score (0 = very casual, 1 = very formal) |
| `face_threat_level` | `low` \| `medium` \| `high` (Brown & Levinson W = Distance + Power + Imposition) |
| `relationship` | `new_client` \| `regular_client` \| `long_term_client` \| `difficult_client` |
| `polite_rewrite` | The polite reply the freelancer should send (or, for `question_how_to_ask`, the suggested phrasing). |
| `explanation` | One short sentence: why this strategy/tone fits. |

### Question-style examples

`question_how_to_ask` rows are questions a freelancer asks the
assistant (e.g. `"how do I ask for payment politely when the client is
12 days late?"`). Their `polite_rewrite` is the suggested phrasing to
send, so the fine-tuned model learns to detect question intent and
answer with a usable message instead of treating the question as the
message itself. 4,545 of the 49,995 rows (9.1%) are questions.

## Label balance (full 49,995 rows)

Intents are equal by construction (~4,545 each, 9.1% — none below 3%
or above 25%):

| Intent | Rows | % |
|---|---|---|
| payment_request | 4,545 | 9.1 |
| deadline_negotiation | 4,545 | 9.1 |
| scope_boundary | 4,545 | 9.1 |
| revision_request | 4,545 | 9.1 |
| late_delivery_apology | 4,545 | 9.1 |
| rate_discussion | 4,545 | 9.1 |
| follow_up | 4,545 | 9.1 |
| feedback_handling | 4,545 | 9.1 |
| question_how_to_ask | 4,545 | 9.1 |
| greeting | 4,545 | 9.1 |
| other | 4,545 | 9.1 |

Strategies (strategy-weighted sampling in the generator):

| Strategy | Rows | % |
|---|---|---|
| negative_politeness | 23,328 | 46.7 |
| positive_politeness | 16,201 | 32.4 |
| off_record | 5,637 | 11.3 |
| bald_on_record | 4,829 | 9.7 |

Tones: polite 37.4%, warm 22.8%, firm_polite 18.6%, apologetic 16.6%,
formal 4.1%, casual 0.6%.

## Dedup

- Exact duplicates: removed on normalised input text (lowercased,
  punctuation/whitespace collapsed).
- Near-duplicates: removed when the normalised input matches after
  stripping only the client name (names are interchangeable slots).
  Amounts, day counts, projects and invoice numbers are kept as
  distinguishing content — they make the situation genuinely different.
- Spot-check (20 random train rows, seed 7): 20/20 coherent, labels
  match the situation, rewrites polite and on-topic. Two redundancy
  bugs found in the first check (repeated channel/timing clause,
  stacked "thank you for your understanding") were fixed in the
  generator and the set regenerated.

## Labelling notes

- **No real data.** No real names, emails, phone numbers, invoice
  numbers from real clients, or pasted real conversations. All names
  (`Sarah`, `James`, …), amounts and invoice numbers are fictional.
- **Seeds are hand-written; expansion is template-based, not
  LLM-generated.** The 110 generator template rows were authored from
  the seed structures. No synthetic example was bulk-accepted from an
  LLM.
- **Quality > quantity.** A wrong-strategy example teaches the model
  the wrong mapping; delete a doubtful example rather than keep it.
- **Toxic / biased samples:** filter out any example that is abusive,
  threatening, deceptive, or that stereotypes a protected group.

## v1 seed (kept for the baseline)

`seed.jsonl` is the original 60-example seed in the old schema
(`scenario`, `context{relationship, imposition}`, `input`, `strategy`,
`reply`, `explanation`, `tone`) with splits in `splits/` (train 40 /
val 10 / test 10). It is used by `ml/evaluation/metrics.py` for the
rule-engine baseline only — it is **not** part of v2 training.
