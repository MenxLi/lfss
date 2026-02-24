all: front doc
	python3 collect_static.py

js-api:
	cd frontend_v2/src && npx tsc api.ts \
		--target ES2020 \
		--module ESNext \
		--outDir ../dist/api \
		--declaration && \
	cp api.ts ../dist/api/api.ts

front:
	cd frontend_v2 && npm i && npm run build

doc:
	npm i && npm run docs:build

test:
	pytest test/cases/test_*.py --html=test/report/index.html --pdb

.PHONY: all test js-api front doc