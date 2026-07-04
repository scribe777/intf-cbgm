<template>
  <span class="ai-stemma">
    <!-- trigger + engine -->
    <button type="button" class="btn btn-sm ai-suggest-btn"
            :disabled="busy" @click="suggest ()"
            title="Ask an AI to propose a local stemma for this passage.">
      <span class="ai-spark">✦</span>
      {{ busy ? 'Thinking…' : 'Suggest local stemma' }}
    </button>
    <select v-model="selected" class="ai-engine" :disabled="busy || !catalogue.length"
            title="AI engine / model">
      <optgroup v-for="grp in catalogue" :key="grp.engine" :label="grp.label">
        <option v-for="m in grp.models" :key="grp.engine + '::' + m.id"
                :value="grp.engine + '::' + m.id">{{ m.name }}</option>
      </optgroup>
    </select>

    <!-- staged-suggestion hint when one already exists and none is open -->
    <span v-if="!panel && stagedProducers.length" class="ai-staged-hint">
      <button type="button" class="btn btn-sm ai-review-btn" @click="review ()">
        ✦ review {{ stagedProducers.join (', ') }}
      </button>
    </span>

    <!-- the review panel (floats below the caption) -->
    <div v-if="panel" class="ai-panel">
      <div class="ai-panel-head">
        <span class="ai-who"><span class="ai-dot"></span>{{ panel.model || engine }}</span>
        <span class="ai-conf" v-if="panel.confidence != null">
          confidence
          <span class="ai-conf-bar"><span class="ai-conf-fill"
                :style="{ width: confPct + '%' }"></span></span>
          <span class="ai-conf-n">{{ confLabel }}</span>
        </span>
        <span class="ai-spring"></span>
        <button type="button" class="ai-close" @click="panel = null" title="close">✕</button>
      </div>

      <div v-if="meterLabel" class="ai-meter">{{ meterLabel }}</div>

      <p v-if="panel.comments" class="ai-comments">{{ panel.comments }}</p>

      <!-- how many are real changes vs. paths already selected, + a toggle to
           reveal the agreeing ones (for their rationale) -->
      <div v-if="panel.stemma.length" class="ai-sub">
        <span class="ai-sub-count">
          {{ changeEdges.length }} change<span v-if="changeEdges.length !== 1">s</span>
          <span v-if="agreeEdges.length" class="ai-sub-agree">
            · {{ agreeEdges.length }} already set</span>
        </span>
        <span class="ai-spring"></span>
        <button v-if="agreeEdges.length" type="button" class="ai-toggle"
                @click="showAll = !showAll">
          {{ showAll ? 'changes only' : 'show all' }}
        </button>
      </div>

      <div v-if="visibleEdges.length" class="ai-cards">
        <div v-for="e in visibleEdges" :key="e.reading" class="ai-card"
             :class="{ 'ai-card-init' : e.source === '*', 'ai-card-done' : e._done,
                       'ai-card-agrees' : agrees (e) }"
             @mouseenter="hover (e)" @mouseleave="hover (null)">
          <div class="ai-card-head">
            <span class="ai-tok ai-tok-reading">{{ e.reading }}</span>
            <span class="ai-tok-arrow">←</span>
            <span class="ai-tok ai-tok-source">{{ e.source }}</span>
            <span v-if="agrees (e)" class="ai-card-badge ai-badge-set">✓ set</span>
            <span v-else-if="e.source === '*'" class="ai-card-badge">initial</span>
          </div>
          <p v-if="e.rationale" class="ai-card-reason">{{ e.rationale }}</p>
          <div class="ai-card-actions">
            <button type="button" class="ai-card-accept"
                    :disabled="e.source === '*' || busy || e._done || agrees (e)"
                    :title="e.source === '*' ? 'initial-text edge — set via the editor' : 'Apply ' + e.reading + ' ← ' + e.source"
                    @click="accept (e)">
              {{ e._done ? '✓ applied' : (agrees (e) ? '✓ already set' : 'Accept') }}
            </button>
            <button type="button" class="ai-card-dismiss"
                    :disabled="busy" title="Dismiss this suggestion"
                    @click="dismiss (e)">
              Dismiss
            </button>
          </div>
        </div>
      </div>

      <div v-else-if="panel.stemma.length" class="ai-empty">
        The AI agrees with your stemma — nothing to change.
        <button v-if="agreeEdges.length" type="button" class="ai-toggle"
                @click="showAll = true">see its reasoning</button>
      </div>

      <div v-if="contributors.length" class="ai-contrib">
        <span class="ai-contrib-lab">at this passage:</span>
        <span v-for="c in contributors" :key="c.tier + '/' + c.producer"
              class="ai-person" :class="'tier-' + c.tier">
          {{ c.producer }}<span class="ai-tier">{{ c.tier }}</span>
        </span>
      </div>
    </div>

    <alert ref="alert" />
  </span>
</template>

<script>
/**
 * [Suggest Local Stemma] — ask an AI to propose a local stemma for the current
 * passage, review its edges + rationale, and accept them one by one (each
 * accept is an ordinary stemma-edit, so it flows through the normal
 * decision/sync path).  Staged suggestions live in the ai/ tier of the
 * project-data store (cbgm_ai /suggest-stemma + /suggestions); they are shown
 * beside the human editors, never auto-applied.
 *
 * @component client/ai_stemma
 */

import alert from 'widgets/alert.vue';

export default {
    'components' : { alert },
    'props' : {
        'pass_id'      : { 'type' : [Number, String], 'required' : true },
        'epoch'        : { 'type' : Number, 'default' : 0 },
        // current stemma { reading: sourceLabez }, from local_stemma via coherence
        'stemma_state' : { 'type' : Object, 'default' : null },
    },
    data () {
        return {
            'catalogue'    : [],     // [{ engine, label, models:[{id,name}] }] usable here
            'selected'     : '',     // "<engine>::<model_id>"
            'busy'         : false,
            'panel'        : null,   // the suggestion being reviewed { model, confidence, comments, stemma[] }
            'contributors' : [],     // [{ producer, tier }]
            'staged'       : [],     // ai-tier fragments already stored here
            'showAll'      : false,  // reveal edges the AI proposes that are already set
        };
    },
    'computed' : {
        engine () { return (this.selected.split ('::')[0]) || 'gemini'; },
        model  () { return this.selected.split ('::')[1] || ''; },
        stagedProducers () {
            return this.staged.map ((s) => s.producer);
        },
        /** Proposed edges that differ from the current stemma (real changes). */
        changeEdges () {
            return (this.panel ? this.panel.stemma : []).filter ((e) => !this.agrees (e));
        },
        /** Proposed edges that already match the current stemma. */
        agreeEdges () {
            return (this.panel ? this.panel.stemma : []).filter ((e) => this.agrees (e));
        },
        /** Cards to render: changes only by default, everything under "show all". */
        visibleEdges () {
            if (!this.panel) return [];
            return this.showAll ? this.panel.stemma : this.changeEdges;
        },
        confPct () {
            const c = this.panel && this.panel.confidence;
            if (typeof c === 'number') return Math.round (c * 100);
            // string confidences from the model: high/medium/low
            return { high : 90, medium : 60, low : 30 }[String (c).toLowerCase ()] || 50;
        },
        confLabel () {
            const c = this.panel && this.panel.confidence;
            return typeof c === 'number' ? c.toFixed (2) : String (c);
        },
        /** "$0.0042 · 3.2s · 1.7k→1.7k tok" — cost, time, and token counts. */
        meterLabel () {
            const p = this.panel;
            if (!p) return '';
            const parts = [];
            if (p.price != null)      parts.push ('$' + Number (p.price).toFixed (4));
            if (p.durationMs != null) parts.push ((p.durationMs / 1000).toFixed (1) + 's');
            if (p.tokensIn != null || p.tokensOut != null) {
                parts.push (this.fmtTok (p.tokensIn) + '→' + this.fmtTok (p.tokensOut) + ' tok');
            }
            return parts.join (' · ');
        },
    },
    'watch' : {
        // A new passage closes the open panel; an epoch bump (e.g. after
        // accepting an edge) keeps it open so you can accept the rest.
        pass_id () { this.panel = null; this.showAll = false; this.refresh (); },
        epoch   () { this.refresh (); },
        // Ghost the proposed edges on the stemma whenever the panel opens,
        // switches, or closes.  local_stemma draws them (via coherence).
        panel (p) {
            if (p) this.showAll = false;   // a fresh suggestion starts changes-only
            this.$trigger ('ai_proposal', p
                ? p.stemma.map ((e) => ({ 'reading' : e.reading, 'source' : e.source }))
                : null);
        },
    },
    'mounted' : function () { this.loadModels (); this.refresh (); },
    'methods' : {
        /** Fetch the engine/model catalogue (only key-configured engines) and
         *  default the picker to the server's preferred engine. */
        loadModels () {
            const vm = this;
            vm.get ('models')
                .then ((r) => {
                    const d = r.data.data || r.data;
                    vm.catalogue = d.engines || [];
                    const def = vm.catalogue.find ((e) => e.engine === d.default)
                                || vm.catalogue[0];
                    if (def && def.models.length) {
                        vm.selected = def.engine + '::' + def.models[0].id;
                    }
                })
                .catch (() => { vm.catalogue = []; });
        },
        /** Load any staged AI suggestions + contributors for this passage. */
        refresh () {
            const vm = this;
            if (!vm.pass_id) { vm.staged = []; vm.contributors = []; return; }
            vm.get ('suggestions/' + vm.pass_id)
                .then ((r) => {
                    const d = r.data.data || r.data;
                    vm.staged = d.suggestions || [];
                    vm.contributors = d.contributors || [];
                })
                .catch (() => { vm.staged = []; vm.contributors = []; });
        },
        /** Open a staged suggestion (the first one) in the review panel. */
        review () {
            const s = this.staged[0];
            if (s) this.panel = this.fragmentToPanel (s);
        },
        /** Ask the model for a fresh suggestion. */
        suggest () {
            const vm = this;
            if (vm.busy) return;
            vm.busy = true;
            const q = '?engine=' + encodeURIComponent (vm.engine)
                    + (vm.model ? '&model=' + encodeURIComponent (vm.model) : '');
            vm.post ('suggest-stemma/' + vm.pass_id + q)
                .then ((r) => {
                    const d = r.data.data || r.data;
                    const res = d.result || d;
                    if (!res || !res.stemma) {
                        vm.$refs.alert.show (
                            (res && res.error) || 'The model did not return a stemma.',
                            'error');
                        return;
                    }
                    vm.panel = {
                        'model'      : res.model || vm.engine,
                        'confidence' : res.confidence,
                        'comments'   : res.comments,
                        'price'      : res.price,
                        'durationMs' : res.durationMs,
                        'tokensIn'   : res.tokensIn,
                        'tokensOut'  : res.tokensOut,
                        'stemma'     : (res.stemma || []).map ((e) => ({ ...e, '_done' : false })),
                    };
                    vm.refresh ();   // pick up the freshly-stored ai/ producer
                })
                .catch ((error) => {
                    const msg = (error.response && error.response.data
                                 && (error.response.data.result || {}).error)
                                || (error.response && error.response.statusText)
                                || 'suggestion failed';
                    vm.$refs.alert.show (msg, 'error');
                })
                .finally (() => { vm.busy = false; });
        },
        /** Does this proposed edge already match the current stemma? (i.e. the
         *  reading's source is already what the AI proposes — nothing to do). */
        agrees (e) {
            const st = this.stemma_state;
            return !!(st && Object.prototype.hasOwnProperty.call (st, e.reading)
                      && st[e.reading] === e.source);
        },
        /** Card hover -> tell the stemma to emphasise this ghost edge and pulse
         *  its source (amber) + reading (green) nodes — the analogue of the
         *  collation editor's orange/green cell highlight on suggestion hover. */
        hover (e) {
            this.$trigger ('ai_hover', e
                ? { 'reading' : e.reading, 'source' : e.source }
                : null);
        },
        /** Drop one suggestion from the panel (local only; nothing persisted).
         *  Re-ghosts the remaining edges so the overlay stays in sync. */
        dismiss (e) {
            const vm = this;
            if (!vm.panel) return;
            vm.panel.stemma = vm.panel.stemma.filter ((x) => x !== e);
            vm.$trigger ('ai_hover', null);
            vm.$trigger ('ai_proposal', vm.panel.stemma.map (
                (x) => ({ 'reading' : x.reading, 'source' : x.source })));
        },
        /** Accept one edge: set reading <- source via an ordinary stemma-edit. */
        accept (e) {
            const vm = this;
            if (e.source === '*' || vm.busy) return;
            vm.busy = true;
            vm.post ('stemma-edit/' + vm.pass_id, {
                'action'     : 'move',
                'labez_old'  : e.reading,
                'clique_old' : '1',
                'labez_new'  : e.source,
                'clique_new' : '1',
            })
                .then (() => {
                    vm.$set (e, '_done', true);
                    vm.$trigger ('epoch');   // redraw stemma / coherence
                })
                .catch ((error) => {
                    vm.$refs.alert.show (
                        (error.response && error.response.data && error.response.data.message)
                        || 'could not apply', 'error');
                })
                .finally (() => { vm.busy = false; });
        },
        /** Turn a stored fragment (locstem + suggestions block) into a panel. */
        fragmentToPanel (frag) {
            const s = frag.suggestions || {};
            const rats = s.rationale || {};
            const stemma = (frag.locstem || []).map ((row) => ({
                'reading'   : row[0],
                'source'    : row[2],
                'rationale' : rats[row[0]] || '',
                '_done'     : false,
            }));
            return {
                'model'      : s.model || frag.producer,
                'confidence' : s.confidence,
                'comments'   : s.comments,
                'price'      : s.price,
                'durationMs' : s.durationMs,
                'tokensIn'   : s.tokensIn,
                'tokensOut'  : s.tokensOut,
                'stemma'     : stemma,
            };
        },
        /** Compact token count: 1740 -> "1.7k". */
        fmtTok (n) {
            if (n == null) return '?';
            return n >= 1000 ? (n / 1000).toFixed (1) + 'k' : String (n);
        },
    },
};
</script>

<style lang="scss">
$ai: #7657e6;
$ai-soft: #8b6df0;

.ai-stemma {
    margin-left: 0.75em;
    font-weight: normal;
    font-size: 0.85rem;
}
/* Anchor the review panel to the card (not the caption span) and float it
   top-right, so it never covers the stemma the ghost edges are drawn on. */
.card-local-stemma { position: relative; }
.ai-suggest-btn {
    color: #fff;
    background: linear-gradient(180deg, #8f72f3, $ai);
    border: 1px solid rgba(118, 87, 230, 0.6);
    padding: 0.1em 0.6em;
    &:hover { filter: brightness(1.07); color: #fff; }
    &:disabled { opacity: 0.7; }
}
.ai-spark { margin-right: 0.3em; }
.ai-engine {
    margin-left: 0.35em;
    font-size: 0.8rem;
    border: 1px solid #ccc;
    border-radius: 0.2rem;
    padding: 0.05em 0.2em;
}
.ai-review-btn {
    margin-left: 0.5em;
    color: $ai;
    border: 1px solid rgba(118, 87, 230, 0.5);
    background: rgba(139, 109, 240, 0.08);
    padding: 0.1em 0.6em;
}

.ai-panel {
    position: absolute;
    z-index: 30;
    top: 3.2em;
    right: 0.8em;
    left: auto;
    width: 26em;
    max-width: 48%;
    background: #1f2740;
    color: #e7e9f0;
    border: 1px solid rgba(139, 109, 240, 0.4);
    border-radius: 0.6em;
    box-shadow: 0 24px 60px -24px rgba(0, 0, 0, 0.7);
    padding: 0.8em 0.9em;
    text-align: left;
    font-weight: normal;
}
.ai-panel-head { display: flex; align-items: center; gap: 0.7em; }
.ai-who {
    font-size: 0.8rem; letter-spacing: 0.05em; color: $ai-soft;
    display: flex; align-items: center; gap: 0.4em;
}
.ai-dot { width: 6px; height: 6px; border-radius: 50%; background: $ai-soft; box-shadow: 0 0 8px $ai-soft; }
.ai-conf { font-size: 0.72rem; color: #a9b0c0; display: flex; align-items: center; gap: 0.4em; }
.ai-conf-bar { width: 60px; height: 5px; border-radius: 3px; background: rgba(255,255,255,0.1); overflow: hidden; }
.ai-conf-fill { display: block; height: 100%; background: linear-gradient(90deg, #7657e6, #a98cf7); }
.ai-conf-n { color: $ai-soft; font-variant-numeric: tabular-nums; }
.ai-spring { flex: 1; }
.ai-close { background: none; border: none; color: #8b93a7; cursor: pointer; font-size: 0.9rem; }
.ai-close:hover { color: #fff; }

.ai-meter {
    margin-top: 0.45em;
    font-family: monospace;
    font-size: 0.72rem;
    color: #8b93a7;
    letter-spacing: 0.02em;
}
.ai-comments {
    margin: 0.6em 0 0.5em;
    font-size: 0.82rem; line-height: 1.4; color: #c7ccda;
    border-left: 2px solid rgba(139, 109, 240, 0.5);
    padding-left: 0.6em;
}
/* Suggestion cards — modelled on the collation editor's Regularization
   Suggestions cards (reg-card): a hover-lift card with coloured source/target
   tokens, a reason line, and an Accept/Dismiss pair.  Hovering a card also
   emphasises its ghost edge and pulses its nodes on the stemma (see hover()). */
.ai-cards { display: flex; flex-direction: column; gap: 0.5em; margin-top: 0.2em; }
.ai-card {
    padding: 0.55em 0.6em;
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 0.5em;
    background: rgba(255, 255, 255, 0.03);
    cursor: pointer;
    transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}
.ai-card:hover {
    border-color: rgba(139, 109, 240, 0.7);
    box-shadow: 0 2px 12px -3px rgba(139, 109, 240, 0.55);
    background: rgba(139, 109, 240, 0.08);
}
.ai-card-done { opacity: 0.55; }
.ai-card-init { opacity: 0.8; }
.ai-card-head {
    display: flex; align-items: center; gap: 0.4em; flex-wrap: wrap;
    margin-bottom: 0.35em;
}
.ai-tok {
    font-family: monospace; font-weight: bold; font-size: 0.95rem;
    padding: 0.05em 0.4em; border-radius: 0.25em;
}
.ai-tok-reading { background: rgba(90, 160, 115, 0.24); color: #cde7d6; }
.ai-tok-source  { background: rgba(230, 170, 70, 0.20);  color: #f2d9a8; }
.ai-tok-arrow   { color: $ai-soft; padding: 0 0.15em; }
.ai-card-badge {
    margin-left: auto; font-size: 0.62rem; text-transform: uppercase;
    letter-spacing: 0.05em; padding: 0.1em 0.4em; border-radius: 0.25em;
    background: rgba(139, 109, 240, 0.15); color: $ai-soft;
}
.ai-card-reason {
    margin: 0 0 0.45em; font-size: 0.78rem; color: #a9b0c0; line-height: 1.4;
}
/* changes-vs-already-set summary + the show-all toggle */
.ai-sub {
    display: flex; align-items: center; gap: 0.5em;
    margin: 0.55em 0 0.15em; font-size: 0.72rem; color: #8b93a7;
}
.ai-sub-agree { color: #7fae8c; }
.ai-toggle {
    background: none; border: 1px solid rgba(139, 109, 240, 0.5);
    color: $ai-soft; border-radius: 1em; padding: 0.05em 0.65em;
    font-size: 0.7rem; cursor: pointer;
    &:hover { background: rgba(139, 109, 240, 0.12); }
}
.ai-empty {
    font-size: 0.82rem; color: #a9b0c0; line-height: 1.45;
    padding: 0.5em 0.2em 0.2em;
    display: flex; flex-direction: column; align-items: flex-start; gap: 0.5em;
}

/* an already-selected path shown under "show all": muted, source token neutral */
.ai-card-agrees {
    opacity: 0.72;
    .ai-tok-source { background: rgba(255, 255, 255, 0.06); color: #aeb4c4; }
}
.ai-badge-set { background: rgba(127, 174, 140, 0.18); color: #9fd0ab; }

.ai-card-actions { display: flex; gap: 0.4em; }
.ai-card-accept {
    flex: 1; padding: 0.2em; font-size: 0.8rem; font-weight: bold;
    color: #cde7d6; background: rgba(90, 160, 115, 0.18);
    border: 1px solid rgba(90, 160, 115, 0.6); border-radius: 0.25em;
    cursor: pointer;
    &:hover { background: rgba(90, 160, 115, 0.3); }
    &:disabled { opacity: 0.45; cursor: default; }
}
.ai-card-dismiss {
    flex: 1; padding: 0.2em; font-size: 0.8rem;
    color: #9098ab; background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.14); border-radius: 0.25em;
    cursor: pointer;
    &:hover { background: rgba(255, 255, 255, 0.08); color: #c9cede; }
    &:disabled { opacity: 0.45; cursor: default; }
}

.ai-contrib {
    margin-top: 0.7em; padding-top: 0.6em;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    display: flex; flex-wrap: wrap; align-items: center; gap: 0.4em;
    font-size: 0.75rem;
}
.ai-contrib-lab { color: #636b82; }
.ai-person {
    display: inline-flex; align-items: center; gap: 0.35em;
    padding: 0.1em 0.5em; border-radius: 1em;
    border: 1px solid rgba(255, 255, 255, 0.1); color: #c9cede;
}
.ai-person.tier-ai { border-color: rgba(139, 109, 240, 0.5); background: rgba(139, 109, 240, 0.1); }
.ai-tier {
    font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: #636b82;
}
.ai-person.tier-ai .ai-tier { color: $ai-soft; }
</style>
