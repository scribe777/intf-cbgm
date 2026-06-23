# CBGM coherence engine — how it works

How the INTF CBGM tool turns an apparatus + editorial decisions into the
numbers and diagrams editors use: **pre-genealogical coherence** (closest
relatives), **genealogical coherence** (who is older/newer than whom, how many
times), and the **textual-flow** arrows. Traced from the source; file:line
references are for navigation.

## The two layers of coherence

- **Pre-genealogical coherence** — pure agreement between witnesses, computed
  straight from the apparatus, **no editorial decisions involved**. Symmetrical
  (A↔B). Answers "how similar are two witnesses" → *closest relatives*.
- **Genealogical coherence** — directional, computed from the editors' **local
  stemmata** (`locstem`). Asymmetrical (A→B ≠ B→A). Answers "at how many
  passages is A prior to B" → *potential ancestors* and *textual flow*.

Both are written to one table, `affinity`, per *range* (each chapter and the
whole book).

## Data model (the editorial layer)

| table | what it holds | who sets it |
|-------|---------------|-------------|
| `apparatus` | which `labez` (reading) each witness offers at each passage | import (collation) — *source data* |
| `readings` | the readings (`labez` → text) at each passage | import |
| `cliques` | sub-groupings of a reading (`labez`,`clique`); default one `'1'` per reading | import default + editor splits |
| `ms_cliques` | which clique each witness sits in | import default (`'1'`) + editor |
| `locstem` | **the local stemma**: for each `(labez,clique)`, its `source_labez/source_clique` (`*`=original, `?`=unclear) | **editor** |
| `notes` | editor's note per passage | editor |
| `affinity` | computed pairwise coherence per range | the `cbgm` script |

The **editorial decision** is essentially the `locstem` DAG (plus clique splits
and witness clique-assignments). Everything else is apparatus/source data. (See
the editorial-sync design, which persists exactly this decision delta and
overlays it on the current apparatus.)

## The pipeline

Per instance config, two CLI passes (`Makefile`, or `docker-compose run
ntg-app-server cbgm`):

```
python3 -m scripts.cceh.prepare  instance/<project>.conf   # build matrices from the apparatus
python3 -m scripts.cceh.cbgm     instance/<project>.conf   # rebuild 'A', then preco + postco
```

`scripts/cceh/cbgm.py` `__main__` runs, in order:

1. `build_A_text` — reconstruct the initial text 'A' from `locstem`.
2. `create_labez_matrix` — witness × passage matrix of readings (incl. 'A').
3. `calculate_mss_similarity_preco` — pre-genealogical (agreements).
4. `calculate_mss_similarity_postco` — genealogical (older/newer via the DAG).
5. `write_affinity_table` — persist to `affinity` (+ `ms_ranges` lengths).

`preco`/`postco`/`write_affinity_table` live in `ntg_common/cbgm_common.py`.

> **Key consequence for editing:** `preco` is independent of decisions, so
> closest-relatives is available as soon as the apparatus is imported.
> `postco` is a pure function of the **current `locstem`**, so the older/newer
> statistics are only as current as the decisions in the DB *when `cbgm` runs*
> — it is a batch recompute, not per-edit. To get whole-project genealogical
> coherence you must load every editor's decisions into `locstem` first (the
> editorial-sync **Refresh All**), then run `cbgm`.

## `build_A_text` — reconstructing the initial text

`scripts/cceh/cbgm.py:34`. 'A' (`MS_ID_A`, ms_id = 1) is a **virtual
manuscript** representing the editors' reconstructed archetype. It is rebuilt
entirely from `locstem`:

1. Delete any existing 'A' rows (`ms_cliques`, `ms_cliques_tts`, `apparatus`).
2. For every non-*Fehlvers* passage, set A's reading to the reading the editors
   marked **original** — the `locstem` row whose `source_labez = '*'`:
   ```sql
   SELECT :A, p.pass_id, COALESCE (l.labez, 'zz'), COALESCE (l.clique, '1'), ...
   FROM passages p
   LEFT JOIN locstem l ON (l.pass_id, l.source_labez) = (p.pass_id, '*')
   WHERE NOT p.fehlvers
   ```
   If no reading is connected to `*` (editors undecided) → A reads `'zz'` (a gap
   in the reconstructed text).
3. *Fehlvers* passages (verse judged not original) → A reads `'zu'`.
4. A's `lesart` is always NULL (virtual).

The `locstem` index `ix_locstem_unique_original` enforces **at most one `*`
source per passage**, so 'A' is well-defined. Because 'A' participates as a
witness in `preco`/`postco`, every other witness gets a coherence relationship
*to the initial text* — the central CBGM question ("how close is this ms to A,
and could it be an ancestor?"). `postco` sanity-checks that nothing computes as
older than A.

It must run **first** because A enters the matrices in steps 2–4.

## Pre-genealogical coherence (`preco`)

`cbgm_common.py:calculate_mss_similarity_preco`. For every pair (symmetrical):

- `common` — passages where **both** witnesses are extant (both defined),
- `equal` — passages where they read the **same**,
- `affinity = equal / common`.

That's it — closest relatives = highest affinity. No stemma involved. Computed
as NumPy boolean-matrix ANDs over the labez matrix, per range.

## Genealogical coherence (`postco`) — older vs newer

`cbgm_common.py:calculate_mss_similarity_postco`. Reduces to one bitwise test
per passage per pair, after this setup:

**1. Per-passage DAG.** `local_stemma_to_nx` builds a directed graph from
`locstem`: nodes are reading-cliques (`a1`,`b1`,…), edges run source → derived,
plus pseudo-nodes `*` (archetype) and `?` (unknown source).

**2. Bitmask per reading.** `*` → 0; `?` → 1 (bit 0 = "source unclear" flag);
every real reading → a distinct bit `1<<i` (64-clique ceiling).

**3. Ancestor masks.** `parents[n]` = OR of direct-source bits; `ancestors[n]`
= OR of **all transitively prior** readings (via `networkx.transitive_closure`).
So `ancestors[n]` is the set of every reading upstream of `n` in the stemma.

**4. Per (ms, passage) lookup** (from `apparatus_cliques_view`, excluding `z*`
and non-cbgm): store `mask_matrix` (the reading's bit), `ancestor_matrix` (its
ancestor mask), `parent_matrix`; `quest_matrix = parent_matrix & 1` flags an
unclear source.

**5. The decision** (`cbgm_common.py:502`):
```python
varidj_is_older = (mask_matrix[j] & ancestor_matrix[k]) > 0   # j prior to k  (j → k)
varidk_is_older = (mask_matrix[k] & ancestor_matrix[j]) > 0   # k prior to j  (j ← k)
```
**j is *older* than k at a passage iff j's reading is among the ancestors of
k's reading in that passage's local stemma.** NumPy runs it over all passages
at once.

At each passage where both are extant and **differ**, exactly one bucket:
- **older** — `varidj_is_older` (j → k)
- **newer** — `varidk_is_older` (j ← k)
- **unclear** — differ, ≥1 reading has source `?`, and neither is ancestral to
  the other (`cbgm_common.py:523`)
- **norel** — remainder, computed later as `common − equal − older − newer −
  unclear`.

**Loop guard:** if both `varidj_is_older` and `varidk_is_older` come out true
(a cycle in the stemma), both are zeroed and the passage is logged — a bad
editorial DAG can't inflate counts.

**Two granularities** (`cbgm_common.py:536`): `postco` runs twice —
`parent_matrix` (direct source only → `p_older/p_newer/p_unclear`) and
`ancestor_matrix` (transitive → `older/newer/unclear`). Genealogical coherence /
potential ancestors uses the **transitive** set.

`count_by_range` tallies per chapter and book; `older` and its transpose
`newer` are the "→ / ← how many times" aggregates.

## The `affinity` table

`ntg_common/db.py` (`affinity`): `rg_id, ms_id1, ms_id2`,
`affinity, common, equal` (pre-genealogical), `older, newer, unclear`
(genealogical, transitive), `p_older, p_newer, p_unclear` (genealogical,
direct-parent). One row per ordered pair per range.

## Textual-flow arrows (`server/textflow.py`)

How the aggregates become the arrows an editor sees.

**A. Nodes** — every witness extant at the passage (`apparatus`), optionally
filtered to one `labez` ("Coherence in Attestations"); z-readings excluded
unless ranking them.

**B. Rank potential ancestors** — the core query (`textflow.py:139`):
```sql
rank() OVER (PARTITION BY ms_id1
             ORDER BY affinity DESC, common, older, newer DESC, ms_id2)
FROM <affinity_view> a
WHERE ms_id1 IN :nodes AND rg_id = :rg_id AND ms_id2 NOT IN :exclude
  AND newer > older                 -- ms2 is a POTENTIAL ANCESTOR of ms1
  AND a.common > a.ms1_length/2     -- enough shared text (unless 'fragments')
WHERE rank <= :connectivity
```
- `newer > older`: for the pair (ms1, ms2), ms2 is prior to ms1 more often than
  the reverse → ms2 qualifies as a potential ancestor of ms1. **This turns the
  directional counts into the candidate-ancestor set.**
- `ORDER BY affinity DESC …`: rank candidates by *pre-genealogical* closeness →
  **rank 1 = closest potential ancestor**.
- `connectivity` caps the search depth (default 10; **global flow forces
  connectivity=1**, `:91`; 21 → unlimited, `:94`). `common > ms1_length/2`
  drops candidates that barely overlap.
- `mode='rec'` uses `affinity_view` (transitive older/newer); `mode='sim'` uses
  `affinity_p_view` (the `p_` parent variant). (`textflow.py:85`)

**C. Attach readings** — each node's `labez`/`clique`; `group_field` is `labez`
or `labez_clique` per the *cliques* toggle.

**D. Choose the parent arrow** — two passes over the ranked candidates
(closest-first) (`textflow.py:216`):
- **Pass 1 (agreeing ancestor):** edge from the highest-ranked potential
  ancestor that **shares ms1's reading**. `add_edge(ms2, ms1)` — arrow points
  **ancestor → descendant**. Tag ms1; no further parent.
- **Pass 2 (reading boundary):** if no same-reading ancestor exists in range,
  connect to the highest-ranked potential ancestor regardless of reading — that
  arrow **crosses a reading change**, marking where ms1's variant emerged.

Each witness ends up with essentially **one incoming arrow**: its nearest
potential ancestor that best explains its reading.

**The number on an arrowhead** is `headlabel = rank` when rank > 1
(`textflow.py:238`): "the nearest ancestor that actually shares my reading was
only my *Nth*-closest relative." High number = coherence red flag — the
witness's closest relatives don't carry its reading.

**E. Prune** (`textflow.py:250`) — drop z leaf nodes (lacunose/uncertain)
unless requested; remove isolated non-focus nodes; `var_only` extra cleanup;
render to GraphViz dot.

**What `connectivity` means:** how willing the diagram is to attribute a
reading to a more distant relative. At 1, a witness connects only to its single
nearest potential ancestor; if that disagrees, the variant appears "born" there
(a Pass-2 edge). Higher → reach further down the ancestor ranking for an
*agreeing* source, revealing whether the reading is coherent among near
relatives or keeps arising independently.

`hyp_a` lets an editor test "what if A read X here" by overriding A's reading
(`textflow.py:102`, `:193`) and re-deriving the graph — without changing the DB.

## End-to-end summary

```
apparatus (collation)          locstem (editor decisions)
        │                               │
        │                       build_A_text  ──► virtual ms 'A' = initial text
        │                               │
   create_labez_matrix ◄────────────────┘
        │
        ├─ preco  ──► common/equal/affinity ........ closest relatives (symmetric)
        └─ postco ──► older/newer/unclear ........... potential ancestors (directional)
                          │
                   write_affinity_table  ──►  affinity (per range)
                          │
                   textflow.py: newer>older filter → rank by affinity →
                   connectivity cap → two-pass parent pick → arrows
```

Change a `locstem` edge → re-run `cbgm` → the affinity counts and every
textual-flow arrow shift accordingly. That re-run over the *combined* decisions
of all editors is what the editorial-sync **Refresh All** exists to feed.
