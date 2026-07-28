# AI as a Legitimate Assistant at Every Stage of Digital Critical Editing

**Draft outline — short paper + 20-min talk (slide deck to follow)**
**Author:** Troy A. Griffitts (VMRCRE / NTVMR, INTF Münster)
**Date:** 2026-07-01
**Venue:** 13th International Congress of Coptic Studies, Göttingen, 27 Jul – 1 Aug 2026
  · track **"Coptology and Digital Humanities"** · **20 min + 5 min discussion** ·
  abstract **~200 words** (submission deadline 31 Dec 2025 — already accepted; now
  building talk/paper).
**Audience:** Coptic-studies scholars, *not* NT textual critics — they **are** an
  under-served manuscript tradition. **Lead pole = access/equity** (AI reaches
  labour-starved traditions like theirs); governance = the rigorous backbone;
  sustainability (Göttingen Academy funds CoptOT) = the returning-funder note. Hook:
  the platform already hosts them at `coptot.manuscriptroom.com`.
**Source material:** `ai-transcription-community-fit.md`, `problems-in-focus.md`,
`transcription-states.md`, `endpoint-transcript-generate-fromimage.md`, and session
notes on collation, RTL editing, and the secrets-service design.

> **Thesis.** We set out to research a single question: *can AI be a legitimate
> **assisting** tool at every stage of producing a critical edition?* Our field —
> collaborative digital editing of the Greek New Testament — decomposes into **12
> discrete stages**. This paper walks the pipeline, reports where AI already helps and
> where it doesn't yet, and draws the governance lessons that let AI **assist every
> stage without *owning* any result above the human line.** *Assist everywhere;
> author nothing that becomes the edition.* Those lessons generalize to any
> expert pipeline with stages of varying judgment-depth.

---

## Abstract (FINAL — submitted)

**Title:** *AI integration with collaborative digital tools for critical editions*

The workflow for editing the Digital Edition of the Coptic Old Testament consists of 11
discrete stages — from cataloguing, to imaging, indexing, transcribing, collating,
regularizing, to reconstructing the textual history. This session explores our
adventures integrating AI with 6 stages of this workflow as a proof of concept to answer
the question: can AI be a legitimate assistant at every stage in a way which actually
improves our editing experience and without eroding the accountability that makes an
edition authoritative? We'll give a realtime demonstration of our live integration
points into the Virtual Manuscript Room Collaborative Research Environment and discuss
our lessons learned along the way.

> **Framing locked by the submitted abstract — propagate through the talk/deck:**
> - **Pipeline = 11 stages** (public). This is our internal 12 minus **Teststellen**
>   (folded out; this audience doesn't need it). 11 = cataloguing · imaging · indexing ·
>   transcribing · reconciling · collating · regularizing · setting variant units ·
>   ordering reading priority · versional evidence · reconstructing textual history
>   (CBGM).
> - **6 integrated as PoC** (the ★ stages): indexing · transcribing · collating ·
>   regularizing · setting variant units · versional evidence. (CBGM = the not-yet /
>   next target; reconciling + ordering-priority = human-reserved.)
> - **Question refined:** not just *can* AI assist, but assist **in a way that actually
>   improves the editing experience** *and* preserves accountability. Two tests, not one.
> - **Format:** a **realtime live demo** of the integration points (the Ps.22.2
>   collation before/after + regularization gate we captured) + **lessons learned**.
>   Conclusions are deliberately left for the session (teaser abstract).
> - Renumber the §1 stage table to 11 (drop Teststellen row) when building the deck.

---

## 0. Framing (~1 page) — what our world is, and why the pipeline matters

- **The problem domain, briefly, for a general audience.** A critical edition
  reconstructs the earliest recoverable text of a work surviving in many hand-copied
  witnesses (for the Greek NT: ~5,000 manuscripts, no two identical). The *Editio
  Critica Maior* (ECM) is that edition; the VMRCRE / NTVMR is the collaborative online
  platform that produces it, with a global volunteer community and 70+ contributing
  projects.
- **The key idea a general reader should take away: this is a *pipeline of distinct
  intellectual tasks*, not one monolithic act of "editing."** Each stage has its own
  skills, tools, and — crucially — its own *depth of scholarly judgment*. That is
  exactly what makes it a good laboratory for AI: you can ask, stage by stage, "is AI
  legitimately helpful *here*?" and get 12 different, honest answers.
- **The founding design principle (carries through the whole paper): mechanism
  design.** The platform is built so the path of least resistance for a self-interested
  scholar — "study the manuscripts I care about" — is *also* the path that enriches
  the shared research dataset the whole community draws on. AI is simply the newest tool
  a scholar carries through the door;
  the platform's job is unchanged: **enable**. Friction is the enemy.
- **Why this generalizes.** Medicine, law, scientific data curation — any field with a
  multi-stage expert pipeline, a provenance/trust substrate, and a
  scarce-expertise bottleneck faces the same question we do. Our stage-by-stage answer
  is a transferable template.

## 0.5 Positioning at ICCS XIII — the AI/DH conversation already in the room (1 slide)

*Name the neighbors, then stand cleanly apart. There is an active AI subcommunity at
this congress; our niche is the gap between its poles.*

- **AI as a Coptic *model/engine*** — So Miyagawa, *THOTH AI 2.0 / Coptic Composer AI*
  (built on Claude Opus + RAG; SOTA BLEU/METEOR/ROUGE for Coptic↔English) and an
  LLM-for-Coptic tutorial; Díaz Hernández, NLP treebanks for pre-Coptic Egyptian. These
  build the *capability*.
- **AI as *cultural risk*** — Mena Basta, *"Prompting the ⲡⲛⲉⲩⲙⲁ"*: generative AI's
  "hallucinated orthodoxy," a call for "digital asceticism." Takes the *danger*
  seriously.
- **AI inside a *collaborative editing workflow*** — Lincke, Vanderheyden & Cowey,
  *AI-Assisted Workflow for papyri.info*: OCR → editor → **"the voting process that
  precedes publication."** The closest sibling — a review gate before the commons.
- **Funding vocabulary is live here** — Naether et al., dictionaries as Linked Open
  Data under **DFG Text+ / NFDI**. Our sustainability pitch (§7) speaks this language.

- **Our distinct contribution.** We build neither a Coptic model nor a critique. We
  offer the **governance model** that sits between Miyagawa's utility and Basta's
  caution: take AI's usefulness seriously *and* answer "hallucinated orthodoxy"
  concretely — AI as a named, accountable member with a hard ceiling (*assist
  everywhere; author nothing that becomes the edition*). papyri.info's "voting before
  publication" is exactly our tier/review economy, generalized into a trust economy
  that spans human and machine contributors and a bring-your-own-key funding model.
  *We are the platform that already hosts CoptOT — the audience are potential members.*

## 1. The 12 stages, and where AI stands today (the map — 1 page + table)

*This table is the paper's backbone and the deck's hero slide.* Star = AI has been
applied and it works; the rest are frontier or deliberately human.

| # | Stage | AI applied? | One-line role of AI at this stage |
|---|---|---|---|
| 1 | Cataloging | — | metadata extraction from catalog prose; duplicate-identity reconciliation |
| 2 | Imaging | — | enhancement / layout & region detection; multispectral read-through |
| 3 | Indexing | ★ **robust** | identify page content (e.g. "Psalm 22") — reliable *even when transcription is subpar* |
| 4 | Teststellen (Text und Textwert) | — | select test passages & classify witnesses — *domain-specific; not elaborated for this audience* |
| 5 | Transcribing | ★ *contested* | assistive first-pass seed from the image; quality varies by model, scholars will challenge |
| 6 | Reconciling | — (reserved) | *assists*: surface transcriber disagreement; never owns the merged result |
| 7 | Collating | ★ | align witnesses — **incl. LXX↔Coptic**, which the old engine structurally cannot do |
| 8 | Regularizing | ★ | normalize orthographic / abbreviation noise before the apparatus |
| 9 | Setting variant units | ★ | propose variation-unit (column-group) boundaries |
| 10 | Ordering reading priority | — (reserved) | *assists*: propose local stemma; scholar decides the Ausgangstext |
| 11 | Versional evidence | ★ Coptic *demonstrated* | semantic cross-language alignment (LXX/Latin/Syriac ↔ target); Coptic works today |
| 12 | CBGM | ★ = **to do before the congress** | coherence-assisted local stemmata / textual flow (cf. Gerd Mink) |

- **The map's punchline.** The un-starred stages are *not random*. They fall into two
  clean groups: **front-of-pipeline physical/infrastructural** work (cataloging,
  imaging) we simply haven't reached, and the **deep editorial-judgment core**
  (reconciling, ordering reading priority, CBGM) that the governance model *reserves*
  for human authority. Where AI hasn't entered, it's either "not yet" or "by design" —
  and the design boundary is legible on this map.
- **"Assist ≠ own."** Reconciling and ordering-priority still show AI *assisting*
  (disagreement signals, proposed local stemmata) — the human keeps authorship. This
  is the concrete face of the tier ceiling (§4).

## 2. Walking the pipeline — what worked, what didn't (2 pages)

*Grouped into three bands. Each stage: what AI does, the win, the failure/pitfall, the
lesson.*

### Band A — stages where AI already earns its place (the successes)

- **Collating (7) — the headline win, and it's a *Coptic* win.** The traditional engine
  (CollateX, character/token alignment) is excellent within one language but **produces
  nothing usable across languages** — the lesson stated precisely: *not "bad," but
  zero.* An LLM doing *semantic* alignment aligns across languages and handles
  transposition, nomina sacra, and multiple hands as separate witnesses, emitting
  structured JSON. **Concretely for this room: collation between the LXX (Greek
  Septuagint) and the Coptic works well** — running today on `coptot.manuscriptroom.com`
  through the same API. AI does the one thing the old tool structurally could not, at
  exactly the Greek↔Coptic boundary Coptic OT scholars live on. *(This is the money
  slide — a real, live Coptic result, not a Greek demo.)*
  - *Sub-lesson:* you can't split "linguistic" from "mechanical" work — the merge
    decision (*tapis* = *mat*) *is* linguistic, so alignment + merge + regularization
    happen in one shot. And: over-split beats wrong-merge (splitting a unit is a
    right-click; un-merging means re-collating).
  - *The gate this stage taught us (→ §6 pilot lesson):* the AI will silently **drop
    tokens, invent tokens, or change the witness's actual words** while producing
    fluent output — so collation output is validated against the input for exactly
    those three failure modes before it is ever trusted.
- **Versional evidence (11) — the highest-leverage win, and Coptic is *demonstrated*.**
  Precisely because the human specialist pool for Coptic/Syriac/Ethiopic is tiny, AI's
  cross-language semantic alignment matters *most* here — and the LXX↔Coptic collation
  above is exactly this stage, working now. The strategic tension elsewhere — *the place
  AI helps most is the place we can vouch for it least* — is being **retired
  language-by-language**: Coptic is validated in practice; Syriac/Ethiopic remain the
  next gates (§4, per-language validation). For this audience that's the honest and
  flattering message: *your* tradition is where it already works.
- **Indexing (3) — a robust, honest win, *decoupled from transcription quality*.**
  Definitively, some models reliably identify *what biblical content is on a page*
  (e.g. "this is Psalm 22") **even when their transcription of it is subpar.** This is
  the paper's stage-decomposition thesis vindicated in one fact: a model can *fail*
  stage 5 and still *pass* stage 3 — so "is AI useful?" genuinely has different answers
  per stage, and indexing is a stage where the answer is a confident yes. High value in
  practice: a mis-indexed page is invisible to the scholars who could work on it;
  getting the *identification* right unlocks the manuscript even before a good
  transcription exists.
- **Transcribing (5) — useful with some models, but *contested*; do not headline.**
  `transcript/generate/fromimage` turns a blank page into a seed + an invitation to
  judge, and some models produce genuinely helpful first passes. But **scholars will
  (rightly) challenge transcription quality** — so present it honestly as *assistive
  seeding*, not solved. The community's verb shifts from *transcribe-from-nothing* to
  *correct-and-promote* — lower activation energy — and the honest posture (subpar
  drafts still have value as a starting point, and as the indexing signal above) is
  more persuasive to this audience than an accuracy claim they'll contest.
- **Regularizing (8) & Setting variant units (9).** AI proposes the normalization and
  the unit boundaries; the editor adjusts in the UI. Bias the AI toward over-splitting.
  - **Regularizing is a two-tier task, and the tiers demand different machinery
    (2026-07-05, live on `variant/apparatus/suggest/regularizations`).** The
    *mechanical* tier — bracket/underdot "unclear/supplied" confirmations,
    diacritic-only differences — is generated **deterministically** (string
    comparison, no model); the AI is called only for the *linguistic residue*:
    itacisms, nomina sacra, contextual nonsense (fehler), elision. **This split is
    Coptic-born:** the CoptOT team's UI already divided suggestions into a
    bulk-acceptable "Simple Diacritic" group vs. individually-reviewed linguistic
    cards — their UX instinct anticipated the governance split by years. *(Nice
    ICCS beat: a design your community shaped now structures the AI integration.)*
  - **The killer empirical fact (Titus.1.2, MOTB Greek Paul, 344 witnesses):** the
    deterministic tier finds **38** mechanical rules in **102 ms for free**; the
    earlier all-AI run had found only **34 of those same 38** — the frontier model
    *silently missed four bracket-stripping cases that string comparison cannot
    miss*. Meanwhile the AI residue is just **4-5 suggestions** (~$0.19 with prompt
    cache vs $0.32 all-AI), every one requiring genuine Greek: e.g. `ον→ην` fehler
    ("masculine relative has no feminine antecedent"), `θς̣→θεος` nomen sacrum.
    The expensive tokens now buy *only judgment*, never bracket-stripping.
  - **The boundary case that proves the boundary is real:** 088's
    `επη̣γ̣γ̣[ιλατο]` — stripping the marks mechanically reaches only `επηγγιλατο`;
    the remaining `ι`/`ει` itacism *requires linguistic judgment*. The mechanical
    tier stops exactly where judgment starts, and both rules are offered — the
    editor picks. The mechanical/linguistic line isn't rhetoric; it's legible in a
    single word.
  - **Determinism as a feature, observed:** across repeated runs at temperature 0
    (with thinking), the AI residue varies by ±1 suggestion (an `η(ν)→ην`
    expansion came and went); the deterministic 38 never vary. Another concrete
    argument for pushing everything mechanizable below the model.
  - **Setting variant units (9), same thesis from the other side (50-verse ECM
    Matthew replay vs. the human editor's gold states):** prompt iteration bought
    *precision* (spurious overlap rows 44→6) but detection plateaued ~65% until we
    enriched the *input* deterministically — exact transposition flags, whole-verse
    om/lac rosters — which jumped overlap agreement 0.42→0.63. **Moving
    intelligence into deterministic input beats prompt-tuning**, and it helps the
    *cheaper* model most. Boundary-F1 ~0.88 = ~7 of 8 unit boundaries pre-drawn
    right: strong as a *suggestion* engine, wrong as an auto-setter — the numbers
    themselves argue assist-not-own.
- **A free byproduct across all of Band A: a self-labeling research corpus.** Every
  generation is persisted at `ai/<engine-model>/…` with full `(engine, model, params)`
  provenance; **human adoption is the label.** Editors pursuing their own editions
  produce, for free, the dataset that tells us which model/prompt to trust for which
  language/script/hand.

### Band B — stages deliberately reserved for human authority (the ceiling, made concrete)

- **Reconciling (6)** and **Ordering reading priority (10)** are where scholarly
  authorship lives. AI *assists* — multiple AI seeds turn reconciliation's diff into a
  "here are the hard spots" signal; AI can propose a local stemma — but the human owns
  the result. This is not a limitation we regret; **it is the values statement of the
  edition** (§4): *AI accelerates the floor of the work; human scholars own the ceiling
  — what becomes the edition.*

### Band C — the frontier (not yet, and the pre-congress target)

- **Cataloging (1) & Imaging (2)** — front-of-pipeline, different modality, simply not
  reached yet. Sketch the obvious AI roles (metadata extraction, layout/region
  detection, image enhancement).
- **CBGM (12) — the live target "before the congress" (cf. Gerd Mink).** The
  Coherence-Based Genealogical Method is already computational; AI's candidate
  contribution is at the *local-stemma / reading-priority* layer that feeds it — the
  same judgment as stage 10, one scale up. State with appropriate humility: this is the
  next experiment, not a result.

## 3. The cross-cutting pitfalls — where *integration itself* bites (1 page)

*Not stage-specific — these are platform-level, and every one has the same shape: a
mechanism built for a human-only world collides with AI's arrival.*

- **The impersonation-guard collision (flagship story).** Giving the AI its own
  `userID` (`claude`, `gemini`) is what makes it a *member*. But the anti-impersonation
  guard exists precisely to stop a caller saving under a `userID` that isn't theirs.
  Result: the transcription tool worked **only for admins** — it silently locked out
  Drew Longacre and every non-admin, the model never even called. *The security control
  and the community-design goal were in direct, invisible conflict.* Fix: write to a
  **shared engine namespace** `ai/<engine-model>/`, which is nobody's human identity —
  so it was never impersonation.
- **The personal-key hack = live financial exposure.** One API key in
  `sysconfig.properties` — the maintainer's own, personally paid — and the
  `AI: Collation` role enforced *nowhere*, so a collation user falls through to
  spending the maintainer's money with no gate. Transcription grew the *guard* but one
  fixed key; collation grew *key resolution* but no guard — each subsystem built the
  opposite half.
- **A trust ladder that encodes a value judgment as a bug.** The stop-gap
  `CONFIDENCETIER` hard-codes *all humans above all AI*, so a first-week student
  outranks a strong model at high confidence. The correct axis is *reliable >
  unreliable*, which cuts across the human/machine line.
- **Accreted muddiness AI forced us to face.** 15 years of a live system: transcription
  "state" encoded as *file location*; a lost `statusMask` makes the top tier a
  singleton only INTF can hold; `"PUBLISHED"` is a magic string; the DB `TRANSCRIPTION`
  column literally holds `"repo:yes"`. AI didn't create this — it made the latent mess
  *load-bearing*.
- **Key-leak history.** A real incident — seven API keys once staged into git by
  filename. BYOK raises the stakes of exactly this; it shapes the secrets design (§5).

## 3.5 The hinge — how AI joins a *contribution* ethos (½ page; frames §4–§5)

*The platform's ethos is contribution-by-mechanism-design: self-interest, channeled
through shared infrastructure, becomes public good. The central question — how do you
bring AI into a culture built to **encourage and incentivize contribution**? — has one
answer expressed as five moves. §4 (membership) and §5 (BYOK) are its two mechanisms.*

1. **Same citizenship, not a guest pass.** AI takes a `userID` and the same contract
   every human accepts — attributed, reviewed, ranked, reported on. No parallel "AI
   mode"; extend the membership that already exists.
2. **It enriches the shared research dataset.** BYOK lets a scholar spend their *own* AI
   budget on the manuscripts they study; the AI-assisted results enrich the **shared
   research dataset** — the manuscripts, images, transcriptions, and collations the
   platform hosts — that **many teams** draw on for their own projects, editions, and
   publications (CoptOT, the INTF's ECM, and dozens more), not one edition alone. The AI
   contribution feeds a common *resource*, not any team's edition and not "scholarship";
   self-interested research stocks the shared dataset, and that reuse *is* the community
   benefit.
   *(Framing notes, not talk points: avoid the trigger "public data." And don't claim
   the contributor controls release of the AI output — an AI seed lives in a shared
   namespace by design; the visibility axis governs the scholar's own human work, not
   the seed. Keep both distinctions implementation-level; don't belabor either.)*
3. **The valued contribution shifts to judgment.** Correct-and-promote. If promoting an
   AI seed counts in your profile like keyboarding it yourself (the scholarly judgment
   is the valuable part), AI *grows* the contributor pool instead of displacing it —
   the years-unclaimed blank page becomes a five-minute "fix three letters and accept."
4. **Contribution gains a second currency: expertise *or* compute.** You've always
   contributed labor and skill; now also the AI budget you spend on the manuscripts you
   care about. Same commons, same ethos, new resource (and the sustainability story).
5. **The trust economy is the immune system that makes it safe.** AI's eager-to-please
   failure mode (§6 lesson 1) means unvetted output could *degrade* the commons, so the
   same review/provenance/trust machinery that governs humans governs AI — validation
   as admission ritual, the tier ceiling, full audit. Self-interest supplies the
   energy; the institutions supply the regulation. **AI amplifies the energy, so the
   regulation matters more, not less.**

> **One line:** AI enters the contribution ethos not as a tool bolted to the side but
> as a *new member and a new currency* — held to the same citizenship terms, restocking
> the commons it draws from, and amplifying human contribution rather than replacing it.

## 4. Making the AI a *member* of the community (1 page)

- **The central move: the AI is a member, not infrastructure** — it gets a `userID` in
  the same namespace as human scholars. The community already knows how to handle
  members (review, credit, rank, report); **no new social structure is invented.**
- **Accountable, not merely credited.** Every call lands in `AI_USAGE_LOG` with full
  provenance; reputation is earned per `engine+model+language`, on evidence.
- **The trust axis was always there.** Contributors have always ranged from students to
  world-class experts; trust was managed *socially* via reconciliation. AI doesn't add
  the axis — it makes it **impossible to keep tacit**. One scale, human or machine:
  producer-baseline trust × artifact confidence.
- **The review queue is the real community surface.** If promoting an AI draft
  **counts as a contribution** in the promoter's profile (a policy choice), AI *grows*
  the contributor base rather than shrinking it.
- **The tier ceiling is a values statement — and it maps onto the pipeline (§1).** AI
  caps below reconciling (6) and ordering reading priority (10); those un-starred
  stages are the ceiling made visible.
- **Per-language validation as the admission ritual.** A validation study per language
  is the deliberate community *gate* for AI membership in that language — governance,
  not afterthought.

## 5. Bring-your-own-key — funding as a first-class axis (1 page)

*AI inference is the first per-use-cost input the platform has ever had. "Whose budget
pays, and who may spend it" is its own axis.*

- **Three key tiers, precedence user → project → system;** the response always surfaces
  *whose money paid.*

  | Tier | Whose budget | Authorized by | Stored |
  |---|---|---|---|
  | User-provided | the individual | being that user | per-user, **encrypted** |
  | Project | a project's own budget | project membership / project-scoped role | project config / Git store |
  | Systemwide | the institution (historically DFG/INTF) | site-wide `AI:` role | `sysconfig.properties` |

- **BYOK UX *is* the width of the door.** Every step between "I have a key and a
  manuscript I love" and "the system is AI-assisting me and capturing the result" is
  where self-interested contribution leaks away.
- *(Framing note, not a slide: simply avoid the "public data" trigger. A scholar's own
  human work carries the normal visibility axis, but the AI seed is shared by design —
  so don't advertise contributor control over AI output, and don't foreground seed
  reuse / cost cross-subsidy. Keep all of this implementation-level; understatement.)*
- **A secrets service, not an auth service.** Identity stays in Liferay; scope to
  credential custody; never roll your own crypto (argon2id + libsodium/AES-GCM;
  OpenBao for server-custody). Personal ring = *user-custody* ("we hold an encrypted
  ring we cannot open" — the GDPR-defensible, deletable store); project keys =
  *server-custody* (must run unattended, can't be passphrase-locked).
- **The honest residual (say it out loud).** The server brokers the call, so plaintext
  is in JVM heap *for the duration of a call*. The posture to sell is **not** "never on
  our server" but *"never recoverable at rest, ephemeral in memory, scoped, revocable,
  audited"* — plus scoped, spend-capped provider keys.

## 6. Lessons — transferable beyond textual criticism (½ page)

- **Gate the output, never the vibe — AI is eager to please (the pilot lesson).** An
  LLM is *sly*: it will guess an answer and dress the guess in confident, agreeable
  prose, optimizing to make *you* happy rather than to be right. The only defense is to
  name an **invariant the answer must satisfy** and enforce it in code, not by reading
  the narrative. **Collation is the canonical example.** A collation is a *rearrangement
  of the witness's own tokens*, so the output is mechanically checkable against the
  input for exactly three failure modes:
  1. **tokens missing** (dropped from the witness),
  2. **tokens added** (invented, not in the witness),
  3. **actual words silently changed from the input tokens** — the sneakiest, because
     the result still *reads* perfectly.

  A validator that flags all three converts "sounds right" into "provably preserves the
  text." This is the pilot for a general rule that applies at *every* AI stage: find
  the invariant that stage must preserve and gate on it deterministically. The eager-to-
  please failure mode is exactly why provenance + gating (§3, §4) is load-bearing, not
  optional.
- **Prefer AI that *writes your tools* over AI that *does your task*.** AI is
  non-deterministic — the same prompt yields different output run to run — so its
  direct answers can't be relied on for consistent quality. But AI is excellent at
  writing **deterministic code**, and code runs the same every time. So push the AI up
  a level: instead of asking it to *do* the work, ask it to *build the tool* that does
  the work, then iteratively improve that tool until it gives consistent, inspectable
  results. The non-determinism moves from the *result* (expensive, every run) to the
  *authoring* (cheap, one time). This is the constructive twin of the pilot lesson —
  in fact the collation token-diff gate is itself an instance: AI *wrote the
  deterministic validator*, and the validator, not the AI's freehand judgment, is what
  we trust on every run.
  - **The one-sentence proof (regularization, Titus.1.2):** asked to do the whole
    task, the frontier model missed **4 of 38** purely mechanical bracket-stripping
    rules while producing fluent, confident output; the deterministic tier finds all
    38, in 102 ms, for free, identically every run. *String comparison cannot miss;
    the model can — so mechanize everything mechanizable and spend the model only on
    judgment.* Corollary from stage 9: the same move applied to the *input*
    (deterministic transposition flags fed to the model) was worth more than any
    amount of prompt engineering.
- **Decompose the work into stages, then admit AI stage by stage.** "Is AI helpful?"
  has no single answer; "is AI helpful at stage *k*?" has 12 honest ones. This is the
  method other fields can borrow.
- **The gaps in AI adoption should be *legible* — "not yet" vs. "by design."** A
  governance model that maps onto pipeline stages (a ceiling humans own) is what makes
  the boundary defensible rather than arbitrary.
- **Absorb, don't bolt on.** The wins came from AI entering the *existing* machinery
  (userID, review queue, provenance log, trust levels), not a parallel "AI mode."
- **Provenance-first is what makes it both safe and studyable** — the audit layer is
  also the research instrument. Build it in day one.
- **Name failure as total when it is total** — it licenses a different approach instead
  of tuning a dead end.
- **The hard problems are governance, not model quality** — impersonation vs.
  membership, whose-money-pays, does-promotion-count, human-vs-machine trust.
- **Extend, don't rewrite** — old code embodies thousands of fixes
  (expand → migrate → contract; warts kept *understood*).

## 7. Toward a research agenda / DFG framing (½ page)

- **The fundable claim is about humans, not models.** "AI can transcribe Greek" is
  assumed. The open question:
  > *What governance model lets AI assist at every stage of scholarly editing without
  > eroding the provenance and accountability that make a critical edition
  > authoritative?*
- **Why the VMRCRE is the right instrument:** a working provenance/trust
  infrastructure; a multilingual corpus with wildly uneven human capacity (a natural
  experiment on AI's marginal value vs. labour scarcity — the versions vs. Greek); a
  real observable community; a self-labeling evaluation corpus generated for free.
- **Sustainability, for a returning funder:** the original DFG investment built a
  commons still drawing contributions a decade on. The new ask is *not* "pay our
  inference invoice" — it is the *framework for federated, self-funded AI augmentation*
  where system, project, and individual budgets sit side by side.
  Contribute-your-expertise becomes contribute-your-expertise-**or-your-compute**.
- **The 12-stage program as the deliverable spine:** each stage is a milestone with a
  defensible output; CBGM (12) is the near-term flagship (before the congress);
  per-language validation is the recurring gate.

---

### Resolved (from the venue)
- **Venue/format:** ICCS XIII, "Coptology and Digital Humanities," 20-min talk + 5
  discussion, ~200-word abstract; host-privileged late submission.
- **Lead pole:** **access/equity** (AI reaches labour-starved traditions like Coptic),
  governance as backbone, sustainability (DFG Text+/NFDI, Göttingen Academy) as the
  returning-funder note.
- **How personal:** first-person war stories — a 20-min talk *wants* the impersonation
  guard, the personal key, and the AI-logs-in-and-drives-the-editor anecdote.

### Resolved: the Coptic evidence (from coptot.manuscriptroom.com, same API)
- **Collating — LXX↔Coptic works well, running now.** The money slide: a real, live
  Coptic result, not a Greek demo.
- **Indexing — definitively useful *even when transcription is subpar*.** The
  stage-decomposition thesis vindicated: a model can fail stage 5 yet pass stage 3.
- **Transcribing — some models useful, but scholars will challenge.** Present as
  assistive seeding, honestly; do not headline an accuracy claim.
- *Still an option for the close:* invite the audience to be the validators for the
  next languages (Syriac/Ethiopic), positioning Coptic as the proven case.

### Still open (need your call)
- **CBGM (stage 12) — keep or drop for this audience?** It's NT-textual-criticism-
  specific (Mink) and may not land with Coptologists. Options: demote to a one-line
  "even the genealogical stage is in reach," or cut from the talk and keep for an NT
  venue.
- **The closing call-to-action.** Lean toward: *your expertise is the validation gate —
  come be the validators; the platform already hosts CoptOT.* Confirm you want to
  recruit from the podium.
- **Co-author / acknowledge Ulrich Schmid?** He's on the Coptic-Sahidic OT at the host
  institution — his name and that project are the credibility bridge to this room.
