FROM python:3.8-slim-bullseye

RUN	apt-get update && \
    apt-get install -y --no-install-recommends graphviz gosu postgresql-client openjdk-17-jre-headless && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN useradd --create-home ntg
WORKDIR /home/ntg

COPY .pgpass                /home/ntg/

RUN chown ntg:ntg .pgpass && chmod 600 .pgpass

COPY server                 /home/ntg/server
COPY ntg_common             /home/ntg/ntg_common
COPY instance/*.conf        /home/ntg/instance/
COPY client                 /home/ntg/client
COPY scripts/*.py           /home/ntg/scripts/
# The local-stemma AI service (jars + prompt + schema). Dormant unless the
# entrypoint sees AI_LOCALSTEMMA_ENABLED at container start.
COPY ai                     /home/ntg/ai
ENV  AI_CBGM_LOCAL_STEMMA_DEFAULT_SYSTEM_PROMPT=/home/ntg/ai/system.prompt

COPY docker-entrypoint.sh   /usr/local/bin/
RUN chown ntg:ntg /usr/local/bin/docker-entrypoint.sh
RUN chown ntg:ntg -R /home/ntg/client
# "Start CBGM" writes new instance .conf files here at runtime.
RUN chown ntg:ntg -R /home/ntg/instance
# Per-project instance confs land here (kept out of instance/ so it can be a
# persistent volume); see CBGM_PROJECTS_DIR.
RUN mkdir -p /home/ntg/projects && chown ntg:ntg /home/ntg/projects
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 5000

ENV PYTHONPATH /home/ntg:/home/ntg/server:/home/ntg/scripts

USER ntg

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["app-server"]

# ENTRYPOINT ["tail", "-f", "/dev/null"] # for debugging
