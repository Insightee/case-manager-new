# InsightCase — common commands (see CONTRIBUTING.md)

.PHONY: check push-check release-check hooks

## Run full local gate before opening a PR (blocks if on main)
check push-check:
	./scripts/pre-push-check.sh

## Run before production release promote
release-check:
	./scripts/pre-release-check.sh

## Install git hooks (pre-commit + pre-push tests)
hooks:
	pip install pre-commit
	pre-commit install
	pre-commit install --hook-type pre-push

## CI parity only (tests + build, no branch check)
ci-parity:
	./scripts/run-ci-parity-checks.sh
