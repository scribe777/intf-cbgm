<template>
  <div id="app">
    <page-header></page-header>
    <flash-messages></flash-messages>
    <router-view></router-view>
    <page-footer></page-footer>
  </div>
</template>

<script>
/**
 * App component.  The whole application.
 *
 * @component client/app
 * @author Marcello Perathoner
 */

import Vue from "vue";
import Vuex from "vuex";
import { mapGetters } from "vuex";
import VueRouter from "vue-router";
import axios from "axios";
import url from "url";

import d3common from "d3_common";

import page_header from "page_header.vue";
import page_footer from "page_footer.vue";
import flash_messages from "flash_messages.vue";
import prj_list from "project_list.vue";
import index from "index.vue";
import find_relatives from "find_relatives.vue";
import coherence from "coherence.vue";
import comparison from "comparison.vue";
import checks_list from "checks_list.vue";
import notes_list from "notes_list.vue";
import opt_stemma from "optimal_substemma.vue";
import set_cover from "set_cover.vue";
import notfound from "notfound.vue";

Vue.use(Vuex);
Vue.use(VueRouter);

const default_home = {
  caption: "Project Overview",
  route: "index"
};

const router = new VueRouter({
  mode: "history",
  routes: [
    {
      path: "/",
      component: prj_list,
      name: "prj_list",
      props: true,
      meta: {
        type: 'index',
        caption: "CBGM",
        home: default_home,
        projects: { caption: "Show all Projects", route: "prj_list" }
      }
    },
    {
      path: "/:app_id/:phase/",
      component: index,
      name: "index",
      props: true,
      meta: {
        type: 'overview',
        caption: "CBGM ",
        home: { caption: "INTF Website", route: "external.intf" },
        projects: { caption: "Show all Projects", route: "prj_list" }
        // home: { caption: "Back", route: "prj_list" }
      }
    },
    {
      path: "/:app_id/:phase/find_relatives",
      component: find_relatives,
      name: "find_relatives",
      props: true,
      meta: {
        type: 'subpage',
        caption: "Find Relatives",
        home: default_home,
        projects: { caption: "Show all Projects", route: "prj_list" }
      }
    },
    {
      path: "/:app_id/:phase/coherence/:passage_or_id",
      component: coherence,
      name: "coherence",
      props: true,
      meta: {
        type: 'subpage',
        caption: "Coherence and Textual Flow",
        home: default_home,
        projects: { caption: "Show all Projects", route: "prj_list" }
      }
    },
    {
      path: "/:app_id/:phase/comparison",
      component: comparison,
      name: "comparison",
      props: true,
      meta: {
        type: 'subpage',
        caption: "Comparison of Witnesses",
        home: default_home,
        projects: { caption: "Show all Projects", route: "prj_list" }
      }
    },
    {
      path: "/:app_id/:phase/notes",
      component: notes_list,
      name: "notes_list",
      props: true,
      meta: {
        type: 'subpage',
        caption: "List of Notes",
        home: default_home,
        projects: { caption: "Show all Projects", route: "prj_list" }
      }
    },
    {
      path: "/:app_id/:phase/checks",
      component: checks_list,
      name: "checks_list",
      props: true,
      meta: {
        type: 'subpage',
        caption: "List of Congruence Check Failures",
        home: default_home,
        projects: { caption: "Show all Projects", route: "prj_list" }
      }
    },
    {
      path: "/:app_id/:phase/opt_stemma",
      component: opt_stemma,
      name: "opt_stemma",
      props: true,
      meta: {
        type: 'subpage',
        caption: "Optimal Substemma",
        home: default_home,
        projects: { caption: "Show all Projects", route: "prj_list" }
      }
    },
    {
      path: "/:app_id/:phase/set_cover",
      component: set_cover,
      name: "set_cover",
      props: true,
      meta: {
        type: 'subpage',
        caption: "Minimum Set Cover",
        home: default_home,
        projects: { caption: "Show all Projects", route: "prj_list" }
      }
    },

    // external routes

    { path: "/user/sign-in", name: "user.login" },
    { path: "/user/profile", name: "user.profile" },
    { path: "/user/sign-out", name: "user.logout" },

    {
      path: "/intf",
      name: "external.intf",
      // hack because router cannot handle external links
      // See: https://github.com/vuejs/vue-router/issues/1280
      beforeEnter() {
        /* eslint-disable-next-line no-restricted-globals */
        location.href = "http://intf.uni-muenster.de/cbgm/acts/";
      }
    },

     { path: '/:pathMatch(.*)*', name: 'notfound', component: notfound },
  ]
});

const default_application = {
  name: "",
  read_access: "public",
  read_access_private: "nobody",
  write_access: "nobody"
};

const store = new Vuex.Store({
  state: {
    route_meta: {
      caption: "Index",
      home: default_home
    },
    api_url: "",
    instances: [],
    ranges: [],
    // Selectable VMRCRE backends ("Connect to..." menu) and the active one's id.
    // See vmrcre/CONNECTIONS.md.
    connections: [],
    active_connection_id: null,
    current_application: {
      ...default_application
    },
    current_user: {
      username: "anonymous",
      roles: ["public"]
    }
  },
  mutations: {
    instances(state, data) {
      state.instances = data;
    },
    connections(state, data) {
      state.connections = (data && data.connections) || [];
      state.active_connection_id = (data && data.active) || null;
    },
    api_url(state, data) {
      state.api_url = data;
    },
    route_meta(state, data) {
      state.route_meta = data;
      document.title = data.caption;
    },
    caption(state, data) {
      state.route_meta.caption = data;
      document.title = data;
    },
    current_user(state, data) {
      state.current_user = data;
    },
    current_application(state, data) {
      state.current_application = data;
    },
    passage(state, data) {
      Object.assign(state, data);
    },
    ranges(state, data) {
      state.ranges = data;
    }
  },
  getters: {
    api_url: (state) => state.api_url,
    connections: (state) => state.connections,
    active_connection: (state) =>
      state.connections.find((c) => c.id === state.active_connection_id) ||
      null,
    route_meta: (state) => state.route_meta,
    ranges: (state) => state.ranges,
    current_application: (state) => state.current_application,
    current_user: (state) => state.current_user,
    is_logged_in: (state) => {
      return state.current_user.username !== "anonymous";
    },
    can_read: (state) => {
      return state.current_user.roles.includes(
        state.current_application.read_access
      );
    },
    can_read_private: (state) => {
      return state.current_user.roles.includes(
        state.current_application.read_access_private
      );
    },
    can_write: (state) => {
      return state.current_user.roles.includes(
        state.current_application.write_access
      );
    }
  }
});

/*
 * Get application information *before* displaying the view.
 */

router.beforeEach((to, from, next) => {
  if (to.params.app_id) {
    const api_url = url.resolve(
      api_base_url,
      to.params.app_id + "/" + to.params.phase + "/"
    );
    if (api_url !== store.state.api_url) {
      const requests = [
        axios.get(url.resolve(api_url, "application.json")),
        axios.get(url.resolve(api_url, "ranges.json/"))
      ];
      Promise.all(requests)
        .then((responses) => {
          store.commit("current_application", responses[0].data.data);
          store.commit("ranges", responses[1].data.data);
          store.commit("api_url", api_url);
          store.commit("route_meta", to.matched[0].meta);
          next();
        })
        .catch((dummy_error) => {
          next(false);
        });
      return;
    }
    store.commit("route_meta", to.matched[0].meta);
    next();
    return;
  }
  store.commit("api_url", "");
  store.commit("route_meta", to.matched[0].meta);
  next();
});

/**
 * Ascend the VM tree until you find an api_url and use it as prefix to build
 * the full API url.
 *
 * @param    {String} suffix - Url suffix
 * @returns  {String} Full API url
 * @memberof module:client/app
 */

Vue.prototype.build_full_api_url = function(suffix) {
  let vm = this;
  /* eslint-disable-next-line no-constant-condition */
  while (true) {
    if (vm.api_url) {
      return url.resolve(vm.api_url, suffix);
    }
    if (!vm.$parent) {
      break;
    }
    vm = vm.$parent;
  }
  return url;
};

/**
 * Make a GET request to the API server.
 *
 * @param {String} suffix - Url suffix
 * @param {Object} config - Params for axios call
 * @returns {Promise}
 * @memberof module:client/app
 */

Vue.prototype.get = function(suffix, config = {}) {
  return axios.get(this.build_full_api_url(suffix), config);
};

Vue.prototype.post = function(suffix, config = {}) {
  return axios.post(this.build_full_api_url(suffix), config);
};

Vue.prototype.put = function(suffix, config = {}) {
  return axios.put(this.build_full_api_url(suffix), config);
};

/**
 * Trigger a native event.
 *
 * vue.js custom 'events' do not bubble, so they are useless.  Trigger a real
 * event that bubbles and can be caught by vue.js.
 *
 * @param {string} name - event name
 * @param {array}  data - data
 * @memberof module:client/app
 */

Vue.prototype.$trigger = function(name, data) {
  const event = new CustomEvent(name, {
    bubbles: true,
    detail: { data: data }
  });
  this.$el.dispatchEvent(event);
};

/* eslint-disable no-new */
export default {
  router: router,
  store: store,
  data: function() {
    return {
      api_base_url: api_base_url,
      bust: 1
    };
  },
  components: {
    "page-header": page_header,
    "page-footer": page_footer,
    "flash-messages": flash_messages
  },
  computed: {
    ...mapGetters(["api_url"])
  },
  methods: {
    // (Re)load instances + current user into the store.  Resolves true if a
    // (non-anonymous) NTVMR user is logged in.
    refresh_session() {
      const vm = this;
      return Promise.all([
        axios.get(url.resolve(vm.api_base_url, "info.json")),
        axios.get(url.resolve(vm.api_base_url, "user.json"))
      ])
        .then((responses) => {
          vm.$store.commit("instances", responses[0].data.data.instances);
          vm.$store.commit("current_user", responses[1].data.data);
          return responses[1].data.data.username !== "anonymous";
        })
        .catch(() => {
          // The local /api/ endpoints failed (server hiccup); keep whatever
          // session state we have rather than throwing an unhandled rejection.
          return false;
        });
    },
    // Load the VMRCRE connection registry + active connection (a LOCAL endpoint,
    // so it works offline too) and point window.vmrcre_api_url at the active
    // backend for the SSO handshake.  No active connection => standalone (no
    // SSO).  See vmrcre/CONNECTIONS.md.
    load_connections() {
      const vm = this;
      return axios
        .get(url.resolve(vm.api_base_url, "connections.json"))
        .then((r) => {
          const d = (r.data && r.data.data) || r.data || {};
          vm.$store.commit("connections", d);
          const active = vm.$store.getters.active_connection;
          window.vmrcre_api_url = active ? active.api_url : "";
        })
        .catch(() => {
          // Keep the api.conf.js fallback already in window.vmrcre_api_url.
        });
    }
  },
  async created() {
    const vm = this;
    // NTVMR single sign-on: if we just returned from the NTVMR login redirect
    // (auth/session/check?r=...), it appended ?vmrcreSession=<hash>.  Capture
    // it into a cookie on this origin so the server's request_loader can use
    // it, then drop it from the URL.  See vmrcre/README.md.
    const params = new URLSearchParams(window.location.search);
    const sess = params.get("vmrcreSession");
    const returned_from_dance = sess !== null;
    if (returned_from_dance) {
      if (sess && sess !== "null") {
        document.cookie =
          "vmrcreSession=" + encodeURIComponent(sess) + "; path=/; SameSite=Lax";
      }
      params.delete("vmrcreSession");
      const qs = params.toString();
      window.history.replaceState(
        {},
        "",
        window.location.pathname + (qs ? "?" + qs : "") + window.location.hash
      );
    }
    // Resolve the active VMRCRE backend (sets window.vmrcre_api_url) BEFORE the
    // SSO gate below, which keys off it.  No active connection => standalone.
    await vm.load_connections();
    // Automatic single sign-on.  If we have no session yet, bounce once through
    // the NTVMR -- a *top-level* redirect, so the browser sends the NTVMR
    // session cookie (a hidden iframe can't: it's third-party).  If the user is
    // logged into the NTVMR we come back with ?vmrcreSession=<hash> and are
    // logged in; if not, we come back with none and show "Log In".  A
    // sessionStorage guard makes this happen at most once, so logged-out users
    // don't loop.  See vmrcre/README.md.
    const has_cookie = document.cookie.indexOf("vmrcreSession=") !== -1;
    let tried = false;
    try {
      tried = window.sessionStorage.getItem("vmrcre_sso_tried") === "1";
    } catch (e) {
      tried = true; // no sessionStorage -> don't risk a loop
    }
    if (returned_from_dance) {
      try {
        window.sessionStorage.setItem("vmrcre_sso_tried", "1");
      } catch (e) {
        /* noop */
      }
    }
    if (!has_cookie && !tried && !returned_from_dance && window.vmrcre_api_url) {
      // Probe the NTVMR before doing a *top-level* SSO redirect.  A navigation
      // hangs forever when offline (blank screen, stuck on the NTVMR URL); a
      // fetch fails fast.  Only bounce if the NTVMR is actually reachable --
      // otherwise stay in the app and run offline.  See vmrcre/README.md.
      const ctrl = new AbortController();
      const timer = window.setTimeout(function() {
        ctrl.abort();
      }, 2500);
      window
        .fetch(window.vmrcre_api_url + "auth/session/check/", {
          mode: "no-cors",
          signal: ctrl.signal
        })
        .then(function() {
          window.clearTimeout(timer);
          // NTVMR reachable -> do the one-time SSO bounce (top-level redirect).
          try {
            window.sessionStorage.setItem("vmrcre_sso_tried", "1");
          } catch (e) {
            /* noop */
          }
          const here = window.location.origin + window.location.pathname;
          window.location.href =
            window.vmrcre_api_url +
            "auth/session/check/?r=" +
            encodeURIComponent(here);
        })
        .catch(function() {
          window.clearTimeout(timer);
          // Offline / NTVMR unreachable -> don't navigate away; run offline.
          vm.refresh_session();
        });
      return; // either bouncing (reachable) or refreshing offline (catch)
    }
    vm.refresh_session();
  },
  mounted() {
    // insert css for color palettes
    d3common.insert_css_palette(
      d3common.generate_css_palette(
        d3common.labez_palette,
        d3common.cliques_palette
      )
    );
  }
};

// The browser triggers hashchange only on window.  We want it on every app.
window.addEventListener("hashchange", function() {
  const event = new CustomEvent("hashchange");
  document.querySelectorAll(".want_hashchange").forEach(function(el) {
    el.dispatchEvent(event);
  });
});
</script>

<style lang="scss">
/* app.vue */

@import "../css/bootstrap-custom.scss";

/* bootstrap */

/* FIXME: this file is huge, maybe pick only the things we use */
@import "../../node_modules/bootstrap/scss/bootstrap";

/* List of icons at: http://astronautweb.co/snippet/font-awesome/ */

/* FIXME: this file is huge, maybe pick only the icons we use */
@import "../../node_modules/@fortawesome/fontawesome-free/css/fontawesome.css";
@import "../../node_modules/@fortawesome/fontawesome-free/css/solid.css";

@font-face { 
    font-family: "Metawebpro";
    src: url("../webfonts/metawebpro-normal.woff"); 
  }

@font-face { 
    font-family: "MetawebproBold";
    src: url("../webfonts/metawebpro-bold.woff"); 
  }

@font-face { 
  font-family: "WWUSymbol";
  src: url("../webfonts/wwu_symbol.woff"); 
}

a {
  font-size: 16px;
  text-decoration: none;
  font-weight: 700;
  color: #41799e;
  &:hover {
    font-weight: bold;
    text-decoration: underline;
    color: #41799e;
  }
}

p {
  font-size: 16px;
}

</style>
