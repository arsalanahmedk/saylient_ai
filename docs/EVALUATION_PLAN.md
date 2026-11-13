# Evaluation Plan

## 1. Research questions
- RQ1: Does a theory-guided, fine-tuned model produce more polite and appropriate replies than a generic prompted LLM?
- RQ2: Can the system classify the politeness strategy reliably?
- RQ3: Is the extension workflow usable and faster than copy-paste into a chatbot?

## 2. Systems compared
B1 generic prompted LLM, B2 prompted + rules engine, M1 fine-tuned, M2 fine-tuned + rules scoring (final).

## 3. Test data
Held-out test split (10%) from `DATASET_SPEC.md`, stratified by scenario and strategy, frozen before training.

## 4. Automatic metrics
- Strategy classification: precision, recall, macro-F1.
- JSON/schema validity rate.
- Reply length and readability (Flesch).
- Rule-based politeness score (hedges, please/thank, indirectness, directness markers).
- Latency (p50/p95).

## 5. Human evaluation
- Raters: >= 2 linguists + 10-15 freelancers; blind, randomized system order.
- Scale 1-5: **Politeness**, **Clarity**, **Appropriateness** (+ optional "would send as is").
- Inter-rater agreement (Krippendorff's alpha or Cohen's kappa).
- Pairwise preference between B1 and M2.

## 6. Usability study
Tasks: draft a payment reminder using (a) the extension, (b) manual copy-paste into a chatbot. Measure time, errors, SUS score.

## 7. Safety evaluation
Set of rude/manipulative/illegal-request prompts and prompt-injection cases; measure refusal/sanitization rate.

## 8. Analysis
Report means with confidence intervals; significance via Wilcoxon signed-rank (paired ratings); error analysis by scenario.

## 9. Success thresholds
Average human rating >= 4.0; >= 15% improvement over B1; macro-F1 >= 0.75; SUS >= 70.

## 10. Ethics
Participant consent, anonymized data, right to withdraw.
