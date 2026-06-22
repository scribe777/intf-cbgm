<template>
  <div class="container footer">
    <div class="row-top">
      <a class="nav-slideup six columns" href="#top">nach oben<span></span></a>
    </div>
    <footer>
      <div class="container">
        <div class="row">
          <div class="col-sm-4">
            <h2>Contact</h2>
            <address>
              <span>Westfälische Wilhelms-Universität Münster</span><br /><span
                >Universität Münster</span
              ><br />
              <span>Institut für Neutestamentliche Textforschung</span><br />
              <span>
                Pferdegasse 1
                <br /><span>48143</span> <span>Münster</span> </span
              ><br /><br />
              Tel: <span>+49 251 83-22581</span><br />Fax:
              <span>+49 251 83-22582</span><br /><a
                class="u-email"
                href="mailto:paulson@uni-muenster.de"
                >Dr. Gregory S. Paulson</a
              >
            </address>
            <a href="https://www.youtube.com/wwumuenster" target="_blank">
              <span class="wwu-symbol"></span></a
            >
            <a href="https://www.facebook.com/wwumuenster" target="_blank">
              <span class="wwu-symbol">f</span></a
            >
            <a href="https://twitter.com/WWU_Muenster" target="_blank">
              <span class="wwu-symbol"></span></a
            >
            <a href="https://www.instagram.com/wwu_muenster/" target="_blank">
              <span class="wwu-symbol"></span></a
            >
          </div>
          <div class="col-sm-4">
            <h2>Partners</h2>
                      <div class="row logos">
            <div class="col-6">
              <a href="http://egora.uni-muenster.de/intf/index_en.shtml"
                ><img :src="intf_logo"
              /></a>
            </div>
            <div class="col-6">
              <a href="http://www.awk.nrw.de"><img :src="awk_logo"/></a>
            </div>
            <div class="col-6">
              <a href="http://cceh.uni-koeln.de"><img :src="cceh_logo"/></a>
            </div>
            <div class="col-6">
              <a href="https://www.uni-muenster.de/SCDH/"
                ><img :src="scdh_logo"
              /></a>
            </div>
          </div>
          </div>



          <div class="col-sm-4">
            <div class="claim">
              <a
                href="https://www.uni-muenster.de/de/"
                title="Startseite der WWU"
                class="claim"
                >living.knowledge</a
              >
            </div>
          </div>
        </div>
      </div>
    </footer>

    <div class="container sub-footer">
      <div class="row">
        <div class="col-sm-9">
          <nav class="nav-footer">
            <ul>
              <li class="js" style="width: 50.4833px; max-width: 50.4833px;">
                <a href="https://www.uni-muenster.de/uv/wwuaz/unilist/en"
                  >Index</a
                >
              </li>
              <li class="js" style="width: 72.8833px; max-width: 72.8833px;">
                <a href="https://www.uni-muenster.de/de/en/sitemap.html"
                  >Site Map</a
                >
              </li>
              <li class="js" style="width: 92.9667px; max-width: 92.9667px;">
                <a href="https://www.uni-muenster.de/de/en/impressum.html"
                  >Impressum</a
                >
              </li>
              <li class="js" style="width: 164.867px; max-width: 164.867px;">
                <a
                  href="https://www.uni-muenster.de/de/en/datenschutzerklaerung.html"
                  >Data Privacy Statement</a
                >
              </li>
              <li class="js" style="width: 132.5px; max-width: 132.5px;">
                <a
                  href="https://www.uni-muenster.de/de/en/barrierefreiheit.html"
                  >Accessibility</a
                >
              </li>
            </ul>
          </nav>
        </div>
        <div class="col-sm-3">
          <div class="name">
            <p>© 2021 Universität Münster</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import intf_logo from "../images/intf2021.jpeg";
import awk_logo from "../images/awk-logo-00.png";
import cceh_logo from "../images/cceh-logo.png";
import scdh_logo from "../images/scdh-logo.svg";

export default {
  data() {
    return {
      intf_logo: intf_logo,
      awk_logo: awk_logo,
      cceh_logo: cceh_logo,
      scdh_logo: scdh_logo
    };
  },
  computed: {}
};
</script>

<style lang="scss">
@import "bootstrap-custom";

img {
  width: 100px;
  margin: 0 2rem 2rem 0;
}

.footer {
  margin-top: 3rem;
  font-family: Metawebpro, Verdana, sans-serif;
}

.row-top {
  a {
    color: white;
    &:hover {
      color: white;
      text-decoration: none;
    }
  }
  background-color: var(--brand-color); // or #7ab51d;
  min-height: 39.15px;
  padding: 0.5rem;
  span {
    float: right;
    font-family: WWUSymbol, Verdana, sans-serif;
    transform: rotate(-90deg);
  }
}

footer {
  margin-top: 1rem;
  margin-bottom: 1rem;
  padding: 1rem;
  background-color: #3e3e3c;
  min-height: 200px;
  color: white;

  a {
    color: white;
    font-size: 1rem;
    text-decoration: none;
    &:hover {
      color: inherit;
      text-decoration: none;
    }
  }

  address {
    line-height: 1.2rem;
    font-size: 1rem;
  }

  h2 {
    font-family: MetawebproBold, Verdana, sans-serif;
    font-size: 1.7em;
    font-weight: 800;
    letter-spacing: 0.232em;
    border-bottom: 1px solid;
    text-transform: uppercase;
  }
  .wwu-symbol {
    margin: 0.5rem;
    font-family: WWUSymbol, Verdana, sans-serif;
    font-size: 52px;
  }
}

.nav-footer {
  ul {
    margin-left: -2rem;
    li {
      display: inline;
      padding: 0.25rem;
    }
    li ~ li {
      border-left: 1px solid;
    }
  }
}

.sub-footer {
  text-transform: uppercase;
  .name {
    float: right;
  }
  a {
    color: #3e3e3c;
    &:hover {
      color: #3e3e3c;
    }
  }
}

.claim a {
  font-weight: 700;
  float: right;
  font-size: 36px;
  font-weight: bold;
  text-align: center;
  padding-right: 0;
  letter-spacing: -0.05em;
  &:hover {
    text-decoration: underline;
  }
}
</style>
