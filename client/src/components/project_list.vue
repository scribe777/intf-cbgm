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
      <h4>Currently online projects</h4>
      <br />
      <table class="table table-bordered table-hover">
        <tbody>
          <tr>
            <th></th>
            <th>Project</th>
            <th>Editable</th>
            <th>Description</th>
            <th>Guide</th>
          </tr>
          <router-link
            v-for="i of $store.state.instances"
            :key="i.application_root"
            tag="tr"
            :to="'/' + i.application_root"
          >
          <td style="width:50px; text-align:center;"><i class="fas fa-folder-open" style="font-size: 20px;"></i></td>
            <td class="app_name">
              <a>{{ i.application_name }}</a>
            </td>
            <td class="can_edit" style="text-align:center;">
              <span v-if="i.user_can_write" class="fas fa-pen-square" style="color: #41799e;"/>
            </td>
            <td class="app_desc">
              {{ i.application_description }}
            </td>
            <td class="guide">
              <div v-if="i.application_name.includes('Acts')">
                <a href="/pdfs/GenQ4_Guide.pdf" target="_blank"
                  >Short Guide (PDF) for Acts</a
                >
              </div>
              <div v-if="i.application_name.includes('Mark')">
                <a href="/pdfs/Short_Guide_CBGM_Mark_KW.pdf" target="_blank"
                  >Short Guide (PDF) for Mark</a
                >
              </div>
            </td>
          </router-link>
        </tbody>
      </table>

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
/* import these images for the side-effect only: make webpack pack these files. */

import actsguide from "../images/actsguide.jpg";
import markguide from "../images/markguide.jpg";
import ECMActs from "../images/ECMActs.jpg";
import Docker from "../images/docker.png";

export default {
  data: function() {
    return {
      markguide: markguide,
      actsguide: actsguide,
      ECMActs: ECMActs,
      Docker: Docker
    };
  }
};
</script>

<style lang="scss">
/* project_list.vue */

div.vm-project-list {
  .img-guide {
    height: 200px;
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
