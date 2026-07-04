# -*- encoding: utf-8 -*-

"""AI local-stemma support for the CBGM API server.

This module is the deterministic *digest layer* that turns a variation unit in
the database into the compact JSON contract the CBGMLocalStemma task consumes
(schema/cbgm-local-stemma-unit.schema.json in vmrcre/contrib/ai/cbgm-ai/). The
heavy O(witnesses^2) affinity data stays in Postgres; what leaves here is a
reading-scale digest:

  - readings + their weight-bearing witnesses,
  - coherence.perReading  — for each reading, the pre-genealogical
    coherence-ranked candidate ancestor(s) (which reading do the closest
    relatives of this reading's witnesses attest?),
  - coherence.incoherentWitnesses — the Wachtel exceptions (a witness whose
    nearest relative reads differently here).

The same functions are the future *pull-mode* tool registry (see TOOLS): the
push path calls them all up front to build the unit; an agentic mode would
expose them as on-demand tools. All coherence comes from `affinity_view` (the
PRE-genealogical, decision-independent view) so seeding never depends on the
local stemma it is trying to propose.
"""

import collections
import json
import os

import flask
from flask import request, current_app
import flask_login
import requests

from ntg_common.db_tools import execute

from helpers import parameters, Passage
from login import edit_auth

bp = flask.Blueprint ('cbgm_ai', __name__)

SCHEMA_VERSION = '1.0'
AI_SERVER_URL  = 'http://127.0.0.1:8078/localstemma'   # the warm JVM co-process

# engine name (AIEngine.getName) -> the API-key env var that enables it, and a
# display label.  Used to offer only usable engines in the model picker.
ENGINE_KEY_ENV = {
    'claude':        'ANTHROPIC_API_KEY',
    'gemini':        'GEMINI_API_KEY',
    'openai':        'OPENAI_API_KEY',
    'xai':           'XAI_API_KEY',
    'perplexity':    'PERPLEXITY_API_KEY',
    'openrouter':    'OPENROUTER_API_KEY',
    'github-models': 'GITHUB_TOKEN',
}
ENGINE_LABELS = {
    'claude': 'Claude', 'gemini': 'Gemini', 'openai': 'OpenAI', 'xai': 'xAI (Grok)',
    'perplexity': 'Perplexity', 'openrouter': 'OpenRouter', 'github-models': 'GitHub Models',
}


def _model_catalogue ():
    """The shared model catalogue (the same models.json crosswire.jar's
    ModelRegistry reads), or {} if unavailable."""
    path = os.environ.get ('AI_MODEL_REGISTRY', '/home/ntg/ai/models.json')
    try:
        with open (path) as fp:
            return json.load (fp)
    except (OSError, ValueError):
        return {}


def init_app (_app):
    """ Initialize the flask app. """
    pass


# --------------------------------------------------------------------------- #
#  Primitives — each is also a pull-mode tool (see TOOLS).                     #
# --------------------------------------------------------------------------- #

def readings_of (conn, pass_id):
    """The non-lacunose readings of the passage: [(labez, lesart), ...]."""
    res = execute (conn, """
        SELECT labez, lesart
        FROM readings
        WHERE pass_id = :pass_id AND labez !~ '^z'
        ORDER BY labez
    """, dict (parameters, pass_id = pass_id))
    return [(labez, lesart or '') for labez, lesart in res]


def witnesses_of (conn, pass_id):
    """labez -> [(hs, hsnr), ...] for the certain, non-z, collated witnesses."""
    res = execute (conn, """
        SELECT labez, hs, hsnr
        FROM apparatus_view_agg
        WHERE pass_id = :pass_id AND labez !~ '^z' AND certainty = 1.0
        ORDER BY labez, hsnr
    """, dict (parameters, pass_id = pass_id))
    out = collections.defaultdict (list)
    for labez, hs, hsnr in res:
        out[labez].append ((hs, hsnr))
    return out


def reading_at (conn, ms_id, pass_id):
    """The labez this witness reads at the passage, or None (lac/uncertain)."""
    res = execute (conn, """
        SELECT labez FROM apparatus_view_agg
        WHERE pass_id = :pass_id AND ms_id = :ms_id AND certainty = 1.0
    """, dict (parameters, pass_id = pass_id, ms_id = ms_id))
    row = res.fetchone ()
    return row[0] if row else None


def closest_relatives (conn, ms_id, rg_id, k = 10):
    """Top-k PRE-genealogical relatives of a witness in a range.

    Returns [{ms_id, hs, affinity, common, equal, rank}] ranked by affinity —
    the same window function textflow uses, on the decision-independent view.
    """
    res = execute (conn, """
        SELECT ms_id2, hs, affinity, common, equal, rank FROM (
            SELECT a.ms_id2,
                   rank () OVER (ORDER BY a.affinity DESC, a.common DESC, a.ms_id2) AS rank,
                   a.affinity, a.common, a.equal
            FROM affinity_view a
            WHERE a.ms_id1 = :ms_id AND a.rg_id = :rg_id
        ) t JOIN manuscripts m ON m.ms_id = t.ms_id2
        WHERE rank <= :k
        ORDER BY rank
    """, dict (parameters, ms_id = ms_id, rg_id = rg_id, k = k))
    return [dict (ms_id = r[0], hs = r[1], affinity = float (r[2]),
                  common = r[3], equal = r[4], rank = r[5]) for r in res]


# --------------------------------------------------------------------------- #
#  Reductions — the coherence digest.                                         #
# --------------------------------------------------------------------------- #

def per_reading_coherence (conn, pass_id, rg_id):
    """For every reading, its coherence-ranked candidate ancestor readings.

    For each witness w reading L here, take its nearest relative that reads a
    *different* non-z reading; tally those differing readings per L. bestAncestor
    is the most-attested; ancestorStrength = (that count) / (#witnesses of L).

    Returns { labez -> {bestAncestor|None, ancestorStrength, candidates:[{labez,strength}]} }.
    """
    res = execute (conn, """
        WITH att AS (
            SELECT ms_id, labez FROM apparatus_view_agg
            WHERE pass_id = :pass_id AND labez !~ '^z' AND certainty = 1.0
        ),
        rel AS (
            SELECT att.labez AS lw, a.ms_id1 AS w, a.ms_id2 AS r,
                   rank () OVER (PARTITION BY a.ms_id1
                                 ORDER BY a.affinity DESC, a.common DESC, a.ms_id2) AS rk
            FROM att JOIN affinity_view a ON a.ms_id1 = att.ms_id AND a.rg_id = :rg_id
        ),
        relread AS (
            SELECT rel.lw, rel.w, rel.rk, av.labez AS lr
            FROM rel JOIN apparatus_view_agg av ON av.ms_id = rel.r AND av.pass_id = :pass_id
            WHERE av.certainty = 1.0 AND av.labez !~ '^z' AND av.labez <> rel.lw
        ),
        nearest AS (
            SELECT DISTINCT ON (lw, w) lw, w, lr FROM relread ORDER BY lw, w, rk
        )
        SELECT lw, lr, count(*) AS n FROM nearest GROUP BY lw, lr ORDER BY lw, n DESC
    """, dict (parameters, pass_id = pass_id, rg_id = rg_id))

    totals = { labez: len (wits) for labez, wits in witnesses_of (conn, pass_id).items () }
    agg = collections.OrderedDict ()
    for lw, lr, n in res:
        total = totals.get (lw, 0) or 1
        entry = agg.setdefault (lw, { 'labez': lw, 'bestAncestor': None,
                                      'ancestorStrength': 0.0, 'candidates': [] })
        strength = round (n / total, 3)
        entry['candidates'].append ({ 'labez': lr, 'strength': strength })
        if strength > entry['ancestorStrength']:
            entry['bestAncestor'], entry['ancestorStrength'] = lr, strength
    # readings with no differing-relative signal look self-contained / initial
    for labez in totals:
        agg.setdefault (labez, { 'labez': labez, 'bestAncestor': None,
                                 'ancestorStrength': 0.0, 'candidates': [] })
    return agg


def incoherent_witnesses (conn, pass_id, rg_id, cap = 15):
    """Witnesses whose NEAREST relative reads differently here (the exceptions).

    Returns [{siglum, reads, closestRelative, relativeReads}], capped.
    """
    res = execute (conn, """
        WITH att AS (
            SELECT ms_id, hs, labez FROM apparatus_view_agg
            WHERE pass_id = :pass_id AND labez !~ '^z' AND certainty = 1.0
        ),
        rel AS (
            SELECT att.ms_id AS w, att.hs AS whs, att.labez AS lw, a.ms_id2 AS r,
                   rank () OVER (PARTITION BY a.ms_id1
                                 ORDER BY a.affinity DESC, a.common DESC, a.ms_id2) AS rk
            FROM att JOIN affinity_view a ON a.ms_id1 = att.ms_id AND a.rg_id = :rg_id
        ),
        rank1 AS (
            SELECT DISTINCT ON (w) w, whs, lw, r FROM rel ORDER BY w, rk
        )
        SELECT r1.whs, r1.lw, m.hs, av.labez
        FROM rank1 r1
          JOIN apparatus_view_agg av ON av.ms_id = r1.r AND av.pass_id = :pass_id
                                    AND av.certainty = 1.0 AND av.labez !~ '^z'
          JOIN manuscripts m ON m.ms_id = r1.r
        WHERE av.labez <> r1.lw
        LIMIT :cap
    """, dict (parameters, pass_id = pass_id, rg_id = rg_id, cap = cap))
    return [dict (siglum = r[0], reads = r[1], closestRelative = r[2], relativeReads = r[3])
            for r in res]


# --------------------------------------------------------------------------- #
#  Witness weighting + composition (the PUSH path).                           #
# --------------------------------------------------------------------------- #

def _weight_bearing (wits, name_cap):
    """Split [(hs, hsnr), ...] into (named sigla, total count).

    Names the most significant witnesses first (lowest hsnr: A, MT, majuscules,
    versions ... come before the minuscule mass) up to name_cap; the rest are
    represented only by the count. For small versional projects every witness
    is named. NOTE: hsnr-order significance is a heuristic to refine per project.
    """
    named = [hs for hs, _ in wits[:name_cap]]
    return named, len (wits)


def build_unit (conn, pass_id, rg_id = None, k = 10, name_cap = 20):
    """Assemble a schemaVersion-1.0 unit for the passage — exactly what
    POST /localstemma validates and consumes."""
    p = Passage (conn, pass_id)
    if rg_id is None:
        rg_id = p.range_id ()          # chapter-scoped coherence (CBGM norm)

    texts = dict (readings_of (conn, pass_id))
    wits  = witnesses_of (conn, pass_id)
    coh   = per_reading_coherence (conn, pass_id, rg_id)

    readings = []
    for labez in sorted (set (texts) | set (wits)):
        named, total = _weight_bearing (wits.get (labez, []), name_cap)
        readings.append ({
            'labez': labez,
            'text': texts.get (labez, ''),
            'witnesses': named,
            'witnessCount': total,
        })

    unit = {
        'schemaVersion': SCHEMA_VERSION,
        'verse': p.to_hr (),
        'readings': readings,
        'coherence': {
            'perReading': [ coh[labez] for labez in sorted (coh) ],
            'incoherentWitnesses': incoherent_witnesses (conn, pass_id, rg_id),
        },
    }
    return unit


# --------------------------------------------------------------------------- #
#  Pull-mode tool registry (same functions, on-demand). Documents the mini-MCP #
#  surface an agentic variant would expose; not yet wired to a tool loop.      #
# --------------------------------------------------------------------------- #

TOOLS = {
    'attestation':          { 'fn': witnesses_of,          'args': ['pass_id'] },
    'reading_at':           { 'fn': reading_at,            'args': ['ms_id', 'pass_id'] },
    'closest_relatives':    { 'fn': closest_relatives,     'args': ['ms_id', 'rg_id', 'k?'] },
    'per_reading_coherence':{ 'fn': per_reading_coherence, 'args': ['pass_id', 'rg_id'] },
}


# --------------------------------------------------------------------------- #
#  HTTP                                                                        #
# --------------------------------------------------------------------------- #

@bp.route ('/models')
def models ():
    """The engine/model catalogue for the AI picker, an optgroup-shaped list
    limited to engines that have an API key configured in this container (so the
    picker only offers usable choices).  Reads the same models.json that
    crosswire.jar's ModelRegistry does."""
    catalogue = _model_catalogue ()
    engines = []
    for name, key in ENGINE_KEY_ENV.items ():
        models_ = catalogue.get (name)
        if not models_ or not os.environ.get (key):
            continue
        engines.append ({
            'engine' : name,
            'label'  : ENGINE_LABELS.get (name, name),
            'models' : [{ 'id' : m['id'], 'name' : m.get ('name', m['id']) }
                        for m in models_ if isinstance (m, dict) and m.get ('id')],
        })
    return flask.jsonify ({
        'engines' : engines,
        'default' : os.environ.get ('AI_DEFAULT_ENGINE', 'gemini'),
    })


@bp.route ('/localstemma/<passage_or_id>')
def local_stemma (passage_or_id):
    """Build the unit for a passage and (unless ?dry_run) ask the AI server for
    a proposed local stemma. ?engine=claude|gemini|... ?model=<id> ?rg=<rg_id>
    ?dry_run=1."""
    with current_app.config.dba.engine.begin () as conn:
        p = Passage (conn, passage_or_id)
        rg = request.args.get ('rg')
        unit = build_unit (conn, p.pass_id, rg_id = int (rg) if rg else None)

    if request.args.get ('dry_run'):
        return flask.jsonify (unit)

    result, _ = _ask_model (unit, request.args.get ('engine', 'gemini'),
                            request.args.get ('model'))
    return flask.jsonify (result)


def _ask_model (unit, engine, model = None):
    """POST a unit to the warm JVM co-process and return its parsed result, or a
    ({'error'}, reachable=False) tuple if the AI server is not up.  A non-empty
    model overrides the engine's default; the JVM validates it against the
    registry."""
    payload = dict (unit, engine = engine)
    if model:
        payload['model'] = model
    try:
        resp = requests.post (AI_SERVER_URL, json = payload, timeout = 180)
    except requests.RequestException as e:
        return { 'error': 'AI server unavailable: %s' % e }, False
    try:
        return resp.json (), True
    except ValueError:
        return { 'error': 'AI server returned non-JSON', 'raw': resp.text[:500] }, True


def suggestion_fragment (begadr, endadr, result):
    """Shape a JVM stemma result into a project-data fragment.

    The proposed stemma is stored in the SAME shape as a human decision -- a
    ``locstem`` of [labez, clique, source_labez, source_clique] rows (clique '1',
    the default) -- so the review UI can diff it against the current stemma and
    accept/override edge by edge (an accept is then an ordinary stemma-edit).
    Alongside it rides a ``suggestions`` provenance block (model, confidence,
    per-reading rationale, comments) that the review rail renders and that marks
    the blob as proposed rather than committed.  See project_cbgm_ai_as_contributor.
    """
    stemma = result.get ('stemma') or []
    locstem = [[e.get ('reading'), '1', e.get ('source', '?'), '1']
               for e in stemma if e.get ('reading')]
    rationale = { e['reading']: e.get ('rationale', '')
                  for e in stemma if e.get ('reading') }
    return {
        'begadr': int (begadr), 'endadr': int (endadr),
        'locstem': locstem, 'cliques': [], 'ms_cliques': [], 'notes': [],
        'suggestions': {
            'model': result.get ('model'),
            'engine': result.get ('engine'),
            'confidence': result.get ('confidence'),
            'initial': result.get ('initial'),
            'hasUndecided': result.get ('hasUndecided'),
            'comments': result.get ('comments'),
            'rationale': rationale,
            'attempts': result.get ('attempts'),
            'tokensOut': result.get ('tokensOut'),
        },
    }


@bp.route ('/suggestions/<passage_or_id>')
def suggestions_at (passage_or_id):
    """Contributors + any STAGED AI suggestions at a passage, for the review UI.

    Returns { ref, contributors: [{producer, tier}], suggestions: [fragment...] }.
    contributors is every producer with data here (AI models + human editors, so
    the "who has data" strip can show them side by side); suggestions is the
    ai-tier fragments (locstem + the `suggestions` provenance block) the client
    renders in review mode.  Read-only; no model call.
    """
    import cbgm_backup   # lazy: same rationale as suggest_stemma
    user = flask_login.current_user
    sh = getattr (user, 'api_key', None)
    project = current_app.config.get ('VMRCRE_PROJECT_NAME')
    with current_app.config.dba.engine.begin () as conn:
        p = Passage (conn, passage_or_id)
        begadr, endadr = int (p.start), int (p.end)
    ref = cbgm_backup.passage_ref (begadr, endadr)

    contributors = cbgm_backup.list_segment_contributors (project, ref, sh) if project else []
    suggestions = []
    for c in contributors:
        if c['tier'] == 'ai':
            frag = cbgm_backup.get_segment (project, ref, c['producer'], sh, state = 'ai')
            if frag is not None:
                suggestions.append (dict (frag, producer = c['producer']))
    return flask.jsonify ({ 'ref': ref, 'contributors': contributors,
                            'suggestions': suggestions })


@bp.route ('/suggest-stemma/<passage_or_id>', methods = ['POST', 'OPTIONS'])
def suggest_stemma (passage_or_id):
    """Generate an AI local-stemma suggestion and STAGE it in the ai/ tier.

    The [Suggest Local Stemma] write path: build the digest, ask the model, shape
    the result into a suggestion fragment, and write it under the model's name
    (state='ai') via cbgm_backup.put_suggestion.  It is staged, not applied -- it
    appears beside the human editors ("who has data here") and is reviewed
    (accept/override) in the UI.  ?engine=gemini|claude|... ?rg=<rg_id>.
    """
    if request.method == 'OPTIONS':
        return flask.jsonify ({})
    edit_auth ()
    import cbgm_backup   # lazy: keeps a non-VMRCRE boot from needing the sync deps

    engine = request.args.get ('engine', 'gemini')
    model  = request.args.get ('model')
    with current_app.config.dba.engine.begin () as conn:
        p = Passage (conn, passage_or_id)
        rg = request.args.get ('rg')
        unit = build_unit (conn, p.pass_id, rg_id = int (rg) if rg else None)
        begadr, endadr = int (p.start), int (p.end)

    result, reachable = _ask_model (unit, engine, model)
    if not reachable or not result.get ('stemma'):
        # AI server down, or the model failed to produce a stemma -- surface it,
        # store nothing.
        return flask.jsonify ({ 'stored': False, 'ref': None,
                                'result': result }), (503 if not reachable else 200)

    model = result.get ('model') or result.get ('engine') or engine
    fragment = suggestion_fragment (begadr, endadr, result)

    user = flask_login.current_user
    project = current_app.config.get ('VMRCRE_PROJECT_NAME')
    ref = cbgm_backup.passage_ref (begadr, endadr)
    root = cbgm_backup.put_suggestion (project, ref, fragment, model,
                                       getattr (user, 'api_key', None), push = 'true')
    return flask.jsonify ({
        'stored': root is not None,
        'ref': ref, 'tier': 'ai', 'producer': model,
        'result': result,
    })
