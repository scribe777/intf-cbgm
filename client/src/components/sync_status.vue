<template>
  <span v-if="loaded" class="sync-status" :title="hint">
    <span v-if="count === 0" class="sync-ok">✓ synced</span>
    <span v-else class="sync-dirty">
      <template v-if="connection_active">
        <span class="sync-icon">{{ can_save ? '⏳' : '🔒' }}</span>
        {{ count }} unsynced
        <button type="button" class="btn btn-sm btn-outline-primary sync-btn"
                :disabled="busy || !can_save"
                @click="sync_now">{{ busy ? 'syncing…' : 'Sync now' }}</button>
      </template>
      <template v-else>
        <span class="sync-icon">🔌</span>
        {{ count }} saved locally &mdash; reconnect to
        <strong>{{ connection_label || 'its VMRCRE' }}</strong> to save
      </template>
    </span>
  </span>
</template>

<script>
/**
 * Outbox status + manual sync control.  Polls editorial/status.json: shows how
 * many of my segments are edited-but-not-yet-synced to the NTVMR, whether I
 * have permission to sync (Project CBGM Editor), and a "Sync now" button.
 *
 * Also retries the flush periodically, so work made offline (or before the
 * save role was granted) syncs on its own once connectivity / the role return.
 *
 * @component client/sync_status
 */

export default {
    'props' : {
        'epoch' : { 'type' : Number, 'default' : 0 }, // bump => an edit happened
    },
    data () {
        return {
            'loaded'   : false,
            'count'    : 0,
            'can_save' : false,
            'connection_label'  : '',
            'connection_active' : true,
            'busy'     : false,
            'timer'    : null,
        };
    },
    'computed' : {
        hint () {
            if (this.count === 0) {
                return 'All your editorial decisions are synced to the NTVMR.';
            }
            if (!this.connection_active) {
                return this.count + ' segment(s) saved locally. This project'
                    + ' belongs to ' + (this.connection_label || 'another VMRCRE')
                    + '; choose it in “Connect to…” to sync your work there.';
            }
            if (!this.can_save) {
                return this.count + ' segment(s) edited and saved locally, but you'
                    + ' do not have the Project CBGM Editor role on this project,'
                    + ' so they are not shared yet. They will sync once you are'
                    + ' granted the role.';
            }
            return this.count + ' segment(s) edited but not yet synced to the'
                + ' NTVMR. Click "Sync now" to push them.';
        },
    },
    'watch' : {
        epoch () { this.refresh (); },     // re-check right after an edit
    },
    'mounted' : function () {
        this.refresh ();
        // Periodic poll + opportunistic retry (offline/role recovery).
        this.timer = setInterval (() => {
            this.refresh ();
            if (this.count > 0 && this.can_save && !this.busy) {
                this.sync_now ();
            }
        }, 45000);
    },
    'beforeDestroy' : function () {
        if (this.timer) {
            clearInterval (this.timer);
        }
    },
    'methods' : {
        refresh () {
            const vm = this;
            vm.get ('editorial/status.json')
                .then ((response) => {
                    const d = response.data.data || response.data;
                    vm.count    = d.count || 0;
                    vm.can_save = !!d.can_save;
                    vm.connection_label  = d.connection_label || '';
                    // default true so a normal single-backend project is unaffected
                    vm.connection_active = d.connection_active !== false;
                    vm.loaded   = true;
                })
                .catch (() => { /* not in a project instance / not logged in */ });
        },
        sync_now () {
            const vm = this;
            if (vm.busy) {
                return;
            }
            vm.busy = true;
            vm.post ('editorial/sync.json')
                .then ((response) => {
                    const d = response.data.data || response.data;
                    if (typeof d.remaining === 'number') {
                        vm.count = d.remaining;
                    }
                    if (typeof d.can_save === 'boolean') {
                        vm.can_save = d.can_save;
                    }
                })
                .catch (() => {
                    // Sync failed (e.g. offline): keep the queued edits and the
                    // current count; the user can retry.  busy cleared below.
                })
                .finally (() => { vm.busy = false; });
        },
    },
};
</script>

<style lang="scss">
.sync-status {
    font-size: 0.85rem;
    font-weight: normal;
    margin-left: 1em;
    white-space: nowrap;
}
.sync-status .sync-ok      { color: #6c757d; }
.sync-status .sync-dirty   { color: #b8860b; }
.sync-status .sync-btn {
    margin-left: 0.4em;
    padding: 0 0.4em;
    line-height: 1.4;
}
</style>
