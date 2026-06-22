<template>
  <div class="container nav-header">
    <b-navbar>
      <a href="https://www.uni-muenster.de/en" target="_blank">
        <img
          :src="wwu_logo"
          style="float:left; width:280px; margin-right: 1rem;"
        />
      </a>
      <img :src="intf2021" style="position: absolute; right: 0; margin: 0;" />
    </b-navbar>
    <b-navbar class="main-nav">
      <b-navbar-nav>
        <b-nav-item href="/">Home</b-nav-item>

        <b-nav-item-dropdown
          v-for="project of navlist"
          :key="project.name"
          :text="project.name"
          class="prj"
          right
        >
          <b-dropdown-item
            v-for="link of project.links"
            :key="link.desc"
            :text="link.desc"
            :href="link.link"
            >{{ link.desc }}</b-dropdown-item
          >
        </b-nav-item-dropdown>
        <b-nav-item v-if="this.is_logged_in === false" style="position: absolute; right:0;" href="/user/sign-in"
          >Log In</b-nav-item
        >
        <b-nav-item v-if="this.is_logged_in === true" style="position: absolute; right:0;" href="/user/sign-out"
          >Log Out</b-nav-item
        >
      </b-navbar-nav>
    </b-navbar>
  </div>
</template>

<script>
/**
 * The page header with the violet ribbon.
 *
 * @component client/page_header
 * @author Marcello Perathoner
 */

import { mapGetters } from "vuex";
import { BNavbar } from "bootstrap-vue/src/components/navbar/navbar";
import { BNavbarNav } from "bootstrap-vue/src/components/navbar/navbar-nav";
import { BNavItem } from "bootstrap-vue/src/components/nav/nav-item";
import { BNavItemDropdown } from "bootstrap-vue/src/components/nav/nav-item-dropdown";
import { BDropdownItem } from "bootstrap-vue/src/components/dropdown/dropdown-item";

import wwu_logo from "../images/wwu_logo.svg";
import intf2021 from "../images/intf2021.jpeg";

export default {
  components: {
    "b-navbar": BNavbar,
    "b-navbar-nav": BNavbarNav,
    "b-nav-item": BNavItem,
    "b-nav-item-dropdown": BNavItemDropdown,
    "b-dropdown-item": BDropdownItem
  },
  data: function() {
    return {
      wwu_logo: wwu_logo,
      intf2021: intf2021
    };
  },
  computed: {
    ...mapGetters([
      "can_read",
      "is_logged_in",
      "current_application",
      "current_user",
      "route_meta"
    ]),
    navlist: function() {
      // only add public projects to navbar
      let links = this.$store.state.instances.filter((obj) =>
        obj["application_description"].includes("public")
      );
      let navlist = [];
      for (let entry of links) {
        let obj = {};
        obj["name"] = entry["application_name"];
        obj["links"] = [
          {
            desc: "Coherence and Textual Flow",
            link:
              window.location.origin +
              "/" +
              entry["application_root"] +
              "coherence/1"
          },
          {
            desc: "Comparison of Witnesses",
            link:
              window.location.origin +
              "/" +
              entry["application_root"] +
              "comparison"
          },
          {
            desc: "Find Relatives",
            link:
              window.location.origin +
              "/" +
              entry["application_root"] +
              "find_relatives"
          }
        ];
        navlist.push(obj);
      }
      return navlist;
    }
  }
};
</script>

<style lang="scss">
/* page_header.vue */
@import "bootstrap-custom";

.navbar-expand a {
  line-height: 4px;
  &:hover {
    text-decoration: underline;
    color: black;
  }
}

.nav-link.dropdown-toggle::after {
  display: none;
}

nav {
  padding: 0 !important;
}

.nav-header {
  margin-top: 2rem;
  margin-bottom: 3rem;
}

.navbar-nav {
  padding: 1rem;
}
.main-nav {
  border-bottom: 4px solid;
}

.prj {
  border-left: 1px solid;
}

.dropdown-menu-right {
  // use important to overwrite injectes css from bs4
  border: none !important;
  top: 40px !important;
  width: 50vw !important;
  right: -113px !important;
  left: -65px !important;
  border-radius: 0 !important;
  padding-bottom: 2rem !important;
  border-bottom: 4px solid black !important;

  li {
    border-bottom: 1px solid #8c9598;
    a {
      font-family: Metawebpro, Verdana, sans-serif;
      text-transform: uppercase;
      font-size: 20px;
      font-style: normal;
      font-weight: 400;
      line-height: 45px;
      &:hover {
        background-color: #666666;
        text-decoration: none;
        color: white;
      }
    }
  }
}

ul.navbar-nav li.nav-item a.nav-link {
  font-family: Metawebpro, Verdana, sans-serif;
  text-transform: uppercase;
  color: black;
  font-size: 20px;
  font-style: normal;
  font-weight: 400;
}

div.vm-page-header {
  background-color: #d2d2d2;
  margin-bottom: 2rem;

  div.bs-docs-header {
    margin: 0;
    padding: ($spacer * 0.5) 0 ($spacer * 0.25) 0;
    color: var(--light);
    background-color: var(--brand-color);

    @media print {
      /* compensate for missing div.login-nav */
      margin-bottom: $spacer;
      color: black;
      background-color: transparent;
    }
  }

  div.bs-docs-container {
    padding-top: ($spacer * 0.5);
    padding-bottom: ($spacer * 0.5);
  }

  div.login-nav {
    @media print {
      display: none !important;
    }
    a,
    span {
      font-size: 18px;
    }
  }

  div.login-required-message {
    color: red;
  }
}
</style>
