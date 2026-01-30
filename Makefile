test:
	pytest test/cases/test_*.py --html=test/report/index.html --pdb

api:
	cd frontend && npx tsc api.ts --target ES2020 --module ESNext

.PHONY: test api