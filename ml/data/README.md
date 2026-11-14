# Dataset — Saylient v2 (Phase 3)

Two datasets live here. The **v1 seed** (`seed.jsonl`, 60 examples, old
schema) is kept for history and for the rule-engine baseline. The
**v2 dataset** is the training set for Arsalan's own fine-tuned
politeness LLM: **99,990 examples** built from 700 hand-written seeds
plus deterministic combinatorial expansion.

## v2 files

| File | Rows | Description |
|---|---|---|
| `seeds_v2.jsonl` | 700 | Hand-written seed examples, new schema. question_how_to_ask: 90; others 53–65 each. |
| `generate_dataset.py` | — | Deterministic generator (seed 42): 165 hand-written template rows (15 per intent) × slot pools (72 names, 36 amounts, 20 day counts, 40 project types, 59 invoice numbers, 20 context clauses) × strategy-weighted sampling. |
| `splits_v2/train.jsonl` | 84,986 | 85% of the full set, stratified by intent. **Not pushed to GitHub** (about 55 MB — too big for one contents-API call); reproducible exactly from `seeds_v2.jsonl` + `generate_dataset.py`. A 2,000-row sample is pushed as `splits_v2/train_sample_2000.jsonl`. |
| `splits_v2/valid.jsonl` | 7,502 | 7.5%, stratified by intent. |
| `splits_v2/test.jsonl` | 7,502 | 7.5%, stratified by intent. **Never used in training** — not for fitting, not for prompt selection, not for checkpoint choice. |

Regenerate (deterministic — same seed, same output):

```bash
python ml/data/generate_dataset.py --total 100000 --seed 42
```

## v3 expansion (14 Nov 2026)

The dataset grew from 49,995 to 99,990 rows: 200 more hand-written
seeds (total 700, heavy on `question_how_to_ask` — 40 new — and
difficult-client cases), 55 new generator templates (10 → 15 per
intent, including more `off_record` and `bald_on_record` situations),
and expanded slot pools (48 → 72 names, 22 → 36 amounts, 13 → 20 day
counts, 20 → 40 project types, 12 → 20 context clauses). Keyword
baseline on the new test split (7,502 rows): intent accuracy **0.392**,
strategy accuracy **0.447** (majority class), formality MAE **0.108** —
lower than the v2 baseline (0.464 / 0.490 / 0.098) because the more
varied inputs defeat the keyword list, not because the data is worse.
The fine-tuned model must beat 0.392 / 0.447 / 0.108.

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
message itself. 9,090 of the 99,990 rows (9.1%) are questions.

## Label balance (full 99,990 rows)

Intents are equal by construction (~9,090 each, 9.1% — none below 3%
or above 25%):

| Intent | Rows | % |
|---|---|---|
| payment_request | 9,090 | 9.1 |
| deadline_negotiation | 9,090 | 9.1 |
| scope_boundary | 9,090 | 9.1 |
| revision_request | 9,090 | 9.1 |
| late_delivery_apology | 9,090 | 9.1 |
| rate_discussion | 9,090 | 9.1 |
| follow_up | 9,090 | 9.1 |
| feedback_handling | 9,090 | 9.1 |
| question_how_to_ask | 9,090 | 9.1 |
| greeting | 9,090 | 9.1 |
| other | 9,090 | 9.1 |

Strategies (strategy-weighted sampling in the generator):

| Strategy | Rows | % |
|---|---|---|
| negative_politeness | 44,882 | 44.9 |
| positive_politeness | 31,581 | 31.6 |
| off_record | 12,518 | 12.5 |
| bald_on_record | 11,009 | 11.0 |

Tones: polite 34.6%, warm 26.0%, firm_polite 18.8%, apologetic 14.7%,
formal 5.1%, casual 0.7%.

## Dedup

- Exact duplicates: removed on normalised input text (lowercased,
  punctuation/whitespace collapsed).
- Near-duplicates: removed when the normalised input matches after
  stripping only the client name (names are interchangeable slots).
  Amounts, day counts, projects and invoice numbers are kept as
  distinguishing content — they make the situation genuinely different.
- Spot-check (20 random rows, seed 7, v3 set): 20/20 coherent, labels
  match the situation, rewrites polite and on-topic. Known minor slot
  artifacts (same class as v2): occasional article slip ("a online
  shop"), an opening swap that leaves a lowercase continuation
  ("Hi Bilal! as a thank you..."), and two platform context clauses in
  one input. Two redundancy bugs found in the first v2 check (repeated
  channel/timing clause, stacked "thank you for your understanding")
  were fixed in the generator and the set regenerated.

## Labelling notes

- **No real data.** No real names, emails, phone numbers, invoice
  numbers from real clients, or pasted real conversations. All names
  (`Sarah`, `James`, …), amounts and invoice numbers are fictional.
- **Seeds are hand-written; expansion is template-based, not
  LLM-generated.** The 165 generator template rows were authored from
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
