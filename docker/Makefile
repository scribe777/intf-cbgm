.PHONY: backup build clean run app-context \
        crosswire crosswire-app crosswire-db crosswire-login

# Node >= 17 ships OpenSSL 3, which this (pinned, older) webpack's module
# hashing rejects (ERR_OSSL_EVP_UNSUPPORTED).  Re-enable the legacy provider so
# the client build works on a modern node.  The flag is REJECTED by node < 17,
# so add it ONLY when needed -- the documented node v14 build keeps working.
NODE_MAJOR := $(shell node -v 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/')
ifeq ($(shell [ "$(NODE_MAJOR)" -ge 17 ] 2>/dev/null && echo 1),1)
export NODE_OPTIONS := $(NODE_OPTIONS) --openssl-legacy-provider
endif

# The CBGM local-stemma AI service (a small JVM co-process). Its source lives in
# the vmrcre repo; `make dist` there produces the jars + prompt + schema.
CBGM_AI_DIR ?= ../../vmrcre/contrib/ai/cbgm-ai

# Assemble the app build context: (re)build the Vue.js client and copy the
# source trees into this directory (= the Docker build context).
# Works with node v14.15.0 / npm v6.14.8 and with modern node (>=17; see above).
app-context: Makefile
	rm -rf ../client/build
	cd ../client && npm install
	cd ../client && $(MAKE)
	# copy all source folders into this folder so the Dockerfile can COPY them
	rm -rf client scripts server ntg_common ai
	mkdir client scripts
	cp -a ../server ../ntg_common .
	cp -a ../client/build/* ./client
	cp -a ../scripts/cceh/* ./scripts
	# the app imports ntvmrimport (NTVMR -> CBGM apparatus import driver),
	# which lives in scripts/python, not scripts/cceh
	cp -a ../scripts/python/ntvmrimport.py ./scripts
	# stage the local-stemma AI service (jars + prompt + schema) as ai/. The
	# JVM only runs at container start when AI_LOCALSTEMMA_ENABLED is set.
	$(MAKE) -C $(CBGM_AI_DIR) dist
	cp -a $(CBGM_AI_DIR)/dist ./ai

build: app-context
	# single-arch local dev images (intf/*)
	docker build -f Dockerfile.db --tag=intf/ntg-db-server  .
	docker build -f Dockerfile    --tag=intf/ntg-app-server .

# --------------------------------------------------------------------------- #
# Multi-arch publish to Docker Hub (crosswire/*)
#
# Requires podman 5.x with qemu-user-static binfmt registered for arm64
#   check:  ls /proc/sys/fs/binfmt_misc/qemu-aarch64
# and being logged in to Docker Hub (`make crosswire-login`, user scribe777).
#
#   make crosswire        # build + push BOTH images, amd64 + arm64
#   make crosswire-app    # just the app-server image
#   make crosswire-db     # just the (data-less) db-server image
#
# --no-cache is deliberate: it sidesteps a podman COPY-layer cache bug that
# can ship stale code into the pushed manifest.  Override defaults on the
# command line, e.g.  make crosswire-app TAG=test PLATFORMS=linux/arm64
# --------------------------------------------------------------------------- #
PODMAN    ?= podman
NS        ?= crosswire
TAG       ?= latest
PLATFORMS ?= linux/amd64,linux/arm64
APP_IMAGE := docker.io/$(NS)/cbgm-app-server:$(TAG)
DB_IMAGE  := docker.io/$(NS)/cbgm-db-server:$(TAG)
# Build into a DISTINCT local manifest-list name (…-mc), never the image name:
# if the image name has been `podman pull`ed it already exists as a plain
# image, and `build --manifest <that name>` then collides ("image is not a
# manifest list" at push).  The -mc names are only ever manifest lists.
APP_MANIFEST := cbgm-app-server-mc:$(TAG)
DB_MANIFEST  := cbgm-db-server-mc:$(TAG)

crosswire-login:
	$(PODMAN) login docker.io

crosswire-app: app-context
	-$(PODMAN) manifest rm $(APP_MANIFEST) 2>/dev/null
	$(PODMAN) build --no-cache --platform $(PLATFORMS) --manifest $(APP_MANIFEST) -f Dockerfile .
	$(PODMAN) manifest push --all $(APP_MANIFEST) docker://$(APP_IMAGE)

crosswire-db:
	-$(PODMAN) manifest rm $(DB_MANIFEST) 2>/dev/null
	$(PODMAN) build --no-cache --platform $(PLATFORMS) --manifest $(DB_MANIFEST) -f Dockerfile.db.empty .
	$(PODMAN) manifest push --all $(DB_MANIFEST) docker://$(DB_IMAGE)

crosswire: crosswire-app crosswire-db

# this command only works on a production server with a fully functional database
# backup:
# 	mkdir -p /tmp/backup
# 	pg_dump --format custom mark_ph31 -n ntg -T "ntg.original_*" -T "ntg.tmp_*" \
# 			--exclude-table-data="ntg.notes*" > /tmp/backup/mark_ph31.dump

run: build
	docker-compose up

cbgm: build
	docker-compose run ntg-app-server cbgm

# TODO integrate in gitlab registry of wwu.it
# push:
# 	cat ~/.dockerhubpass | docker login --username marcelloperathoner --password-stdin
# 	docker push cceh/ntg-app-server:latest
# 	docker push cceh/ntg-db-server:latest
# 	docker logout

clean:
	docker container stop $$(docker container ls -a -q)
	docker container rm   $$(docker container ls -a -q)
	docker network prune -f
	docker rmi -f $$(docker images --filter dangling=true -qa)
	docker volume rm $$(docker volume ls --filter dangling=true -q)
	docker rmi -f $$(docker images -qa)

clean-volume:
	docker-compose down --volumes
