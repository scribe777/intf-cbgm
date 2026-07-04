<template>
  <span v-if="others.length || dirty" class="editor-decisions">
    <span v-if="dirty" class="editor-decisions-unsaved"
          title="You have unsynced changes on this passage.">● unsaved</span>
    <span v-if="users.length" class="ed-contrib">
      <span class="ed-contrib-lab">at this passage:</span>
      <button v-for="u in users" :key="u" type="button"
              class="ed-person" :class="{ 'ed-loaded': u === loaded }"
              :disabled="busy"
              :title="(u === me ? 'Load your' : 'Load ' + u + '’s')
                      + ' saved decisions at this passage'"
              @click="load_user (u)">
        {{ u }}<span class="ed-tier">{{ u === me ? 'you' : 'editor' }}</span>
      </button>
    </span>
  </span>
</template>

<script>
/**
 * Indicator + toggle showing that other editors have saved decisions at the
 * current passage.  Click an editor to load their decisions into the local
 * database (which then reloads the stemma / coherence views).
 *
 * Data source: the per-user / per-verse editorial backups on the NTVMR,
 * surfaced by the cbgm_backup `editorial/*` endpoints.
 *
 * @component client/editor_decisions
 */

export default {
    'props' : {
        'pass_id' : { 'type' : [Number, String], 'required' : true },
        'epoch'   : { 'type' : Number, 'default' : 0 },
    },
    data () {
        return {
            'verse'  : null,
            'users'  : [],     // every editor with data at this verse
            'me'     : null,
            'mine'   : false,
            'loaded' : null,   // editor whose decisions we last loaded here
            'dirty'  : false,  // I have unsynced local edits at this passage
            'busy'   : false,
        };
    },
    'computed' : {
        /** Editors other than me who have decisions here. */
        others () {
            return this.users.filter (u => u !== this.me);
        },
    },
    'watch' : {
        pass_id () { this.refresh (); },
        epoch   () { this.refresh (); },
    },
    'mounted' : function () { this.refresh (); },
    'beforeDestroy' : function () {
        if (this._dirtyTimer) { clearTimeout (this._dirtyTimer); this._dirtyTimer = null; }
    },
    'methods' : {
        /** Fetch which editors have decisions at this passage. */
        refresh () {
            const vm = this;
            if (!vm.pass_id) {
                vm.users = []; vm.dirty = false; vm.scheduleDirtyPoll ();
                return;
            }
            vm.get ('editorial/users_by_passage.json/' + vm.pass_id)
                .then ((response) => {
                    const d = response.data.data || response.data;
                    vm.verse = d.verse;
                    vm.users = d.users || [];
                    vm.me    = d.me;
                    vm.mine  = d.mine;
                    vm.dirty = !!d.dirty;
                    vm.scheduleDirtyPoll ();
                })
                .catch (() => { vm.users = []; vm.dirty = false; vm.scheduleDirtyPoll (); });
        },
        /** The flush to the NTVMR is asynchronous + debounced, so the one-shot
         *  refresh fired at edit time still sees the edit as unsynced.  While it
         *  stays dirty, keep re-checking so "● unsaved" clears on its own once
         *  the flush lands — fast at first, then backing off so a genuinely
         *  stuck (offline / no-role) edit isn't polled forever. */
        scheduleDirtyPoll () {
            const vm = this;
            if (vm._dirtyTimer) { clearTimeout (vm._dirtyTimer); vm._dirtyTimer = null; }
            if (!vm.dirty) { vm._dirtyTries = 0; return; }
            vm._dirtyTries = (vm._dirtyTries || 0) + 1;
            const delay = vm._dirtyTries <= 6 ? 5000 : 30000;   // ~30s fast, then slow
            vm._dirtyTimer = setTimeout (() => { vm._dirtyTimer = null; vm.refresh (); }, delay);
        },
        /** Load a given editor's decisions for this passage, then reload views. */
        load_user (who) {
            const vm = this;
            if (vm.busy || !vm.pass_id) {
                return;
            }
            // Loading replaces the local stemma; warn if I have unsynced edits.
            if (vm.dirty && !window.confirm (
                'You have unsynced changes on this passage. Loading '
                + who + '’s decisions will replace them. Continue?')) {
                return;
            }
            vm.busy = true;
            vm.post ('editorial/load.json/' + vm.pass_id
                     + '?userName=' + encodeURIComponent (who))
                .then (() => {
                    vm.loaded = who;
                    vm.$trigger ('epoch'); // reload stemma / coherence / apparatus
                })
                .catch (() => {
                    // Load failed (e.g. offline): leave the current decisions
                    // in place; busy is cleared below.
                })
                .finally (() => { vm.busy = false; });
        },
    },
};
</script>

<style lang="scss">
/* Violet accents match $ai / $ai-soft in ai_stemma.vue. */
$pill-ai: #7657e6;

.editor-decisions {
    margin-left: 1em;
    font-weight: normal;
    font-size: 0.85rem;
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.4em;
}
.editor-decisions .editor-decisions-unsaved {
    color: #b8860b;
    font-weight: bold;
    margin-right: 0.2em;
}

/* Shared contributor-pill system — the light-card counterpart of the AI review
   dialog's "at this passage" strip (.ai-contrib / .ai-person), so the two lists
   read as one design.  Un-namespaced on purpose: ai_stemma.vue reuses these for
   its staged AI-producer pills (.ed-person.ed-ai).  These pills are clickable
   (load that editor's decisions / open that AI's suggestion). */
.ed-contrib {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.4em;
}
.ed-contrib-lab {
    color: #8a8f9c;
    font-size: 0.78rem;
}
.ed-person {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    padding: 0.1em 0.6em;
    border-radius: 1em;
    border: 1px solid #ccced6;
    background: #f5f6f8;
    color: #40454f;
    font: inherit;
    font-size: 0.78rem;
    line-height: 1.5;
    cursor: pointer;
    transition: border-color 0.12s, background 0.12s, color 0.12s;
}
.ed-person:hover {
    border-color: rgba(118, 87, 230, 0.55);
    background: rgba(139, 109, 240, 0.08);
}
.ed-person.ed-loaded {
    border-color: $pill-ai;
    background: rgba(139, 109, 240, 0.14);
    color: #5b41c4;
}
.ed-person:disabled {
    opacity: 0.55;
    cursor: default;
}
.ed-tier {
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #9aa0ac;
}
.ed-person.ed-loaded .ed-tier {
    color: $pill-ai;
}
/* AI-producer variant — the light-theme rendering of the dialog's .tier-ai */
.ed-person.ed-ai {
    border-color: rgba(118, 87, 230, 0.45);
    background: rgba(139, 109, 240, 0.09);
    .ed-tier { color: $pill-ai; }
}
.ed-person.ed-ai:hover,
.ed-person.ed-ai.ed-loaded {
    border-color: $pill-ai;
    background: rgba(139, 109, 240, 0.16);
    color: #5b41c4;
}
</style>
