<template>
  <div class="vm-index">
    <div class="container bs-docs-container">
      <div v-if="$store.getters.can_read">
      <ul>
        <li><router-link
          class="biglink"
          :to="{ name: 'coherence', params: { passage_or_id: 1 } }"
          >Coherence and Textual Flow</router-link
        >
        </li><li><router-link class="biglink" :to="{ name: 'comparison' }"
          >Comparison of Witnesses</router-link
        >
        </li><li><router-link class="biglink" :to="{ name: 'find_relatives' }"
          >Find Relatives</router-link
        >
        </li></ul>
        <div v-if="$store.getters.can_read_private">
        <ul>
          </li><li><router-link class="biglink" :to="{ name: 'notes_list' }"
            >List of Notes</router-link
          >
          </li><li><router-link class="biglink" :to="{ name: 'checks_list' }"
            >List of Congruence Check Failures</router-link
          >
          </li><li><router-link class="biglink" :to="{ name: 'opt_stemma' }"
            >Optimal Substemma</router-link
          >
          </li><li><router-link class="biglink" :to="{ name: 'set_cover' }"
            >Minimum Set Cover</router-link
          ></li></ul>
        </div>
        
      </div>
    </div>
  </div>
</template>

<style lang="scss">
/* index.vue */

div.vm-index {
  ul li {
    &:hover {
      font-weight: bold;
    }
    list-style: disclosure-closed;
}
  a.biglink {
    display: block;
    font-size: 150%;
    margin: 1em 0;
    text-decoration: none
  }

  div.gdpr {
    margin-top: 1em;
  }
}
</style>
