# TODO (laptop) — capture real CBGM AI local-stemma screenshots for the ICCS deck

**Note to self, written 2026-07-28 on the prod box.** Troy will launch me on his
**local laptop** to `docker compose` the CBGM stack (can't stand it up on the
prod box — that risks the kind of outage we had in July). Everything in this
folder (`intf-cbgm/vmrcre/iccs-talk/`) is self-contained so the deck can be
rebuilt on the laptop.

## The talk
- ICCS XIII, Göttingen — **Friday 31 July 2026, 16:30–17:00**, DH/AI session,
  chair Eliese-Sophia Lincke. Title (submitted): *AI integration with
  collaborative digital tools for critical editions.*
- Deck: `ai-integration-slides.pptx` (15 slides), built by `build_deck.py` on
  top of the team template (`template.pptx`, warm `#FFF7F6` bg, Roboto titles,
  Göttingen/IACS/NAWG logos). Roboto renders correctly in Google Slides.
- Google Slides copy Troy uploaded:
  https://docs.google.com/presentation/d/1PggM8lP5yMdkSD8MEC6lUtV_4ZHBtAD5/edit

## What's still a placeholder
**Slide 14 — "The pattern generalizes — CBGM local stemma"** is currently a
*schematic* (4 blue pills + 3 bullets). It needs **real screenshots** of the
`[Suggest Local Stemma]` flow, captured the same way we did the Ps 22:2
collation demo. The point of the slide: the collation integration pattern
(deterministic ground-truth → model-registry/BYOK → `ai/` producer tier →
edge-by-edge review gate → cost/token provenance) transplants to the CBGM local
stemma — the hardest editorial judgment in the pipeline.

## Bring up the CBGM AI stack (laptop, has Docker)
```bash
cd intf-cbgm/docker
export GEMINI_API_KEY=...            # BYOK — Gemini gave our best results in the demo
# (or ANTHROPIC_API_KEY / OPENAI_API_KEY; AI_DEFAULT_ENGINE defaults to gemini)
docker compose -f docker-compose.crosswire.yml -f docker-compose.ai.yml up
```
- App: **http://localhost:8088**  (host 8088 → container 5000).
- The AI overlay starts the in-container local-stemma JVM co-process
  (`/localstemma/<passage>`, `AI_LOCALSTEMMA_ENABLED=true`). Keys come from the
  host env, never baked into the image.
- Log in with **NTVMR credentials**; you need the **`CBGM Editor`** role to start
  an import. Pick a project, **Start CBGM**, let a book import (a few minutes).
- Code refs if anything misbehaves: `server/cbgm_ai.py` (digest + `/suggest-stemma`,
  `/suggestions`), client cards modeled on the collation Suggestions panel, D3
  ghost-edge overlay, contributor pill strip. Model picker reads the registry
  (`AI_MODEL_REGISTRY`, our `models.json`).

## Shots to capture (headed Chrome + CDP 9222 + Playwright MCP)
Reuse the harness recipe (see auto-memory `reference_rtl_playwright_harness` /
this session): launch the bundled chromium with `--remote-debugging-port=9222`
on the forwarded/local `DISPLAY`, then drive via the Playwright MCP. Save PNGs
into THIS folder.
1. A variation unit open with the **stemma graph** visible (before AI).
2. The **[Suggest Local Stemma]** action + engine/model picker.
3. The **suggestion review cards** (cost · time · tokens shown).
4. The **D3 ghost-edge overlay** — AI-proposed edges drawn on the stemma.
5. **Edge-by-edge accept** (before/after) + the contributor pill strip.

## Swap them into the deck
```bash
cd intf-cbgm/vmrcre/iccs-talk
# drop the new PNG(s) here, then edit build_deck.py slide 14:
#   replace/complement the schematic with add_image_fit(s, SHOTS+"cbgm_suggest.png", ...)
#   (mirror slides 5–11: image centered ~7.5x5.05in at 2.9,1.7 + a caption)
python3 build_deck.py          # -> ai-integration-slides.pptx (15 slides)
```
Then re-upload the pptx to the Google Slides deck (or hand Troy the file).
Also copy the refreshed pptx back to
`community/contrib/ai/claude/ai-integration-slides.pptx` (the live working copy).

## Framing rules (locked — do not drift)
- Say **"community benefit" / "shared research dataset,"** never "public data."
- AI output **enriches the shared research dataset** used by many teams — it is
  **not** "scholarship" and does **not** go "into the edition."
- Keep the submitted **"6 stages"** honest: CBGM is shown as the **just-landed
  frontier** (gold on the pipeline slide), not counted into the 6.
