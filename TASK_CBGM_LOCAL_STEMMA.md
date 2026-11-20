# Task::CBGMLocalStemma — design notes

*A thinking memo (2026-07-02): could the AI-Task framework we built for
collation and transcription seed the **local stemma** — the central editorial
act of the CBGM? Grounded in Mink's method + our `locstem` model + the
`org.crosswire.ai` Task framework (see the `Collate` / `Transcribe` tasks).*

---

## 1. What the local stemma is, and why it's different from what we've automated so far

A **local stemma** is a directed graph at *one variation unit*: nodes are the
**readings** (`a`, `b`, `c`, … — abstracted away from the manuscripts, Mink's
key move), edges run **source → derived** ("this reading gave rise to that
one"), rooted at the initial text **`a`** (`source = '*'`). It is *not* a
manuscript genealogy — it isolates a single textual-decision point.

In our data model (`CBGM.md`) it is the `locstem` table: for each
`(labez, clique)`, its `source_labez` / `source_clique`, with `'*'` = original
and `'?'` = unclear. **Everything downstream is a pure function of it** —
`build_A_text` reconstructs the initial text 'A' from the `'*'` rows, and
genealogical coherence (`postco`) is computed *over* the `locstem` DAG. Mink:
the method is "the encoding of the textual critic's decisions in local
stemmata."

This is a categorically harder thing to automate than collation or
transcription:

| Task | What the model produces | Nature |
|------|------------------------|--------|
| `Transcribe` | the letters on the page | *observation* — ground truth exists |
| `Collate` | which tokens align | *mechanical-ish* — defensible from the text |
| **`CBGMLocalStemma`** | which reading **descends from** which | ***editorial hypothesis*** — contested scholarship |

So the honest framing is not "the AI decides the stemma" but **"the AI drafts a
coherence-aware proposal the editor interrogates"** — the same seed-not-verdict
posture as our transcription seeds, but with the stakes turned up, because this
*is* the edition's argument.

## 2. How an editor actually builds it (Mink)

Three grounds, applied per edge (which of two readings is prior):

1. **Transcriptional probability** — which change is the more likely scribal
   move? Harmonization to parallels/context, itacism/orthographic drift,
   haplography/homoioteleuton, dittography, expansion/clarification, nomina
   sacra, assimilation. (The "lectio difficilior" family lives here.)
2. **Intrinsic probability** — which reading fits the author's style,
   vocabulary, theology, argument.
3. **Coherence** — *Mink's innovation*: a proposed direction must be consistent
   with the **textual flow**. If `X → Y` is transcriptionally attractive but the
   witnesses attesting `Y` don't connect back through the tradition to witnesses
   of `X`, the hypothesis is suspect. Coherence *tests and corrects* the
   philology.

Two more principles matter for a machine:

- **Phased construction** (Mink): editors start from "secure cases which hardly
  need discussion" and only later spend genealogical data on the hard ones. A
  large fraction of units are near-mechanical (e.g. a nonsense/orthographic
  singular `b` obviously derived from `a`). **That easy majority is exactly what
  an assistant should draft**, leaving the contested minority to the human.
- **`?` is a first-class answer** (like our `punt`): when transcriptional and
  intrinsic arguments pull equally, the honest output is *undecided*, not a
  coin-flip. A model that never says `?` is worse than useless here.
- **Iteration**: local decisions → recompute global coherence → revise the
  weak local stemmata → repeat until local and global reinforce each other.
- **Weighed, not counted** (Wachtel/Mink): a variant's support is *weighed by
  the genealogical significance of the witnesses attesting it*, not tallied as
  raw numbers — a reading carried by texts close to the initial text counts for
  more than the same reading in many late, derivative texts. For the task this
  means the coherence input must convey each witness's *genealogical position*
  (proximity to 'A' / potential-ancestor status), not just a headcount per
  reading.

## 3. Shape of `Task::CBGMLocalStemma`

Mirror `Collate`: inputs in the constructor, a typed result out of
`AIEngine.run(task, ctx)`, all derivation hidden.

**Input (constructor).** One variation unit:
- `verse` / passage ref, language.
- **readings**: `labez → text` for every reading, *including* the surrounding
  Ausgangstext / context window so intrinsic probability is judgeable.
- **attestation**: witnesses (docIDs) per reading — needed for coherence.
- **coherence hints** (optional but high-value): pre-genealogical coherence is
  *decision-independent* and available straight from the apparatus (`preco`), so
  we can feed, per reading, the **closest relatives of its witnesses**. This is
  what turns a pure-philology guess into a *coherence-aware* proposal, and it's
  cheap because `preco` needs no prior `locstem`.

**System prompt** (loaded via `PromptTemplate`, shared/editable like the
collation-assistant prompt): the role + the three grounds above, the DAG output
contract, and a hard instruction to prefer `?` over a forced direction and to
attach a per-edge rationale naming the transcriptional/intrinsic/coherence
argument.

**Output — typed `CBGMLocalStemmaResult extends TaskResult`:**
- `getLocalStemma()` → the DAG as `locstem`-shaped rows:
  `[{labez, clique, source_labez, source_clique, rationale, confidence}]` —
  directly seedable into `locstem` (or the VMRCRE apparatus).
- `getInitialReading()` → the `labez` marked `'*'`.
- generic `getConfidence()` — reuse the field; overall or lowest-edge.
- raw model output stays in the `getParsed()` bag.

**Validation (the `Collate`-style integrity gate, this is essential):**
- the source graph is **acyclic**;
- **exactly one** reading has `source = '*'` (well-defined 'A', matching
  `ix_locstem_unique_original`);
- every `source_labez` names a reading present at the unit (no invented labels);
- every reading is reachable from `'*'` or explicitly `'?'`.
- On violation → `needs_fix` with the specific defect, exactly as `Collate`
  re-prompts on a broken alignment table. This is what keeps the model from
  emitting a pretty-but-invalid stemma.

## 4. The real design fork: single-shot seed vs. coherence loop

- **(A) One-shot, coherence-*informed*.** Feed `preco` closest-relatives in the
  prompt; the model proposes once; the editor reviews. Cheap, robust, and it
  already captures most of Mink's phase-1 "secure cases." This is the `Collate`
  analogue and the right first cut.
- **(B) Coherence *loop*** (the full Mink cycle): propose `locstem` → run our
  `cbgm` (`build_A_text` + `postco`) → read back the **textual-flow** for each
  reading → re-prompt where a proposed edge has no coherent support → repeat to
  a fixed point. This is genuinely powerful and *uniquely enabled by the fact
  that we own the CBGM engine* (`intf-cbgm`): the task can call `prepare`/`cbgm`
  between iterations. It's the editorial iteration, automated, with the model in
  the correction loop the way our engines already re-prompt on `needs_fix` — but
  the "verifier" is the coherence recompute, not a JSON check.

(B) is the interesting research target; (A) is the shippable first step and a
prerequisite for (B).

## 5. Where it genuinely helps vs. where the editor must own it

**Helps:**
- Drafts the large easy majority (orthographic/nonsense/obvious-secondary),
  which is tedious hand-work.
- Surveys the transcriptional + intrinsic arguments for the *hard* units — the
  model has broad recall of scribal tendencies and NT parallels; a good
  "here are the arguments both ways" is real editorial value even when the
  *decision* is withheld.
- **Flags coherence violations** an editor might miss (option B), and proposes
  the `?`s honestly.

**Editor owns:**
- The contested directions — this *is* the edition's argument; the AI's job is
  to make the decision faster and better-informed, never to make it.
- Clique splits (`cliques`/`ms_cliques`) — a further editorial layer we'd keep
  out of scope for a first task.

The guardrails that make this defensible: **`?` is first-class**, **every edge
carries a rationale**, **the validity gate is hard**, and it is presented as a
*seed on the current apparatus* the editor overlays and edits — exactly the
posture of the editorial-sync design (decisions-not-apparatus, overlays on
current data).

## 6. Java sketch (mirrors `Collate`)

```java
// new CBGMLocalStemma(unit)  where unit carries readings + attestation + preco hints
public class CBGMLocalStemma extends Task {
    private final VariationUnit unit;
    public CBGMLocalStemma(VariationUnit unit) { this.unit = unit; }

    public String getName() { return "cbgm-local-stemma"; }

    public String buildSystemPrompt(TaskContext ctx) {
        return PromptTemplate.load(ctx.getSysConfig(), engineName(ctx),
            "_LOCALSTEMMA_DEFAULT_SYSTEM_PROMPT", "AI_LOCALSTEMMA_DEFAULT_SYSTEM_PROMPT",
            FALLBACK);          // the three grounds + DAG contract + "prefer ? " rule
    }

    public List<Message> buildUserMessages(TaskContext ctx) {
        return List.of(Message.user(LocalStemmaTokens.request(unit)));   // readings+attestation+preco
    }

    public TaskResult parseResponse(ApiResult api, TaskContext ctx, int attempt) {
        CBGMLocalStemmaResult r = new CBGMLocalStemmaResult();
        try {
            JSONObject obj = AiJson.parseObject(api.getText());
            List<LocstemRow> dag = LocalStemmaTokens.parse(obj, unit);   // labez->source_labez
            List<String> errs = LocalStemmaTokens.validate(dag, unit);   // acyclic, one '*', known labels
            if (!errs.isEmpty())
                return r.setStatus(NEEDS_FIX).setCorrectionFeedback(join(errs));
            r.setLocalStemma(dag).setConfidence(obj.optString("confidence","medium"))
             .setStatus(SUCCESS);
        } catch (JSONException e) { r.setStatus(NEEDS_FIX).setCorrectionFeedback("...JSON..."); }
        return r;
    }
}
// getLocalStemma() is the client's contract; the preco lookup, the prompt, and
// the acyclicity check are the task's business — change them freely later.
```

## 7. Open questions to settle before building

1. **Where does it run?** A Java Task (vmrcre) over the apparatus
   (`SEGMENTREADING`), writing `locstem` proposals through the editorial-sync
   store — or a component inside `intf-cbgm` (Python) closer to the `cbgm`
   engine for option (B)? The loop (B) argues for living where `cbgm` runs.
2. **Coherence input format** — how much of `preco`/closest-relatives to inline
   before it's noise; probably top-N relatives per witness, summarized per
   reading.
3. **Granularity** — one unit per call (clean, parallelizable, matches how
   editors think) vs. batching a verse. Start one-unit.
4. **Evaluation** — we have ground truth: published ECM local stemmata
   (Catholic Letters, Acts, Revelation). A held-out set of *already-decided*
   units is a real accuracy benchmark — measure agreement with the editors, and
   critically, whether the model's `?`s land on the genuinely hard units.
   Wachtel's *"Constructing Local Stemmata for the ECM of Acts: Examples"* (TC
   20, 2015) is a ready set of fully-worked, reasoned cases — the ideal first
   qualitative benchmark: does the model's rationale track the editors' on the
   same units?

---

**Bottom line.** The framework fits: `CBGMLocalStemma` is `Collate` with a
harder, more editorial payload — inputs in the constructor, a typed
`getLocalStemma()`, a strict validity gate, and `?` as a first-class outcome.
The shippable first cut is one-shot, `preco`-informed proposals for the easy
majority + argument-surfacing for the hard ones. The ambitious version closes
Mink's iteration loop by putting our own `cbgm` recompute in the correction
loop — which we can do precisely because we own the engine.

*Sources (primary practitioner accounts first): Gäbel/Hüffmeier/**Mink**/
Strutwolf/**Wachtel**, "The CBGM Applied to Variants from Acts: Methodological
Background," TC 20 (2015), jbtc.org/v20/TC-2015-CBGM-background.pdf;
**Wachtel**, "Constructing Local Stemmata for the ECM of Acts: Examples," TC 20
(2015), jbtc.org/v20/TC-2015-CBGM-examples.pdf (worked cases); local `CBGM.md`.
Gurry, "A Simple Introduction to the CBGM," is a useful secondary overview.
(The two TC PDFs were not machine-readable through my tools — the jbtc.org host
blocked automated fetches — so their specifics here rest on the editorial
team's published abstracts + framing; read them directly to refine.)*
