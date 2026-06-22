WEBPACK := node_modules/.bin/webpack --no-color
WEBPACK_DEV_SERVER := node_modules/.bin/webpack-dev-server
ESLINT := node_modules/.bin/eslint -f unix
STYLELINT := node_modules/.bin/stylelint --custom-formatter ./stylelint-unix-formatter.js

.PHONY: build build-production

AUX := build/index.html build/api.conf.js build-pdfs build-images

build: $(AUX)
	$(WEBPACK) --config webpack.dev.js

build-production: clean $(AUX)
	$(WEBPACK) --config webpack.prod.js

dev-server: $(AUX)
	$(WEBPACK_DEV_SERVER) --config webpack.dev.js

dev-server-production: clean $(AUX)
	$(WEBPACK_DEV_SERVER) --config webpack.prod.js

lint: eslint csslint

eslint:
	$(ESLINT) src/components/*.vue src/components/widgets/*.vue src/js/*.js src/*.js *.js *.json

csslint:
	$(STYLELINT) src/components/*.vue src/components/widgets/*.vue src/css/*.scss

clean:
	rm -rf build/*
	find . -name "*~" -delete

build/index.html: src/index.html
	-mkdir -p build
	cp $< $@

build/api.conf.js: src/api.conf.js
	-mkdir -p build
	cp $< $@

build/pdfs/Short_Guide_CBGM_Mark_KW.pdf: src/pdfs/Short_Guide_CBGM_Mark_KW.pdf
	-mkdir -p build/pdfs
	cp $< $@

build-pdfs:
	rm -rf build/pdfs
	mkdir build/pdfs
	cp -r src/pdfs build

build-images:
	rm -rf build/images
	mkdir build/images
	cp -r src/images build
