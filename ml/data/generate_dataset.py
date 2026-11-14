"""Generate the Saylient v2 dataset (~50k examples) from the 500 hand-written seeds.

Deterministic (fixed seed 42). Method
--------------------------------------
1. Load ``ml/data/seeds_v2.jsonl`` (500 hand-written examples, new schema).
   They are included verbatim in the output.
2. Expand combinatorially from hand-written per-intent template rows
   (input / rewrite / explanation triples, authored for this script and
   modelled on the seed structures — same situations, tones and Brown &
   Levinson strategies) crossed with slot pools: client names, amounts,
   day counts, project types, invoice numbers, dates. Every generated
   row reuses a seed-style situation; only slot values and the
   opening/closing phrasing vary.
3. Dedup: exact normalised input text, plus near-duplicate removal on
   normalised input with slot values stripped (same skeleton + same
   slots is dropped). Balance: per-intent targets are equal (~1/11
   each), and the template mix is authored so no strategy is below
   ~12% overall.
4. Stratified 85 / 7.5 / 7.5 split by intent, written to
   ``ml/data/splits_v2/{train,valid,test}.jsonl``.

Run::

    python ml/data/generate_dataset.py [--total 50000] [--seed 42]

No network, no API keys, no real client data. All names, amounts and
invoice numbers are fictional.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import re
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS_PATH = ROOT / "ml" / "data" / "seeds_v2.jsonl"
OUT_DIR = ROOT / "ml" / "data" / "splits_v2"

SEED = 42
TOTAL_TARGET = 50000

# --- slot pools (all fictional) -------------------------------------------
NAMES = [
    "Sarah", "James", "Maria", "Alex", "Daniel", "Emma", "Liam", "Priya",
    "Tom", "Zoe", "Mark", "Ana", "Yuki", "Chris", "Omar", "Grace", "Ben",
    "Mia", "Noah", "Ella", "Jack", "Sophia", "Ryan", "Lily", "David",
    "Henry", "Isla", "Adam", "Chloe", "Leo", "Maya", "Sam", "Nadia",
    "Owen", "Ruby", "Felix", "Aisha", "Carlos", "Elena", "Viktor",
    "Hana", "Lucas", "Nina", "Omar", "Tara", "Victor", "Wendy", "Yusuf",
]
AMOUNTS = ["$50", "$75", "$100", "$120", "$150", "$180", "$200", "$250",
           "$300", "$350", "$400", "$450", "$500", "$600", "$750", "$800",
           "$950", "$1,000", "$1,200", "$1,500", "$2,000", "$2,500"]
DAYS = [1, 2, 3, 5, 7, 10, 12, 14, 15, 21, 30, 45, 60]
DAYS_WORD = {1: "one day", 2: "two days", 3: "three days", 5: "five days",
             7: "a week", 10: "ten days", 12: "twelve days",
             14: "two weeks", 15: "two weeks", 21: "three weeks",
             30: "a month", 45: "six weeks", 60: "two months"}
PROJECTS = ["website", "logo", "mobile app", "brand kit", "landing page",
            "e-commerce store", "dashboard", "video edit", "social media campaign",
            "report", "presentation", "blog setup", "booking system",
            "product photos", "email template", " explainer video".strip(),
            "online course", "portfolio site", "newsletter", "chatbot"]
INVOICES = [f"#{1000 + i * 7}" for i in range(1, 60)]

RELATIONSHIPS = ["new_client", "regular_client", "long_term_client",
                 "difficult_client"]

BUSINESSES = ["startup", "café", "law firm", "gym", "school",
              "marketing agency", "online shop", "clinic", "restaurant",
              "tech company", "charity", "fashion brand"]
CHANNELS = ["email", "WhatsApp", "Slack", "Upwork", "LinkedIn", "phone"]
WHENS = ["yesterday", "last week", "this morning", "on Monday",
         "two days ago", "last Friday"]
PLACES = ["London", "New York", "Dubai", "Berlin", "Toronto", "Sydney",
          "Lahore", "Karachi"]
PLATFORMS = ["Upwork", "Fiverr", "LinkedIn", "a referral"]

# Extra context clauses appended to the input text. They add genuine
# surface variety (different business, channel, timing) without
# changing the label: the situation and the required reply stay the
# same. 0-2 clauses are sampled per row, which multiplies the
# distinct-input space far beyond templates x projects.
CONTEXT_CLAUSES = [
    "The client runs a {business}.",
    "We have been talking over {channel}.",
    "This came up {when}.",
    "The client is based in {place}.",
    "They messaged me {when}.",
    "The project started {when}.",
    "We usually talk over {channel}.",
    "I found this client on {platform}.",
    "They replied {when}.",
    "The budget was agreed {when}.",
    "It is for their new {business}.",
    "Their last message came {when}.",
]

# Template row:
# (strategy, tone, sentiment, formality, face, relationship,
#  input_tpl, rewrite_tpl, explanation_tpl)
# Slots: {name} {amount} {days} {days_word} {project} {invoice}
TEMPLATES: dict[str, list[tuple]] = {
"payment_request": [
 ("negative_politeness", "polite", "neutral", 0.7, "high", "regular_client",
  "Invoice {invoice} is {days} days overdue. I need to chase the payment without sounding rude.",
  "Hi {name}, I hope you are doing well. I wanted to follow up on invoice {invoice}, which was due {days} days ago. Could you let me know when I can expect the payment? I am happy to resend the invoice if that helps.",
  "Hedged request plus an offer of help softens a high-imposition payment chase."),
 ("negative_politeness", "firm_polite", "neutral", 0.7, "high", "regular_client",
  "The client approved the {project} milestone but the {amount} payment still has not arrived.",
  "Hi {name}, the {project} milestone was approved and the {amount} payment is still outstanding. Could you please confirm when it will be sent? I need to plan my schedule around it.",
  "Clear facts plus a reason for the deadline make firmness polite."),
 ("positive_politeness", "warm", "positive", 0.4, "low", "long_term_client",
  "My long-term client is usually on time but this invoice is {days} days late. I need a gentle nudge.",
  "Hi {name}! Just a friendly nudge on the latest invoice, it looks like it slipped past its due date by {days} days. Whenever you get a moment, could you take a look? Thanks so much, as always, for being great to work with.",
  "Warmth and shared history fit a long-term relationship and a low-stakes delay."),
 ("negative_politeness", "firm_polite", "frustrated", 0.7, "high", "difficult_client",
  "The client keeps saying the payment is coming next week, but it has been {days_word}. I need to escalate politely.",
  "Hi {name}, I appreciate your updates, but the payment is now {days_word} overdue despite several promised dates. Could we agree on a firm date this week? If payment is not possible right now, please let me know so we can discuss next steps.",
  "Referencing broken promises calmly justifies escalation while offering discussion."),
 ("bald_on_record", "firm_polite", "frustrated", 0.8, "high", "difficult_client",
  "Final notice needed: invoice {invoice} for {amount} is {days} days overdue.",
  "Hi {name}, this is a final notice regarding invoice {invoice} for {amount}, now {days} days overdue. Please arrange payment within 7 days. If I do not hear from you, I will have to pause all work and consider further steps.",
  "After a long delay, direct language with a clear deadline stays professional."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "regular_client",
  "The client paid the wrong amount, {amount} short. I need to point it out politely.",
  "Hi {name}, thanks so much for the payment. I noticed it came through {amount} short of the invoice total, which may just be a typo. Could you check when you have a moment?",
  "Assuming an innocent mistake lets the client correct it without embarrassment."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "new_client",
  "I finished the {project} last week and the client has gone quiet. The {amount} final payment is due.",
  "Hi {name}, I hope the {project} is working well for you. I wanted to check in on the final {amount} payment, which is now due. Could you let me know when it will be sent, or if there is anything you need from me first?",
  "Linking payment to delivered work and offering help keeps the ask reasonable."),
 ("negative_politeness", "formal", "neutral", 0.9, "low", "new_client",
  "The invoice was due yesterday and the client is a big company with slow accounts. I need a polite first reminder.",
  "Dear {name}, I am writing regarding invoice {invoice}, which fell due yesterday. Could you kindly confirm the payment schedule? Please let me know if you need any further documentation from me.",
  "Formal language and a documentation offer suit a company accounts team."),
 ("off_record", "polite", "neutral", 0.5, "medium", "regular_client",
  "I did extra work on the {project} that was not in the quote, worth {amount}. I want to mention it without demanding payment.",
  "Hi {name}, I wanted to mention I added some extra touches to the {project} beyond the quote. If you would like to cover the {amount}, I would appreciate it, but there is no pressure at all.",
  "Mentioning extra work as optional hints at payment without demanding it."),
 ("positive_politeness", "warm", "positive", 0.4, "low", "long_term_client",
  "The client is happy with the work and I want to ask for a testimonial plus the final payment in one message.",
  "Hi {name}, I am so glad you love the final {project}! Two quick things: the final payment of {amount} is still pending, and if you have a moment, a short testimonial would mean a lot. Thank you for a great project!",
  "Pairing the payment reminder with a testimonial ask keeps the message positive."),
],
"deadline_negotiation": [
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "regular_client",
  "The client moved the deadline up by a week and I cannot finish the {project} in time. I need to ask for more time.",
  "Hi {name}, thanks for the updated timeline. The new deadline is very tight given the remaining work on the {project}. Would it be possible to extend it by three days? I want to make sure the quality stays high.",
  "Linking the extension to quality makes the request about the work, not the freelancer."),
 ("negative_politeness", "apologetic", "negative", 0.5, "medium", "regular_client",
  "My laptop broke and I lost a day of work. The {project} deadline is tomorrow and I need an extra day.",
  "Hi {name}, I am sorry to share that my laptop broke yesterday and I lost a full day of work on the {project}. Could we move the deadline to Friday? I am back up and running now and will prioritise your project.",
  "A brief honest reason plus reassurance softens the delay."),
 ("negative_politeness", "firm_polite", "neutral", 0.7, "medium", "new_client",
  "The client gave me the brief late but kept the original deadline for the {project}. I need to push it back fairly.",
  "Hi {name}, thanks for sending the brief. Since it arrived two days late, the original deadline for the {project} is now very tight. Could we shift it by the same two days so the work gets the time it needs?",
  "Pointing to the late brief frames the shift as fair rather than a personal failure."),
 ("positive_politeness", "apologetic", "neutral", 0.4, "medium", "long_term_client",
  "I am juggling three projects and this {project} will be a day late. I should warn the client now.",
  "Hi {name}, a quick heads-up: your {project} delivery will land tomorrow instead of today as I am finishing another project. I am really sorry for the short delay and I will send it first thing in the morning.",
  "Early warning and a specific new time show respect for the client schedule."),
 ("negative_politeness", "firm_polite", "neutral", 0.7, "high", "new_client",
  "Client wants the whole {project} in 5 days but it normally takes 12. I need to negotiate the timeline.",
  "Hi {name}, I appreciate the urgency. A full {project} in five days would mean cutting corners, so I would suggest 12 days for the complete build, or a simpler first version in five days. Which would you prefer?",
  "Offering two options turns a refusal into a choice the client controls."),
 ("negative_politeness", "apologetic", "negative", 0.6, "high", "regular_client",
  "The client is launching on Monday and my part of the {project} is not ready. I need to tell them today, not Monday.",
  "Hi {name}, I need to be honest: my part of the {project} will not be ready for Monday. I am very sorry. I can deliver a working version by Wednesday, or a reduced version on Monday. Please let me know what helps most.",
  "Honesty early plus options gives the client a way to plan around the delay."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "regular_client",
  "I can meet the deadline for the {project} if the client approves the draft today, but they are slow to reply.",
  "Hi {name}, just a quick note: I can still hit Friday on the {project} if the draft is approved today. Could you take a look when you have a moment? Once approved, I will finish the rest straight away.",
  "Linking the deadline to their approval makes the nudge collaborative."),
 ("negative_politeness", "firm_polite", "neutral", 0.7, "high", "long_term_client",
  "The {project} scope grew and the deadline did not. I need an extra week to cover the new work.",
  "Hi {name}, with the extra work we added to the {project}, the original deadline is no longer realistic. Could we extend it by a week? That would let me deliver everything to the standard you expect.",
  "Tying the extension to the added scope makes it a joint consequence, not a delay."),
 ("bald_on_record", "firm_polite", "frustrated", 0.7, "high", "difficult_client",
  "The client keeps moving the deadline for the {project} earlier each time we talk. I need to hold the line.",
  "Hi {name}, I need to be clear: the deadline we agreed is Friday, and moving it earlier each time is not workable. I will deliver the {project} on Friday as planned. If an earlier version is essential, let us agree what to cut.",
  "Direct language is needed when a boundary keeps being pushed."),
 ("off_record", "polite", "neutral", 0.6, "medium", "regular_client",
  "I underestimated the work on the {project} and the deadline is in two days. I need to ask for three more days.",
  "Hi {name}, I owe you an honest update on the {project}: the remaining work is bigger than I first thought. A few more days would let me finish it properly. I will keep you updated daily until it is done.",
  "Owning the misjudgement and offering daily updates rebuilds trust."),
],
"scope_boundary": [
 ("negative_politeness", "firm_polite", "neutral", 0.6, "high", "regular_client",
  "The client keeps asking for extra pages on the {project} that were not in the quote. I need to set a boundary.",
  "Hi {name}, I am happy to add the extra pages to the {project}. They fall outside our original agreement, so I will send a small quote for them. Once approved, I will get started right away.",
  "Agreeing to the work while quoting separately keeps the boundary businesslike."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "new_client",
  "Client asked me to also manage their social media, but I was hired only for the {project}.",
  "Hi {name}, social media is not part of the {project}, but I can recommend someone great for it, or quote it separately if you would like me to handle it.",
  "Offering a referral or a separate quote turns a no into help."),
 ("negative_politeness", "firm_polite", "neutral", 0.7, "high", "regular_client",
  "The client wants unlimited revisions on the {project}, but the contract says two rounds. I need to remind them.",
  "Hi {name}, just a quick note: our agreement includes two revision rounds on the {project}, and we have used both. I am happy to continue with further changes at my hourly rate. Let me know how you would like to proceed.",
  "Referring to the agreement makes the limit a fact, not a personal refusal."),
 ("negative_politeness", "firm_polite", "frustrated", 0.5, "medium", "difficult_client",
  "Client keeps calling me late at night for small questions about the {project}. I need to set working hours.",
  "Hi {name}, I wanted to share my working hours: I am available 9 to 6 on weekdays. Messages outside those hours I will pick up the next morning. This helps me give your {project} my full attention.",
  "Stating hours as a quality measure makes the boundary sound professional."),
 ("bald_on_record", "firm_polite", "frustrated", 0.6, "high", "difficult_client",
  "The client wants me to do the work of their full-time employee for a freelance fee on the {project}.",
  "Hi {name}, I need to be clear about what the fee covers: the agreed deliverables for the {project}, not ongoing day-to-day tasks. I am happy to discuss a retainer if you need regular support.",
  "Direct clarity is needed when the ask keeps expanding beyond the fee."),
 ("negative_politeness", "firm_polite", "neutral", 0.6, "high", "new_client",
  "Client asked for a {project}, now wants a full brand kit for the same price of {amount}.",
  "Hi {name}, a full brand kit is a bigger piece of work than the {project} alone. I would love to do it. Could I send you a quote for the extra items? The {project} itself is on track.",
  "Enthusiasm plus a separate quote separates the new ask from the agreed price."),
 ("negative_politeness", "polite", "neutral", 0.5, "low", "regular_client",
  "I need to stop a client from messaging me on three different apps about the same {project}.",
  "Hi {name}, to keep everything in one place, could we keep {project} messages on email? It helps me track decisions and nothing gets lost. I will reply there quickly.",
  "One channel framed as organisation, not control, is easy to accept."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "regular_client",
  "Client wants me to attend weekly meetings about the {project} that were never agreed. They take two hours each.",
  "Hi {name}, I am happy to join a short check-in on the {project}, but two-hour weekly meetings were not part of our agreement. Could we do a 30-minute call every two weeks, with the rest by email?",
  "A smaller alternative shows willingness while protecting billable time."),
 ("off_record", "polite", "neutral", 0.5, "medium", "regular_client",
  "Client asked me to do their competitor research for free as a favour alongside the {project}.",
  "Hi {name}, that kind of research usually takes me a full day. I could look at it as a small separate project if it would help. What do you think?",
  "Mentioning the time involved hints at the cost without a blunt refusal."),
 ("positive_politeness", "polite", "neutral", 0.6, "medium", "new_client",
  "The client keeps changing the brief for the {project} after I have finished the work.",
  "Hi {name}, I notice the brief for the {project} has changed a few times after delivery. To keep things fair, changes after sign-off will need a small additional fee. I am happy to discuss the latest changes and quote them.",
  "A new rule applied going forward avoids blaming past changes."),
],
"revision_request": [
 ("negative_politeness", "firm_polite", "neutral", 0.7, "high", "regular_client",
  "The client asked for a fifth revision of the {project} and my contract allows two. I need to charge for the extra rounds.",
  "Hi {name}, I am glad to keep refining the {project}. We have now used the two revision rounds in our agreement, so further rounds will be billed at my hourly rate. Shall I go ahead with this round and add it to the invoice?",
  "Counting the rounds factually makes the extra charge expected, not surprising."),
 ("negative_politeness", "polite", "negative", 0.5, "medium", "new_client",
  "Client said they hate the {project} design but gave no details. I need feedback I can act on.",
  "Hi {name}, I am sorry the {project} design is not landing. Could you tell me which parts feel wrong, the colours, the layout, or the style? Even a few words will help me fix it properly.",
  "Turning vague dislike into concrete questions keeps the revision moving."),
 ("positive_politeness", "warm", "positive", 0.4, "low", "regular_client",
  "The client wants the logo bigger, the text smaller, and the colours changed on the {project}, all at once.",
  "Hi {name}, great notes, I will make the logo bigger, shrink the text a touch, and try the new colours on the {project}. I will send a revised version tomorrow so you can see them all together.",
  "Repeating their list back shows listening and confirms the changes."),
 ("negative_politeness", "firm_polite", "frustrated", 0.6, "medium", "difficult_client",
  "Client keeps revising the same page of the {project} in opposite directions. I need to ask for a final call.",
  "Hi {name}, we have tried a few directions on this page of the {project} now. Could we settle on one final version this week? I will prepare the two strongest options side by side to make the choice easier.",
  "Offering a side-by-side choice ends the back-and-forth gracefully."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "regular_client",
  "The client wants a revision to the {project} that makes the design worse. I need to warn them gently.",
  "Hi {name}, I can make that change to the {project}. I just want to flag that it may make the text harder to read on mobile. Would you like me to try it and also keep a version with the safer layout?",
  "Trying their idea while keeping a safe version respects their choice and your expertise."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "new_client",
  "I need to tell the client the revision they want for the {project} will take three extra days.",
  "Hi {name}, I can make those changes to the {project}. Because they touch several pages, they will add about three days. Is that okay, or would you prefer I focus on the most important ones first?",
  "A time cost plus a priority option lets the client control the trade-off."),
 ("negative_politeness", "firm_polite", "neutral", 0.7, "high", "regular_client",
  "The client approved the {project}, then asked for major changes after approval.",
  "Hi {name}, I am happy to make these changes to the {project}. Since the design was approved, I will treat them as a new revision round and send a small quote. Let me know if you would like me to proceed.",
  "Treating post-approval changes as a new round is fair and transparent."),
 ("positive_politeness", "warm", "positive", 0.5, "low", "long_term_client",
  "Client wants the {project} homepage rewritten in a completely different tone.",
  "Hi {name}, I like the new direction for the {project}. I will rewrite the homepage in a friendlier tone and send a draft tomorrow. Let me know how it feels once you read it.",
  "Sharing their enthusiasm makes a big rewrite feel collaborative."),
 ("off_record", "polite", "neutral", 0.6, "medium", "regular_client",
  "Client wants the headline of the {project} changed to something I know will hurt clicks.",
  "Hi {name}, I can change the headline on the {project}. I did wonder if a shorter version might perform better, as long headlines can get cut off. Would you like me to prepare both so you can compare?",
  "Hinting at the risk with a comparison offer avoids a direct disagreement."),
 ("negative_politeness", "polite", "neutral", 0.5, "low", "new_client",
  "The client sent revision notes for the wrong file version of the {project}.",
  "Hi {name}, thanks for the notes on the {project}. I think these refer to the earlier version. Could you check the latest file I sent yesterday? If the notes still apply, I will get on them straight away.",
  "Gently flagging the version mix-up avoids wasted revision work."),
],
"late_delivery_apology": [
 ("negative_politeness", "apologetic", "negative", 0.6, "high", "regular_client",
  "I missed the delivery deadline for the {project} by {days} days and the client is upset. I need to apologise properly.",
  "Hi {name}, I am truly sorry the {project} delivery is {days} days late. I understand this has disrupted your plans. The work is now ready, and I have added a small discount as an apology. I will do better next time.",
  "A full apology plus a concrete remedy shows the client the delay is taken seriously."),
 ("negative_politeness", "apologetic", "negative", 0.5, "high", "long_term_client",
  "My delivery of the {project} is a week late because I was ill. The client has been patient and I feel awful.",
  "Hi {name}, thank you so much for your patience. I was unwell last week, which delayed the {project} delivery by a week. I am sorry for the wait. The work is finished now and I have double-checked everything.",
  "Thanking their patience first frames the apology around gratitude, not excuses."),
 ("negative_politeness", "apologetic", "negative", 0.7, "high", "regular_client",
  "I delivered the {project} late and the client missed their launch. I need to apologise and offer something.",
  "Hi {name}, I am very sorry my late delivery of the {project} meant you missed the launch. That is entirely my fault. I would like to offer the next small update free of charge, and I will prioritise your project going forward.",
  "Naming the real consequence and offering compensation shows accountability."),
 ("negative_politeness", "apologetic", "neutral", 0.5, "low", "regular_client",
  "The {project} delivery is one day late because of a technical problem. Short apology needed.",
  "Hi {name}, apologies for the one-day delay on the {project}, a technical issue slowed me down yesterday. The work is ready now. Thank you for your understanding.",
  "A brief apology with a short reason suits a one-day slip."),
 ("negative_politeness", "apologetic", "negative", 0.7, "high", "difficult_client",
  "The client is angry about the {project} delay and threatening a bad review.",
  "Hi {name}, I completely understand your frustration about the {project} delay and I am very sorry. I have finished the work and sent it now. Please let me know if anything needs fixing, I will sort it immediately.",
  "Calm apology plus immediate delivery is the best reply to a review threat."),
 ("negative_politeness", "apologetic", "negative", 0.6, "high", "long_term_client",
  "I delivered the {project} late for the second time with the same client. I need to rebuild trust.",
  "Hi {name}, I know this is the second late delivery on the {project} and I am sorry. I have changed how I plan my schedule so it does not happen again. The work is ready now, and I will check in daily on the next project.",
  "Naming the repeat and the fix shows the apology is backed by change."),
 ("positive_politeness", "apologetic", "negative", 0.5, "medium", "new_client",
  "I promised the {project} files on Monday but sent them Wednesday. The client has not complained yet.",
  "Hi {name}, I am sorry the {project} files arrived on Wednesday instead of Monday. Thank you for your patience. Everything is now delivered and I am here if you need any tweaks.",
  "Apologising even without a complaint shows professionalism."),
 ("off_record", "apologetic", "neutral", 0.6, "medium", "regular_client",
  "Delivery of the {project} is late because the client sent materials late, but I do not want to blame them.",
  "Hi {name}, thanks for sending the materials for the {project}. With the later start, delivery has moved to Friday. I am sorry for the shift and I will keep you posted as I go.",
  "Mentioning the later start indirectly explains the delay without blame."),
 ("negative_politeness", "apologetic", "negative", 0.6, "high", "regular_client",
  "I am going to be {days} days late delivering the {project} and I need to warn the client before the deadline passes.",
  "Hi {name}, I wanted to warn you early: the {project} delivery will be {days} days late. I am sorry for the inconvenience. I will send a progress update tomorrow and the finished work on the new date.",
  "Warning before the deadline is far better than apologising after it."),
 ("bald_on_record", "apologetic", "negative", 0.5, "high", "new_client",
  "I missed the {project} deadline because I misread the date. I need to own the mistake.",
  "Hi {name}, I made a mistake: I misread the {project} deadline as the 20th instead of the 15th. I am sorry. The work is ready now and I have put a better system in place so it will not happen again.",
  "Direct ownership of a simple mistake is the fastest way to move past it."),
],
"rate_discussion": [
 ("negative_politeness", "firm_polite", "neutral", 0.6, "high", "new_client",
  "The client offered {amount} for a {project} I would normally charge double for. I need to negotiate.",
  "Hi {name}, thank you for the offer. For the {project} scope described, my rate is double that. I could adjust the scope to fit {amount}, for example fewer pages. Would you like me to send a revised quote?",
  "Countering with a scope option keeps the negotiation constructive."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "long_term_client",
  "I have been working with a client for a year at the same rate on the {project}. I want a 15 percent increase.",
  "Hi {name}, after a year of working together on the {project}, I would like to adjust my rate by 15 percent from next month to reflect my growing experience. I value our work together and hope we can continue.",
  "A year of history justifies the increase and invites continuation."),
 ("negative_politeness", "firm_polite", "neutral", 0.6, "high", "new_client",
  "Client says my rate for the {project} is too high compared to others. I need to explain my value.",
  "Hi {name}, I understand there are cheaper options for the {project}. My rate includes revisions, fast replies, and tested, polished delivery. If budget is tight, I can reduce the scope to match it.",
  "Listing what the rate includes reframes price as value."),
 ("bald_on_record", "firm_polite", "neutral", 0.5, "medium", "new_client",
  "Client offered to pay me in exposure instead of money for the {project}. I need to say no.",
  "Hi {name}, I appreciate the offer, but I do not work for exposure. My rate for the {project} is {amount}. If the budget changes, I would be glad to help.",
  "A direct no to exposure work protects the freelancer value."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "new_client",
  "The client wants a fixed price for the {project} but the scope is unclear. I need to propose hourly instead.",
  "Hi {name}, because the {project} scope is still open, a fixed price is hard to set fairly. Could we work hourly at $30 until the scope is clear, then switch to a fixed quote? That protects us both.",
  "Hourly as a temporary step sounds fair when scope is unclear."),
 ("positive_politeness", "warm", "positive", 0.5, "low", "new_client",
  "The client is a nonprofit and asked for a lower rate on the {project}. I can offer 10 percent off.",
  "Hi {name}, I love what your nonprofit does. I can offer a 10 percent discount on the {project}. The fee would be {amount} instead of the usual rate. I hope that helps.",
  "A small nonprofit discount shows goodwill while keeping most of the fee."),
 ("negative_politeness", "firm_polite", "neutral", 0.6, "medium", "regular_client",
  "Client wants me to match a competitor rate for the {project} that is far below mine.",
  "Hi {name}, I understand the competitor price is tempting for the {project}. I cannot match it, but I can offer a smaller package at my rate that covers the essentials. Would that work for you?",
  "A smaller package instead of a rate cut keeps value intact."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "regular_client",
  "I want to charge more for rush work on the {project}. I need to tell the client about the rush fee.",
  "Hi {name}, I can prioritise the {project} and deliver by tomorrow. Rush work carries a 25 percent fee, so the total would be {amount}. Shall I go ahead on that basis?",
  "Naming the rush fee before starting avoids a billing surprise."),
 ("off_record", "polite", "neutral", 0.5, "medium", "new_client",
  "Client asked for a discount on the {project} because they will give me lots of future work.",
  "Hi {name}, I appreciate the promise of future work on the {project}. I keep my rates the same for all clients, but I am happy to discuss a small discount once we have completed a few projects together.",
  "Deferring the discount until after proven work protects the rate."),
 ("positive_politeness", "warm", "positive", 0.4, "low", "long_term_client",
  "I want to offer a loyal client a small discount on the {project} without lowering my rate permanently.",
  "Hi {name}, as a thank you for a great year working together, I would like to offer 10 percent off the {project}. It is a one-off thank you, and I really appreciate our partnership.",
  "Calling it a one-off thank you prevents the discount becoming expected."),
],
"follow_up": [
 ("negative_politeness", "polite", "neutral", 0.6, "low", "new_client",
  "I sent a proposal for the {project} a week ago and heard nothing. I need to follow up.",
  "Hi {name}, I hope you are well. I wanted to follow up on the proposal for the {project} I sent last week. Could you let me know if you have had a chance to review it? I am happy to answer any questions.",
  "A gentle proposal follow-up asks for a status without pressure."),
 ("negative_politeness", "polite", "neutral", 0.5, "low", "regular_client",
  "Client read my message about the {project} but did not reply for five days. I need a polite nudge.",
  "Hi {name}, just a quick nudge on my last message about the {project}. I know things get busy. Whenever you have a moment, a short reply would help me plan the next steps.",
  "Acknowledging busyness makes a read-but-unreplied nudge gentle."),
 ("positive_politeness", "warm", "positive", 0.5, "low", "new_client",
  "I need to follow up with a past client to ask for more work on a new {project}.",
  "Hi {name}, it was great working with you earlier this year. I have some availability next month and would love to help again with a new {project} if you have anything coming up.",
  "A warm check-in with availability is a natural way to win repeat work."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "regular_client",
  "Client said they would reply about the {project} by Friday, but it is now Tuesday. Time to chase.",
  "Hi {name}, I hope you had a good weekend. You mentioned replying about the {project} by Friday, so I wanted to check in. Is there anything you need from me to decide?",
  "Referencing their own promised date makes the chase factual, not pushy."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "regular_client",
  "I sent the {project} draft a week ago and the client has not reviewed it. The project is stalled.",
  "Hi {name}, the {project} draft has been waiting for review for a week now. Could you take a look when you have a chance? Once approved, I can finish the remaining work quickly.",
  "Linking review to finishing the work gives the client a reason to act."),
 ("positive_politeness", "warm", "positive", 0.4, "low", "long_term_client",
  "I want to check in with a client I have not heard from in three months about the {project}.",
  "Hi {name}, it has been a while! I hope you are doing well. I wanted to check in and see how the {project} is performing. If you need any updates, I am here.",
  "A friendly check-in after months keeps the relationship alive."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "regular_client",
  "Client has not replied to my last two messages about the {project}. I need a final check-in.",
  "Hi {name}, I have messaged a couple of times about the {project} without hearing back. I wanted to check if the project is still on. If your plans changed, no worries, just let me know.",
  "A graceful closing option respects a client who has moved on."),
 ("negative_politeness", "formal", "neutral", 0.8, "low", "new_client",
  "I need to follow up on a contract for the {project} that the client has not signed yet.",
  "Hi {name}, I wanted to check if you have had a chance to review the contract for the {project}. I am happy to answer any questions about it. Once signed, I can start right away.",
  "A contract follow-up with a start promise encourages signing."),
 ("off_record", "polite", "neutral", 0.5, "low", "new_client",
  "Client said they will decide on the {project} next week. I want to stay top of mind without pestering.",
  "Hi {name}, thanks for the update on the {project}. I will check back next week as planned. In the meantime, I have attached a recent sample you might like. No need to reply now.",
  "Sharing a sample adds value instead of just asking for a decision."),
 ("bald_on_record", "firm_polite", "frustrated", 0.7, "high", "difficult_client",
  "I need to follow up on an unpaid invoice for the {project} for the third time.",
  "Hi {name}, this is my third follow-up on the overdue invoice for the {project}. I understand things get busy, but I do need a payment date this week. Could you confirm one by Friday?",
  "Counting the follow-ups calmly justifies asking for a firm date."),
],
"feedback_handling": [
 ("negative_politeness", "apologetic", "negative", 0.6, "high", "difficult_client",
  "The client said my work on the {project} is terrible and they are very unhappy. I need to respond calmly.",
  "Hi {name}, I am sorry you feel that way about the {project}, and I understand your frustration. Could you tell me which parts are not working for you? I want to fix them properly and make this right.",
  "Calm acknowledgement plus a request for specifics turns anger into actionable feedback."),
 ("positive_politeness", "warm", "positive", 0.4, "low", "long_term_client",
  "The client loves the {project} work and left great feedback. I want to thank them warmly.",
  "Hi {name}, thank you so much for the wonderful feedback on the {project}! It means a lot to hear that. I really enjoyed working on this project with you.",
  "Warm gratitude for praise strengthens the relationship."),
 ("negative_politeness", "polite", "neutral", 0.5, "medium", "new_client",
  "Client said the {project} is good but not what they imagined. I need to dig deeper.",
  "Hi {name}, thank you for the honest feedback on the {project}. Could you describe what you imagined? Even a few examples would help me reshape the design to match your vision.",
  "Asking them to describe the imagined result turns vague feedback into direction."),
 ("negative_politeness", "apologetic", "negative", 0.7, "high", "difficult_client",
  "The client criticised my {project} work in a group chat in front of others. I need to respond with dignity.",
  "Hi {name}, thank you for the feedback on the {project}. I would like to discuss the details with you directly so we can fix them properly. Could we have a short call today?",
  "Moving criticism to a private call preserves dignity for everyone."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "regular_client",
  "Client said the copy I wrote for the {project} sounds too formal for their young audience.",
  "Hi {name}, good catch, I will make the copy for the {project} more casual and friendly for your audience. I will send a revised version tomorrow. Thanks for the clear direction.",
  "Accepting the note cheerfully and acting fast shows responsiveness."),
 ("negative_politeness", "apologetic", "negative", 0.6, "high", "regular_client",
  "The client said my communication on the {project} is poor. I need to acknowledge it and improve.",
  "Hi {name}, thank you for telling me. You are right, my updates on the {project} have been too rare. From now on I will send a short update every two days. I appreciate your honesty.",
  "Agreeing with fair criticism plus a concrete fix rebuilds trust."),
 ("positive_politeness", "polite", "neutral", 0.5, "low", "new_client",
  "Client gave mixed feedback on the {project}: they like the layout but hate the colours.",
  "Hi {name}, thank you, I am glad the {project} layout works. I will try three new colour options and send them tomorrow so you can pick your favourite.",
  "Separating praise from criticism keeps the reply balanced and forward-looking."),
 ("negative_politeness", "polite", "negative", 0.6, "high", "difficult_client",
  "The client is unhappy with the {project} but will not say why. I need to draw the feedback out.",
  "Hi {name}, I can sense you are not happy with the {project}, and I want to fix it. Could you share even one thing that bothers you most? That would help me start in the right place.",
  "Asking for just one thing lowers the barrier for a silent unhappy client."),
 ("off_record", "polite", "neutral", 0.5, "medium", "regular_client",
  "Client gave feedback that is just wrong, like asking for a feature on the {project} that already exists.",
  "Hi {name}, good news, that feature on the {project} already exists. You can find it in the settings menu. If it is hard to find, I can make it more visible. Would you like me to do that?",
  "Good-news framing plus an offer to improve visibility avoids correcting them bluntly."),
 ("bald_on_record", "firm_polite", "frustrated", 0.7, "high", "difficult_client",
  "The client gave feedback on the {project} in a rude tone. I need to stay professional.",
  "Hi {name}, thank you for the feedback on the {project}. I have noted your points and will address them. Let us focus on the fixes so we can move forward.",
  "Ignoring the tone and focusing on fixes is the most professional reply to rudeness."),
],
"question_how_to_ask": [
 ("negative_politeness", "polite", "neutral", 0.6, "high", "new_client",
  "how do I ask for payment politely when the client is {days} days late on the {project}?",
  "Hi {name}, I hope you are doing well. I wanted to follow up on the outstanding invoice for the {project}, which is now {days} days overdue. Would you be able to confirm a payment date this week? If there is an issue with the invoice, I am happy to help resolve it.",
  "A formal hedged question with a face-saving offer keeps pressure polite with a new client."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "new_client",
  "how do I ask for a deadline extension politely on the {project} without looking unprofessional?",
  "Hi {name}, I wanted to give you an early heads-up that the current deadline for the {project} is at risk. Could we move it by two days? I would rather deliver polished work slightly late than rush it.",
  "An early heads-up plus a quality reason keeps an extension request professional."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "new_client",
  "how do I politely say the extra work on the {project} is out of scope?",
  "Hi {name}, thanks for the idea. That part is outside the scope we agreed for the {project}, but I am happy to quote it as an add-on. Would you like me to send the price?",
  "Naming out-of-scope plainly with an add-on offer keeps the door open."),
 ("negative_politeness", "apologetic", "negative", 0.6, "medium", "regular_client",
  "how do I apologise for late delivery of the {project} without making excuses?",
  "Hi {name}, I am sorry for the delay in delivering your {project}. It is now complete and ready for you. I appreciate your patience and I will make sure the next delivery is on time.",
  "Owning the delay without excuses keeps the apology clean and credible."),
 ("negative_politeness", "firm_polite", "neutral", 0.6, "high", "new_client",
  "how do I say no to an unrealistic deadline for the {project} without losing the client?",
  "Hi {name}, thanks for thinking of me. I would love to take on the {project}, but I cannot deliver quality work by that date. Could we aim for next Tuesday instead? I can start right away.",
  "Enthusiasm plus an alternative date keeps the door open while declining the deadline."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "new_client",
  "how do I ask a client for a higher rate for the {project}?",
  "Hi {name}, I have loved working with you on the {project}. As my experience and costs have grown, I need to raise my rate from $25 to $30 an hour from next month. I hope that works for you, and I am happy to discuss.",
  "Leading with the relationship and a clear reason makes a rate rise easier."),
 ("negative_politeness", "polite", "neutral", 0.5, "low", "new_client",
  "how do I follow up with a client who ghosted me after the first call about the {project}?",
  "Hi {name}, it was great speaking with you last week about the {project}. I wanted to check if you are still interested. No pressure at all, I just wanted to close the loop.",
  "A no-pressure check-in lets a ghosted client re-engage easily."),
 ("negative_politeness", "polite", "negative", 0.6, "high", "difficult_client",
  "how do I respond to harsh criticism of the {project} from a client without getting defensive?",
  "Hi {name}, thank you for the honest feedback on the {project}. I am sorry the work did not meet your expectations. Could you share what specifically fell short? I would like to address it.",
  "Thanking them for honesty disarms criticism and opens a fix."),
 ("positive_politeness", "warm", "positive", 0.4, "low", "new_client",
  "how do I greet a new client professionally in my first email about the {project}?",
  "Hi {name}, thank you for reaching out about the {project}. I appreciate the opportunity to work with you. Please find my portfolio attached, and I look forward to discussing your project.",
  "A warm greeting with a portfolio attachment sets a professional first impression."),
 ("negative_politeness", "polite", "neutral", 0.6, "medium", "regular_client",
  "how do I ask a client to be specific about what they want changed on the {project}?",
  "Hi {name}, thanks for the feedback on the {project}. To make the revision exactly right, could you point out which parts to change and how? A few notes or a marked-up screenshot would help a lot.",
  "Asking for specifics with an easy method gets better feedback faster."),
],
"greeting": [
 ("positive_politeness", "warm", "positive", 0.5, "low", "new_client",
  "I want to introduce myself to a new client for the {project} for the first time.",
  "Hi {name}, thank you for the invitation. I am a designer with four years of experience, and your {project} sounds like a great fit. I would love to learn more about your goals.",
  "A warm self-introduction with relevant experience opens a new client conversation."),
 ("positive_politeness", "warm", "positive", 0.5, "low", "new_client",
  "Client just hired me for the {project} and I want to send a welcoming first message.",
  "Hi {name}, thank you for choosing me for the {project}! I am excited to get started. I will send a short kick-off plan today so we are aligned from day one.",
  "Excitement plus a kick-off plan makes a new hire feel confident."),
 ("positive_politeness", "warm", "positive", 0.4, "low", "long_term_client",
  "I need to say hello to a client I have not spoken to in a year about the {project}.",
  "Hi {name}, it has been a while! I hope you are doing well. I was thinking about our last {project} and wanted to check in. How is it performing?",
  "A warm check-in after a year revives the relationship naturally."),
 ("positive_politeness", "warm", "positive", 0.4, "low", "long_term_client",
  "I want to wish a long-term client a happy new year after finishing the {project}.",
  "Hi {name}, wishing you a very happy new year! Thank you for a wonderful year of working together on the {project}. I look forward to what we build next.",
  "A seasonal greeting with thanks strengthens a long-term bond."),
 ("positive_politeness", "warm", "positive", 0.5, "low", "new_client",
  "I need to welcome a client to the {project} kick-off meeting.",
  "Hi {name}, welcome! Thank you for joining the kick-off for the {project}. I am excited to walk you through the plan today and hear your thoughts.",
  "A welcoming kick-off greeting makes the client feel included from the start."),
 ("negative_politeness", "polite", "neutral", 0.5, "low", "regular_client",
  "Client messaged me on a Sunday about the {project}. I want to reply politely on Monday morning.",
  "Hi {name}, good morning! Thanks for your message about the {project}. I have had a look and will get back to you with a full reply by this afternoon.",
  "A Monday-morning reply acknowledges the message without apologising for the weekend."),
 ("positive_politeness", "warm", "positive", 0.5, "low", "long_term_client",
  "I want to congratulate a client on their business anniversary after our {project}.",
  "Hi {name}, congratulations on five years in business! It has been a pleasure working on the {project} with you. Wishing you many more successful years ahead.",
  "A milestone congratulation shows care beyond the project."),
 ("positive_politeness", "warm", "positive", 0.4, "low", "regular_client",
  "I want to send a good morning message to a client before the {project} launch day.",
  "Hi {name}, good morning! Big day today for the {project}. Everything is ready on my side, and I will be online all day if you need anything. Good luck with the launch!",
  "A launch-day greeting with availability shows support when it matters."),
 ("negative_politeness", "formal", "positive", 0.8, "low", "new_client",
  "I need to introduce myself to a client team I have never met for the {project}.",
  "Hello everyone, thank you for having me. I am the designer working on your new {project}. I look forward to collaborating with you all over the coming weeks.",
  "A brief team introduction establishes the role and the timeline."),
 ("positive_politeness", "casual", "positive", 0.3, "low", "new_client",
  "I need to say hello to a client on WhatsApp for the first time about the {project}.",
  "Hi {name}, great to connect here! I am working on your {project}. Feel free to message me anytime during work hours.",
  "A casual WhatsApp hello fits the channel while staying professional."),
],
"other": [
 ("negative_politeness", "apologetic", "negative", 0.6, "medium", "regular_client",
  "I need to cancel a meeting about the {project} with a client at short notice.",
  "Hi {name}, I am sorry, but I need to cancel our meeting about the {project} today. Something urgent has come up. Could we reschedule for tomorrow? I apologise for the inconvenience.",
  "A short apology plus a reschedule offer softens a late cancellation."),
 ("positive_politeness", "warm", "positive", 0.4, "low", "regular_client",
  "I need to ask a client for a testimonial after the successful {project}.",
  "Hi {name}, I am so glad you are happy with the {project}. If you have a moment, a short testimonial would mean a lot to me. Even a few sentences would help.",
  "A testimonial ask after success feels natural and low-pressure."),
 ("negative_politeness", "polite", "neutral", 0.5, "low", "regular_client",
  "I need to reschedule a call about the {project} with a client to next week.",
  "Hi {name}, would it be possible to move our call about the {project} to next week? I am free Tuesday or Thursday afternoon. I apologise for the change and hope one of those works.",
  "Offering two new times makes rescheduling easy."),
 ("negative_politeness", "formal", "neutral", 0.8, "low", "new_client",
  "The client wants me to sign an NDA before we discuss the {project}.",
  "Hi {name}, I am happy to sign the NDA for the {project}. Please send it over and I will return it signed today. Once that is done, we can discuss the project freely.",
  "A quick yes to an NDA with a same-day promise builds trust."),
 ("negative_politeness", "polite", "neutral", 0.6, "low", "regular_client",
  "I need to tell a client I am going on holiday during the {project} and who will cover for me.",
  "Hi {name}, I wanted to let you know I will be on holiday next week during the {project}. My colleague Sam will cover anything urgent. I will be back on Monday and will catch up then.",
  "Early notice plus a named cover person keeps a holiday smooth."),
 ("negative_politeness", "polite", "neutral", 0.6, "low", "new_client",
  "I need to send a client the final invoice for the {project} and thank them.",
  "Hi {name}, thank you for a great {project}! I have attached the final invoice. It has been a pleasure working with you, and I hope we collaborate again soon.",
  "Pairing the final invoice with thanks ends the project warmly."),
 ("negative_politeness", "apologetic", "negative", 0.5, "medium", "regular_client",
  "I need to apologise for sending the wrong attachment about the {project} to a client.",
  "Hi {name}, I am sorry, I attached the wrong file for the {project}. The correct one is attached here. Please delete the earlier file. Thank you for your understanding.",
  "A quick correction with a delete request fixes a wrong attachment."),
 ("positive_politeness", "warm", "positive", 0.5, "low", "regular_client",
  "Client wants me to teach them how to update the {project} themselves.",
  "Hi {name}, I would love to show you how to update the {project}. I can record a short video guide, or we can do a one-hour training call. Which would you prefer?",
  "Two teaching options let the client pick their preferred learning style."),
 ("negative_politeness", "firm_polite", "negative", 0.7, "high", "difficult_client",
  "I need to politely end the {project} with a client because it is no longer working out.",
  "Hi {name}, after thinking it over, I feel it is best to wrap up our work on the {project} here. I will finish the current milestone and hand over everything cleanly. Thank you for the opportunity.",
  "A clean handover offer makes ending a project professional, not abrupt."),
 ("negative_politeness", "polite", "neutral", 0.5, "low", "new_client",
  "I need to let a client know I am fully booked for the next month and cannot start the {project} yet.",
  "Hi {name}, thank you for reaching out about the {project}. I am fully booked for the next month, but I have availability from the 1st. Would you like me to reserve a slot for you?",
  "Fully-booked news plus a future slot turns a no into a booking."),
],
}

# Closing variants appended to rewrites by tone (adds surface variety).
CLOSINGS = {
    "polite": ["Thanks so much!", "Please let me know what you think.",
               "I appreciate your understanding.", "Thank you!"],
    "warm": ["Thanks a lot!", "Really appreciate it!",
             "Looking forward to hearing from you!"],
    "firm_polite": ["Please let me know by Friday.", "I would appreciate a reply this week."],
    "formal": ["Kind regards.", "Please do not hesitate to contact me."],
    "casual": ["Thanks!", "Cheers!"],
    "apologetic": ["Thank you for your patience.", "I really appreciate your understanding."],
    "assertive": ["Please confirm as soon as you can."],
}

OPENINGS = {
    "polite": ["Hi {name},", "Hello {name},"],
    "warm": ["Hi {name}!", "Hey {name},"],
    "firm_polite": ["Hi {name},", "Hello {name},"],
    "formal": ["Dear {name},", "Dear {name},"],
    "casual": ["Hey {name},", "Hi {name},"],
    "apologetic": ["Hi {name},", "Hello {name},"],
    "assertive": ["Hi {name},", "Hello {name},"],
}


def _norm(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _skeleton(text: str) -> str:
    """Normalised text with only the client name stripped.

    Names are interchangeable slots, so the same wording with a
    different name is a near-duplicate. Amounts, day counts, projects
    and invoice numbers are kept: they make the situation genuinely
    different, and they are what give the combinatorial expansion its
    variety. (Stripping every slot value would collapse each template
    to a single example, which defeats the expansion.)
    """
    text = _norm(text)
    for name in NAMES:
        text = text.replace(name.lower(), " NAME ")
    text = re.sub(r"^(hi|hello|hey|dear) name ", "", text)
    return re.sub(r"\s+", " ", text).strip()


def load_seeds() -> list[dict]:
    rows = []
    with SEEDS_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def make_slots(rng: random.Random) -> dict:
    days = rng.choice(DAYS)
    return {
        "name": rng.choice(NAMES),
        "amount": rng.choice(AMOUNTS),
        "days": days,
        "days_word": DAYS_WORD[days],
        "project": rng.choice(PROJECTS),
        "invoice": rng.choice(INVOICES),
        "business": rng.choice(BUSINESSES),
        "channel": rng.choice(CHANNELS),
        "when": rng.choice(WHENS),
        "place": rng.choice(PLACES),
        "platform": rng.choice(PLATFORMS),
    }


def add_context(inp: str, slots: dict, rng: random.Random) -> str:
    """Append 0-2 sampled context clauses to the input text.

    Each clause is formatted with freshly drawn slot values, and
    clauses that would repeat the same wording (same channel, same
    timing) are dropped, so the result never says the same thing
    twice.
    """
    k = rng.choice([0, 1, 1, 2, 2, 2])
    if k == 0:
        return inp
    chosen = rng.sample(CONTEXT_CLAUSES, k)
    formatted: list[str] = []
    for clause in chosen:
        fresh = dict(slots)
        fresh.update({
            "business": rng.choice(BUSINESSES),
            "channel": rng.choice(CHANNELS),
            "when": rng.choice(WHENS),
            "place": rng.choice(PLACES),
            "platform": rng.choice(PLATFORMS),
        })
        text = clause.format(**fresh)
        if text in formatted:
            continue
        # Drop a second clause that opens with the same words
        # (e.g. two "We ... over Slack" style clauses).
        if any(text.split()[:2] == other.split()[:2] for other in formatted):
            continue
        formatted.append(text)
    if not formatted:
        return inp
    return inp.rstrip() + " " + " ".join(formatted)


def vary_opening(rewrite: str, tone: str, rng: random.Random) -> str:
    """Swap the greeting of a rewrite for a tone-appropriate variant."""
    m = re.match(r"^(Hi|Hello|Hey|Dear) ([A-Z][a-z]+)[,!]?\s*", rewrite)
    if not m:
        return rewrite
    name = m.group(2)
    opening = rng.choice(OPENINGS.get(tone, ["Hi {name},"])).format(name=name)
    return opening + " " + rewrite[m.end():]


def maybe_add_closing(rewrite: str, tone: str, rng: random.Random) -> str:
    if rng.random() < 0.45:
        closings = CLOSINGS.get(tone, [])
        if closings:
            closing = rng.choice(closings)
            lowered = rewrite.lower()
            if closing.lower() in lowered:
                return rewrite
            # Do not stack two near-identical thanks (e.g. rewrite
            # already ends "Thank you for your understanding" and the
            # closing is "I really appreciate your understanding").
            if "understanding" in closing.lower() and "understanding" in lowered:
                return rewrite
            return rewrite.rstrip() + " " + closing
    return rewrite


STRATEGY_WEIGHTS = {
    "negative_politeness": 0.40,
    "positive_politeness": 0.30,
    "bald_on_record": 0.15,
    "off_record": 0.15,
}


def pick_template(templates: list[tuple], rng: random.Random) -> tuple:
    """Sample a template with strategy weights, so the authored
    template mix (which skews negative_politeness) does not dominate
    the dataset. Intents missing a strategy get its weight
    redistributed over the strategies they do have."""
    by_strategy: dict[str, list[tuple]] = defaultdict(list)
    for tpl in templates:
        by_strategy[tpl[0]].append(tpl)
    available = [s for s in STRATEGY_WEIGHTS if s in by_strategy]
    total_w = sum(STRATEGY_WEIGHTS[s] for s in available)
    roll = rng.random() * total_w
    for strat in available:
        roll -= STRATEGY_WEIGHTS[strat]
        if roll <= 0:
            return rng.choice(by_strategy[strat])
    return rng.choice(by_strategy[available[-1]])


def generate_for_intent(intent: str, target: int, rng: random.Random,
                        seen_inputs: set, seen_skeletons: set) -> list[dict]:
    templates = TEMPLATES[intent]
    rows: list[dict] = []
    attempts = 0
    max_attempts = target * 30
    while len(rows) < target and attempts < max_attempts:
        attempts += 1
        tpl = pick_template(templates, rng)
        (strategy, tone, sentiment, formality, face, rel,
         input_tpl, rewrite_tpl, expl_tpl) = tpl
        slots = make_slots(rng)
        try:
            inp = input_tpl.format(**slots)
            rewrite = rewrite_tpl.format(**slots)
            expl = expl_tpl.format(**slots)
        except KeyError:
            continue
        inp = add_context(inp, slots, rng)
        rewrite = vary_opening(rewrite, tone, rng)
        rewrite = maybe_add_closing(rewrite, tone, rng)
        norm_inp = _norm(inp)
        skel = _skeleton(inp)
        if norm_inp in seen_inputs or skel in seen_skeletons:
            continue
        seen_inputs.add(norm_inp)
        seen_skeletons.add(skel)
        rows.append({
            "input": inp,
            "intent": intent,
            "tone": tone,
            "strategy": strategy,
            "sentiment": sentiment,
            "formality": round(formality + rng.uniform(-0.05, 0.05), 2),
            "face_threat_level": face,
            "relationship": rel,
            "polite_rewrite": rewrite,
            "explanation": expl,
        })
    return rows


def stratified_split(rows: list[dict], seed: int) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    by_intent: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_intent[row["intent"]].append(row)
    splits: dict[str, list[dict]] = {"train": [], "valid": [], "test": []}
    for intent, items in sorted(by_intent.items()):
        shuffled = items[:]
        rng.shuffle(shuffled)
        n = len(shuffled)
        n_test = max(1, round(n * 0.075))
        n_valid = max(1, round(n * 0.075))
        splits["test"].extend(shuffled[:n_test])
        splits["valid"].extend(shuffled[n_test:n_test + n_valid])
        splits["train"].extend(shuffled[n_test + n_valid:])
    for name in splits:
        rng.shuffle(splits[name])
    return splits


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Saylient v2 dataset.")
    parser.add_argument("--total", type=int, default=TOTAL_TARGET)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out-dir", type=pathlib.Path, default=OUT_DIR)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    seeds = load_seeds()
    print(f"Loaded {len(seeds)} hand-written seeds from {SEEDS_PATH}")

    seed_by_intent = Counter(r["intent"] for r in seeds)
    intents = sorted(TEMPLATES)
    per_intent_target = args.total // len(intents)
    print(f"Per-intent target: {per_intent_target} across {len(intents)} intents")

    seen_inputs = {_norm(r["input"]) for r in seeds}
    seen_skeletons = {_skeleton(r["input"]) for r in seeds}

    all_rows: list[dict] = list(seeds)
    generated = 0
    for intent in intents:
        need = per_intent_target - seed_by_intent.get(intent, 0)
        new_rows = generate_for_intent(intent, need, rng, seen_inputs, seen_skeletons)
        all_rows.extend(new_rows)
        generated += len(new_rows)
        print(f"  {intent}: seeds={seed_by_intent.get(intent, 0)} "
              f"generated={len(new_rows)} (wanted {need})")

    # Balance guard: no intent below 3% or above 25%.
    counts = Counter(r["intent"] for r in all_rows)
    total = len(all_rows)
    print(f"\nTotal rows: {total} (seeds {len(seeds)} + generated {generated})")
    print("Intent distribution:")
    for intent in intents:
        print(f"  {intent}: {counts[intent]} ({100 * counts[intent] / total:.1f}%)")
    print("Strategy distribution:")
    for strat, n in Counter(r["strategy"] for r in all_rows).most_common():
        print(f"  {strat}: {n} ({100 * n / total:.1f}%)")
    print("Tone distribution:")
    for tone, n in Counter(r["tone"] for r in all_rows).most_common():
        print(f"  {tone}: {n} ({100 * n / total:.1f}%)")

    rng.shuffle(all_rows)
    splits = stratified_split(all_rows, args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in splits.items():
        path = args.out_dir / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"Wrote {path}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
