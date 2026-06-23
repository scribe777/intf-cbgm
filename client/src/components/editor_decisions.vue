<template>
  <span v-if="others.length || dirty" class="editor-decisions">
    <span v-if="dirty" class="editor-decisions-unsaved"
          title="You have unsynced changes on this passage.">● unsaved</span>
    <span v-if="others.length" class="badge badge-info" :title="hint">
      👥 {{ others.length }} other editor<span v-if="others.length > 1">s</span> here
    </span>
    <span v-if="others.length" class="editor-decisions-toggle">
      load:
      <button v-for="u in users" :key="u"
              type="button"
              class="btn btn-sm btn-outline-secondary"
              :class="{ 'btn-outline-primary': u === loaded }"
              :disabled="busy"
              @click="load_user (u)">
        {{ u }}<span v-if="u === me"> (you)</span>
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
        hint () {
            return 'These editors have saved decisions at this passage: '
                + this.users.join (', ')
                + '. Click a name to load that editor’s decisions.';
        },
    },
    'watch' : {
        pass_id () { this.refresh (); },
        epoch   () { this.refresh (); },
    },
    'mounted' : function () { this.refresh (); },
    'methods' : {
        /** Fetch which editors have decisions at this passage. */
        refresh () {
            const vm = this;
            if (!vm.pass_id) {
                vm.users = [];
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
                })
                .catch (() => { vm.users = []; vm.dirty = false; });
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
                .finally (() => { vm.busy = false; });
        },
    },
};
</script>

<style lang="scss">
.editor-decisions {
    margin-left: 1em;
    font-weight: normal;
    font-size: 0.85rem;
}
.editor-decisions .editor-decisions-toggle {
    margin-left: 0.5em;
}
.editor-decisions .editor-decisions-unsaved {
    color: #b8860b;
    font-weight: bold;
    margin-right: 0.5em;
}
.editor-decisions .btn {
    margin-left: 0.25em;
    padding: 0 0.4em;
    line-height: 1.4;
}
</style>
