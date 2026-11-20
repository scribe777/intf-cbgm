<template>
  <div class="vm-project-list">
    <div class="container bs-docs-container">
      <div class="jumbotron">
        <h1 class="display-4">A program suite for the CBGM</h1>
        <p class="lead">Coherence-Based Genealogical Method (CBGM)</p>
        <hr class="my-4" />
        <img
          :src="ECMActs"
          style="float: left; width: 200px; margin: 0 1rem 1rem 0"
        />
        <p>
          The <strong>Coherence-Based Genealogical Method</strong>, developed by
          Gerd Mink at the Institut für Neutestamentliche Textforschung (INTF)
          in Münster, aims at a scientifically founded reconstruction of the
          initial text (*Ausgangstext*) of the New Testament tradition, i.e. a
          hypothesis about the text from which the manuscript transmission
          started.<br />The fundamental problem posed by the nature of the New
          Testament manuscript tradition is known as contamination, the mutual
          influence of different strands of transmission on each other.<br />
          Contamination renders the application of conventional stemmatics
          impossible, and the New Testament manuscript tradition is known to be
          highly contaminated.<br />
          The CBGM, however, offers a cure for contamination. Three essential
          principles distinguishing it from conventional stemmatics:
          pre-genealogical coherence, genealogical coherence, and stemmatic
          coherence.
        </p>
        <br />
        <a
          class="btn btn-primary btn-lg"
          href="http://egora.uni-muenster.de/intf/projekte/gsm_aus_en.shtml"
          target="_blank"
          role="button"
          >Learn more</a
        >
      </div>
    </div>
    <div class="container bs-docs-container">
      <h4>Your projects</h4>
      <br />
      <input
        ref="dump_input"
        type="file"
        style="display: none"
        @change="dump_selected"
      />
      <input
        ref="local_dump_input"
        type="file"
        style="display: none"
        @change="local_dump_selected"
      />
      <div
        v-if="start_dialog"
        class="cbgm-start-overlay"
        @click.self="start_dialog = null"
      >
        <div class="cbgm-start-dialog">
          <h5>Import &ldquo;{{ start_dialog.name }}&rdquo;</h5>
          <p class="text-muted small">
            Choose which witnesses go into the CBGM database. The defaults
            match the standard behaviour; changing them later means reloading
            the project.
          </p>
          <div class="form-group">
            <label for="cbgm-doc-ranges">Document ID ranges</label>
            <input
              id="cbgm-doc-ranges"
              v-model="start_options.doc_ranges"
              class="form-control form-control-sm"
              placeholder="e.g. 10000-29999, 32344"
            />
            <small class="form-text text-muted">
              Only witnesses whose document ID falls in these ranges are
              imported. Leave empty for the default (all Greek manuscripts on
              a New Testament project; everything on other projects).
            </small>
          </div>
          <div class="form-check">
            <input
              id="cbgm-firsthand"
              v-model="start_options.firsthand_only"
              class="form-check-input"
              type="checkbox"
            />
            <label class="form-check-label" for="cbgm-firsthand">
              First hand only
              <small class="text-muted">
                &mdash; the original scribe's reading, or his/her own correction
                (C*) where there is one; uncheck to also import later correctors
                (C, C1, &hellip;) as separate witnesses
              </small>
            </label>
          </div>
          <div class="form-check">
            <input
              id="cbgm-supplements"
              v-model="start_options.exclude_supplements"
              class="form-check-input"
              type="checkbox"
            />
            <label class="form-check-label" for="cbgm-supplements">
              Exclude supplements
              <small class="text-muted">
                &mdash; skip supplement leaves instead of importing them as
                separate &lsquo;s&rsquo; witnesses
              </small>
            </label>
          </div>
          <div class="cbgm-suffixes">
            <label class="mb-0">
              Collapse suffixed witnesses into their reading:
            </label>
            <small class="form-text text-muted" style="margin-top: 0">
              An unchecked suffix excludes those witnesses at that variant
              unit, as if lacunose.
            </small>
            <div class="form-check form-check-inline">
              <input
                id="cbgm-suffix-r"
                v-model="start_options.collapse_regularized"
                class="form-check-input"
                type="checkbox"
              />
              <label class="form-check-label" for="cbgm-suffix-r">
                r <small class="text-muted">(regularized)</small>
              </label>
            </div>
            <div class="form-check form-check-inline">
              <input
                id="cbgm-suffix-f"
                v-model="start_options.collapse_nonsense"
                class="form-check-input"
                type="checkbox"
              />
              <label class="form-check-label" for="cbgm-suffix-f">
                f <small class="text-muted">(Fehler)</small>
              </label>
            </div>
            <div class="form-check form-check-inline">
              <input
                id="cbgm-suffix-v"
                v-model="start_options.collapse_unsure"
                class="form-check-input"
                type="checkbox"
              />
              <label class="form-check-label" for="cbgm-suffix-v">
                V <small class="text-muted">(ut videtur)</small>
              </label>
            </div>
          </div>
          <div class="text-right" style="margin-top: 1rem">
            <button
              class="btn btn-sm btn-secondary"
              @click="start_dialog = null"
            >
              Cancel
            </button>
            <button
              class="btn btn-sm btn-primary"
              style="margin-left: 6px"
              @click="confirm_start"
            >
              Start import
            </button>
          </div>
        </div>
      </div>
      <p v-if="local_dump_enabled">
        <button
          class="btn btn-outline-primary btn-sm"
          @click="pick_local_dump"
        >
          Load a CBGM dump file (work locally)&hellip;
        </button>
        <span class="text-muted" style="margin-left: 0.5rem;">
          Open your own CBGM database dump and work on it locally &mdash;
          nothing is saved back to any VMRCRE.
        </span>
      </p>
      <p v-if="offline && projects.length" class="text-muted">
        <em>Offline</em> &mdash; showing the projects already loaded on this
        computer. <a :href="vmrcre_login_url">Log in</a> when you're back online
        to see all the projects you can work on.
      </p>
      <table
        v-if="projects.length"
        class="table table-bordered table-hover"
      >
        <tbody>
          <tr>
            <th></th>
            <th>Project</th>
            <th>Book</th>
            <th>User group</th>
            <th>CBGM</th>
          </tr>
          <template v-for="g of grouped_projects">
          <tr
            v-if="grouped_projects.length > 1"
            :key="'grp-' + g.id"
            class="conn-group"
          >
            <td colspan="5">
              <span class="conn-badge">{{ g.label }}</span>
              <span v-if="g.local" class="text-muted conn-note">
                &mdash; loaded from a dump; edited locally, not saved to any
                VMRCRE
              </span>
              <span v-else-if="!g.active" class="text-muted conn-note">
                &mdash; read-only here; choose &ldquo;{{ g.label }}&rdquo; in
                <em>Connect to&hellip;</em> to save back
              </span>
            </td>
          </tr>
          <tr v-for="p of g.projects" :key="row_key(p)">
            <td style="width:50px; text-align:center;">
              <i class="fas fa-folder-open" style="font-size: 20px;"></i>
            </td>
            <td class="app_name">{{ p.name }}</td>
            <td>{{ p.object_part }}</td>
            <td>{{ p.user_group }}</td>
            <td class="cbgm-action" style="min-width: 260px; position: relative;">
              <span v-if="importing(p)" class="import-progress">
                <span class="bar">
                  <span class="fill" :style="{ width: percent(p) + '%' }"></span>
                </span>
                {{ p.import.message }}
                <template v-if="p.import.total"
                  >({{ p.import.done }}/{{ p.import.total }})</template
                >
              </span>
              <template v-else>
                <a
                  v-if="p.instance_root"
                  class="btn btn-sm btn-success"
                  :href="'/' + p.instance_root"
                  >Open</a
                >
                <button
                  v-else
                  class="btn btn-sm btn-primary"
                  @click="open_start_dialog(p)"
                >
                  Start CBGM
                </button>
                <span v-if="errored(p)" class="text-danger" style="margin-left:6px;">
                  {{ p.import.message }}
                </span>
                <button
                  class="btn btn-sm btn-light cbgm-more"
                  title="More options"
                  @click="toggle_menu(p)"
                >
                  &ctdot;
                </button>
                <div v-if="menu_open === row_key(p)" class="cbgm-menu">
                  <a @click="pick_dump(p)">Load from CBGM dump file&hellip;</a>
                  <a v-if="p.instance_root" @click="reload_ntvmr(p)"
                    >Reload from {{ p.connection_label || "NTVMR" }}</a
                  >
                  <a v-if="p.instance_root" @click="refresh_all(p)"
                    >Refresh All Decisions</a
                  >
                  <a v-if="p.instance_root" @click="recompute(p)"
                    >Recompute coherence</a
                  >
                </div>
              </template>
            </td>
          </tr>
          </template>
        </tbody>
      </table>
      <p v-else-if="!projects_loaded" class="text-muted">
        Loading your projects&hellip;
      </p>
      <p v-else-if="offline">
        <em>Offline</em> &mdash; no CBGM projects are loaded on this computer
        yet. Connect to the internet and log in to start one.
      </p>
      <p v-else-if="!is_logged_in">
        <a :href="vmrcre_login_url">Log in</a> to see the projects you can work
        on.
      </p>
      <p v-else>
        You are not a member of any projects yet.
      </p>

      <br /><br />
      <h4>
        Steps for installing a local, editable version of the CBGM for Acts and
        Mark
      </h4>
      <p></p>
      <ol>
        <li>
          You need to install the free containerization software
          <a href="https://www.docker.com/" target="_blank">Docker</a>:
        </li>
        <ul>
          <li>
            for Windows see:
            <a
              href="https://docs.docker.com/docker-for-windows/install/"
              target="_blank"
              >Docker for Windows</a
            >
          </li>
          <li>
            for Mac see:
            <a
              href="https://docs.docker.com/docker-for-mac/install/"
              target="_blank"
              >Docker for Mac</a
            >
          </li>
          <li>
            for Debian Linux see:
            <a href="https://docs.docker.com/compose/install/" target="_blank"
              >Docker for Debian Linux</a
            >
          </li>
        </ul>
        <br />
        <p>
          <strong>Important: </strong>Windows users please use this short guide:
          <a href="/pdfs/DockerGuideWindows.pdf" target="_blank"
            >Installing the CBGM Tool via Docker on Windows</a
          >
        </p>
        <p>
          <li>Create a new directory and change into it.</li>
          <li>
            Download
            <a
              href="https://raw.githubusercontent.com/SCDH/intf-cbgm/master/docker/docker-compose.yml"
              target="_blank"
              >https://raw.githubusercontent.com/SCDH/intf-cbgm/master/docker/docker-compose.yml</a
            >
          </li>

          <li>
            Run:

            <code>docker-compose up</code><br />

            This will download the Docker containers and initialize the
            database. It will take some time depending on your internet
            connection speed and your PC.
          </li>

          <li>
            Test the installation: Point your browser to the url:
            <a href="http://localhost:5000" target="_blank"
              >http://localhost:5000</a
            >
            and use the application.
          </li>

          <li>When satisfied, hit Ctrl+C to stop the Docker service.</li>
        </p>
      </ol>

      <img :src="Docker" style="float:left; width:100px; margin-right: 1rem;" />
      <strong>Note</strong>: All newest docker images can be found at<br /><a
        href="https://hub.docker.com/r/scdh"
        target="_blank"
        >https://hub.docker.com/r/scdh</a
      ><br />
      &rarr;<a
        href="https://hub.docker.com/r/scdh/intf-cbgm-app-server"
        target="_blank"
        >intf-cbgm-app-server</a
      ><br />
      &rarr;<a
        href="https://hub.docker.com/r/scdh/intf-cbgm-db-server"
        target="_blank"
        >intf-cbgm-db-server</a
      ><br />
      <ol>
          <p>
              Troubleshooting for MacOS Monterey: Version 12 of MacOS uses port 5000 for AirPlay software, 
              which means port 5000 cannot be used for Docker. An easy solution is to disable port 5000 on MacOS, 
              which is described <a href ='https://anandtripathi5.medium.com/port-5000-already-in-use-macos-monterey-issue-d86b02edd36c' 
              target='_blank'>here.</a> 
          </p>
      </ol>

      <br /><br />
      <h4>
        Video tutorial for installing a local, editable version of the CBGM
        (Mac)
      </h4>
      <br />
      <iframe
        width="560"
        height="315"
        src="https://www.youtube.com/embed/k0_tlbz_YVQ"
        title="YouTube video player"
        frameborder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen
      ></iframe>
      
      </div>
    </div>
  </div>
</template>

<script>
/**
 * Project list component.  List the available projects.
 *
 * A project is one book of the NT and one phase.
 *
 * @component client/project_list
 * @author Marcello Perathoner
 */
import { mapGetters } from "vuex";
import axios from "axios";
import url from "url";

import ECMActs from "../images/ECMActs.jpg";
import Docker from "../images/docker.png";
import { login_url } from "../js/connections";

// The user-configurable import options (mirrors the importer's
// DEFAULT_OPTIONS in ntvmrimport.py); the defaults reproduce the classic
// hard-wired behaviour.  Persisted server-side into the instance .conf and
// echoed back on projects.json (import_options) so a Reload pre-fills them.
function default_start_options() {
  return {
    doc_ranges: "",
    firsthand_only: true,
    collapse_regularized: true,
    collapse_nonsense: true,
    collapse_unsure: true,
    exclude_supplements: false
  };
}

export default {
  data: function() {
    return {
      ECMActs: ECMActs,
      Docker: Docker,
      projects: [],
      projects_loaded: false,
      offline: false,
      menu_open: null,
      start_dialog: null, // project whose import-options dialog is open
      start_options: default_start_options()
    };
  },
  computed: {
    ...mapGetters(["is_logged_in", "active_connection", "local_dump_enabled"]),
    // Group the project list by source backend, active connection first.  See
    // vmrcre/CONNECTIONS.md.
    grouped_projects: function() {
      const active_id = this.active_connection ? this.active_connection.id : null;
      const index = {};
      const groups = [];
      for (const p of this.projects) {
        const id = p.connection_id || "";
        if (!(id in index)) {
          index[id] = {
            id: id,
            label: p.connection_label || "VMRCRE",
            active: id === active_id,
            // Local (dump-loaded) projects have no backend to "reconnect to".
            local: !!p.local || id === "__local__",
            projects: []
          };
          groups.push(index[id]);
        }
        index[id].projects.push(p);
      }
      groups.sort((a, b) =>
        a.active === b.active ? a.label.localeCompare(b.label) : a.active ? -1 : 1
      );
      return groups;
    },
    vmrcre_login_url: function() {
      return login_url(this.active_connection);
    }
  },
  created: function() {
    const vm = this;
    // The user's NTVMR projects (server proxies project membership for us).
    axios
      .get(url.resolve(window.api_base_url, "projects.json"))
      .then(function(r) {
        vm.projects = r.data.data.projects || [];
        vm.offline = !!r.data.data.offline;
        vm.projects_loaded = true;
        // If an import is already running (e.g. after a page reload), resume
        // polling so its progress keeps updating.
        if (vm.projects.some(vm.importing)) vm.ensure_polling();
      })
      .catch(function() {
        vm.projects_loaded = true;
      });
  },
  beforeDestroy: function() {
    if (this._poll) clearInterval(this._poll);
  },
  methods: {
    importing: function(p) {
      return (
        p.import &&
        ["provisioning", "importing", "restoring", "refreshing", "recomputing"].indexOf(
          p.import.state
        ) !== -1
      );
    },
    // A project id is only unique per backend, so key rows / the open menu by
    // (connection, project).
    row_key: function(p) {
      return (p.connection_id || "") + ":" + p.project_id;
    },
    toggle_menu: function(p) {
      const k = this.row_key(p);
      this.menu_open = this.menu_open === k ? null : k;
    },
    pick_dump: function(p) {
      this._dump_project = p;
      this.menu_open = null;
      this.$refs.dump_input.click();
    },
    dump_selected: function(e) {
      const vm = this;
      const file = e.target.files && e.target.files[0];
      e.target.value = "";
      const p = vm._dump_project;
      if (!file || !p) return;

      function upload(force) {
        const fd = new FormData();
        fd.append("dump", file);
        fd.append("name", p.name);
        fd.append("object_part", p.object_part || "");
        fd.append("task_type_id", p.task_type_id || "");
        fd.append("user_group", p.user_group || "");
        fd.append("user_group_id", p.user_group_id || "");
        if (force) fd.append("force", "true");
        vm.$set(p, "import", {
          state: "provisioning",
          message: "uploading dump",
          done: 0,
          total: 0
        });
        axios
          .post(
            url.resolve(
              window.api_base_url,
              "projects/" + p.project_id + "/load_dump.json"
            ),
            fd
          )
          .then(function(response) {
            const d = (response.data && response.data.data) || response.data || {};
            if (d.needs_sync) {
              // unsynced edits would be wiped by the DB recreate
              vm.$set(p, "import", null);
              if (
                window.confirm(
                  d.pending +
                    " unsynced edit(s) on this project will be LOST if you reload" +
                    " from a dump.\n\nOK = discard them and reload.\nCancel = keep" +
                    ' them (open the project and use "Sync now" first).'
                )
              ) {
                upload(true);
              }
              return;
            }
            // A dump load against a not-yet-imported project mints a fresh local
            // id server-side; adopt it so polling/Open target it (on a reload it
            // just equals the current id).
            if (d.pid != null) p.project_id = String(d.pid);
            if (d.status) vm.$set(p, "import", d.status);
            vm.ensure_polling();
          })
          .catch(function(err) {
            vm.$set(p, "import", {
              state: "error",
              message:
                (err.response && err.response.statusText) || "upload failed"
            });
          });
      }
      upload(false);
    },
    // Load a user's own CBGM dump as a NEW purely-local project (no VMRCRE).
    // Unlike pick_dump/dump_selected (which reload INTO an existing project
    // row), this needs no login and no existing project.  See CONNECTIONS.md.
    pick_local_dump: function() {
      this.$refs.local_dump_input.click();
    },
    local_dump_selected: function(e) {
      const vm = this;
      const file = e.target.files && e.target.files[0];
      e.target.value = "";
      if (!file) return;
      const suggested = file.name.replace(/\.(dump|sql|backup|pgdump)$/i, "");
      const name = window.prompt("Name for this local project:", suggested);
      if (name === null) return; // cancelled

      // A temporary row so the user sees upload/restore progress right away; it
      // adopts the server-assigned id, and is replaced by the real row when the
      // finished import reloads the list.
      const placeholder = {
        project_id: "pending-" + Date.now(),
        name: name || "Local project",
        object_part: "",
        user_group: "",
        connection_id: "__local__",
        connection_label: "Local",
        local: true,
        instance_root: null,
        import: {
          state: "provisioning",
          message: "uploading dump",
          done: 0,
          total: 0
        }
      };
      vm.projects.push(placeholder);

      const fd = new FormData();
      fd.append("dump", file);
      fd.append("name", name || "Local project");
      axios
        .post(url.resolve(window.api_base_url, "load_local_dump.json"), fd)
        .then(function(r) {
          const d = (r.data && r.data.data) || r.data || {};
          if (d.started === false) {
            vm.$set(placeholder, "import", {
              state: "error",
              message: d.error || "could not load dump"
            });
            return;
          }
          // Match the server's id so import_status polling finds it.
          placeholder.project_id = String(d.pid);
          if (d.status) vm.$set(placeholder, "import", d.status);
          vm.ensure_polling();
        })
        .catch(function(err) {
          vm.$set(placeholder, "import", {
            state: "error",
            message:
              (err.response &&
                (err.response.data &&
                  err.response.data.error)) ||
              (err.response && err.response.statusText) ||
              "upload failed"
          });
        });
    },
    // Both Start CBGM and Reload go through the import-options dialog; a
    // reload pre-fills the options the project was originally imported with
    // (echoed back on projects.json from the instance .conf).
    open_start_dialog: function(p) {
      this.menu_open = null;
      const opts = default_start_options();
      if (p.import_options) {
        try {
          Object.assign(opts, JSON.parse(p.import_options));
        } catch (e) {
          // unreadable blob: fall back to the defaults
        }
      }
      this.start_options = opts;
      this.start_dialog = p;
    },
    confirm_start: function() {
      const p = this.start_dialog;
      this.start_dialog = null;
      if (p) this.startCbgm(p, this.start_options);
    },
    reload_ntvmr: function(p) {
      this.open_start_dialog(p); // re-runs the NTVMR import
    },
    refresh_all: function(p) {
      const vm = this;
      vm.menu_open = null;
      if (!p.instance_root) return;
      // offer (not force) a coherence recompute once the refresh completes
      p._offer_recompute = true;
      vm.$set(p, "import", {
        state: "refreshing",
        message: "loading decisions",
        done: 0,
        total: 0
      });
      axios
        .post(url.resolve(window.api_base_url, p.instance_root + "editorial/refresh_all.json"))
        .then(function() {
          vm.ensure_polling();
        })
        .catch(function(e) {
          vm.$set(p, "import", {
            state: "error",
            message: (e.response && e.response.statusText) || "refresh failed"
          });
        });
    },
    recompute: function(p) {
      const vm = this;
      vm.menu_open = null;
      vm.$set(p, "import", {
        state: "recomputing",
        message: "starting",
        done: 0,
        total: 0
      });
      axios
        .post(
          url.resolve(
            window.api_base_url,
            "projects/" + p.project_id + "/recompute.json"
          )
        )
        .then(function(r) {
          const d = (r.data && r.data.data) || r.data || {};
          if (d.started === false) {
            vm.$set(p, "import", {
              state: "error",
              message: d.error || "could not start recompute"
            });
            return;
          }
          vm.ensure_polling();
        })
        .catch(function(e) {
          vm.$set(p, "import", {
            state: "error",
            message: (e.response && e.response.statusText) || "request failed"
          });
        });
    },
    done: function(p) {
      return p.import && p.import.state === "done";
    },
    errored: function(p) {
      return p.import && p.import.state === "error";
    },
    percent: function(p) {
      if (!p.import || !p.import.total) return 0;
      return Math.round((100 * p.import.done) / p.import.total);
    },
    startCbgm: function(p, options) {
      const vm = this;
      const opts = options || default_start_options();
      const data = new URLSearchParams();
      data.append("object_part", p.object_part);
      data.append("name", p.name);
      data.append("task_type_id", p.task_type_id || "");
      data.append("user_group", p.user_group || "");
      data.append("user_group_id", p.user_group_id || "");
      for (const [key, val] of Object.entries(opts)) {
        data.append(key, typeof val === "boolean" ? String(val) : val || "");
      }
      vm.$set(p, "import", {
        state: "provisioning",
        message: "queued",
        done: 0,
        total: 0
      });
      axios
        .post(
          url.resolve(
            window.api_base_url,
            "projects/" + p.project_id + "/start.json"
          ),
          data
        )
        .then(function(r) {
          const d = (r.data && r.data.data) || r.data || {};
          if (d.started === false) {
            vm.$set(p, "import", {
              state: "error",
              message: d.error || "could not start CBGM"
            });
            return;
          }
          // The server mints a LOCAL id for a fresh import (distinct from the
          // remote projectID, so backends can't collide).  Adopt it so
          // import_status polling and, later, Open target the right project.
          if (d.pid != null) p.project_id = String(d.pid);
          if (d.status) vm.$set(p, "import", d.status);
          vm.ensure_polling();
        })
        .catch(function(e) {
          vm.$set(p, "import", {
            state: "error",
            message: (e.response && e.response.statusText) || "request failed"
          });
        });
    },
    ensure_polling: function() {
      const vm = this;
      if (vm._poll) return;
      vm._poll = setInterval(function() {
        axios
          .get(url.resolve(window.api_base_url, "import_status.json"))
          .then(function(r) {
            const imports = r.data.data.imports || {};
            let active = false;
            for (const p of vm.projects) {
              const st = imports[p.project_id];
              if (st) vm.$set(p, "import", st);
              if (vm.importing(p)) active = true;
            }
            if (!active) {
              clearInterval(vm._poll);
              vm._poll = null;
              // A finished Refresh All optionally chains into a coherence
              // recompute (not forced — it can take a while; you may just want
              // the decisions synced/loaded and nothing more).
              let chained = false;
              for (const p of vm.projects) {
                if (!p._offer_recompute) continue;
                p._offer_recompute = false;
                if (
                  p.import &&
                  p.import.state === "done" &&
                  window.confirm(
                    "Decisions refreshed. Recompute coherence (closest" +
                      " relatives & textual flow) now? This can take a while" +
                      " — you can also skip it and do it later."
                  )
                ) {
                  vm.recompute(p);
                  chained = true;
                }
              }
              if (chained) return; // recompute restarted polling; defer reload
              // Reload the list so a just-finished import shows its "Open" link
              // (its instance is now mounted).
              vm.refresh_projects();
            }
          })
          .catch(function() {
            // Transient poll failure: keep polling; the next tick retries.
          });
      }, 1500);
    },
    refresh_projects: function() {
      const vm = this;
      axios
        .get(url.resolve(window.api_base_url, "projects.json"))
        .then(function(r) {
          vm.projects = r.data.data.projects || [];
        })
        .catch(function() {
          // Leave the current list in place on a transient fetch failure.
        });
    }
  }
};
</script>

<style lang="scss">
/* project_list.vue */

div.vm-project-list {
  .img-guide {
    height: 200px;
  }

  tr.conn-group td {
    background-color: #eef1f3;
    border-top: 2px solid #8c9598;
    padding-top: 0.4rem;
    padding-bottom: 0.4rem;
  }
  .conn-badge {
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-size: 0.9rem;
  }
  .conn-note {
    margin-left: 0.5rem;
    font-size: 0.85rem;
  }

  .cbgm-more {
    margin-left: 6px;
    font-weight: bold;
    border: 1px solid #ccc;
  }

  .cbgm-menu {
    position: absolute;
    z-index: 20;
    right: 8px;
    margin-top: 4px;
    min-width: 220px;
    background: #fff;
    border: 1px solid #bbb;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
    a {
      display: block;
      padding: 8px 12px;
      cursor: pointer;
      color: #222;
      &:hover {
        background: #f0f4f7;
        text-decoration: none;
      }
      & + a {
        border-top: 1px solid #eee;
      }
    }
  }

  .cbgm-start-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 1000;
    background: rgba(0, 0, 0, 0.35);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .cbgm-start-dialog {
    background: #fff;
    border-radius: 6px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
    padding: 1.25rem 1.5rem;
    width: 480px;
    max-width: 92vw;
    max-height: 90vh;
    overflow-y: auto;

    .form-group,
    .form-check {
      margin-bottom: 0.5rem;
    }
    .cbgm-suffixes {
      margin-top: 0.75rem;
    }
  }

  .import-progress {
    font-size: 0.85em;
    .bar {
      display: inline-block;
      width: 120px;
      height: 8px;
      background: #e0e0e0;
      border-radius: 4px;
      overflow: hidden;
      vertical-align: middle;
      margin-right: 6px;
      .fill {
        display: block;
        height: 100%;
        background: #41799e;
        transition: width 0.4s ease;
      }
    }
  }

  td.app_name {
    width: 20%;
  }

  td.can_edit {
    width: 1%;
  }

  span.fas {
    font-size: 150%;
    color: red;
  }

  table {
    margin-top: 2em;
  }

  div.logos {
    margin-top: 2em;

    img {
      height: 100px;
      padding-right: 1em;
    }
  }
}
</style>
