all: front doc js-api
	python3 collect_static.py

js-api:
	cd frontend_v2/ && \
	mkdir -p dist/api/ && \
	cp src/api.ts dist/api/api.ts && \
	npx tsc dist/api/api.ts \
		--target ES2020 \
		--module ESNext \
		--outDir dist/api/ \
		--declaration

front:
	cd frontend_v2 && npm i && npm run build

doc:
	npm i && npm run docs:build

test:
	pytest test/cases/test_*.py --html=test/report/index.html --pdb

.PHONY: all test js-api front doc