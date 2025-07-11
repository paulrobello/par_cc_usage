###############################################################################
# Common make values.
lib    := pccu
lib_dir := par_cc_usage
run    := uv run
python := $(run) python
ruff   := $(run) ruff
pyright := $(run) pyright
build  := uv build
publish  := uv publish

#export UV_LINK_MODE=copy
export PIPENV_VERBOSITY=-1
##############################################################################
# Run the app.
.PHONY: run
run:	        # Run the app
	$(run) $(lib)

.PHONY: app_help
app_help:	        # Show app help
	$(run) $(lib) --help

.PHONY: monitor
monitor:	        # Run monitoring mode
	$(run) $(lib) monitor

.PHONY: list
list:	        # List token usage
	$(run) $(lib) list

.PHONY: init
init:	        # Initialize config file
	$(run) $(lib) init

.PHONY: clear_cache
clear_cache:	        # Clear file monitoring cache
	$(run) $(lib) clear-cache

.PHONY: test_webhook
test_webhook:	        # Test Discord webhook
	$(run) $(lib) test-webhook

.PHONY: debug_blocks
debug_blocks:	        # Debug block information
	$(run) $(lib) debug-blocks

.PHONY: debug_unified
debug_unified:	        # Debug unified block calculation
	$(run) $(lib) debug-unified

.PHONY: debug_activity
debug_activity:	        # Debug recent activity
	$(run) $(lib) debug-activity

.PHONY: analyze
analyze:	        # Analyze JSONL file (requires file path)
	@echo "Usage: make analyze FILE=path/to/file.jsonl"
	@if [ -n "$(FILE)" ]; then $(run) $(lib) analyze $(FILE); fi

.PHONY: dev
dev:	        # Run in dev mode (monitor with reload)
	$(run) --reload $(lib) monitor

##############################################################################
.PHONY: uv-lock
uv-lock:
	uv lock

.PHONY: uv-sync
uv-sync:
	uv sync

.PHONY: setup
setup: uv-lock uv-sync	        # use this for first time run

.PHONY: resetup
resetup: remove-venv setup			# Recreate the virtual environment from scratch

.PHONY: remove-venv
remove-venv:			# Remove the virtual environment
	rm -rf .venv

.PHONY: depsupdate
depsupdate:			# Update all dependencies
	uv sync -U

.PHONY: depsshow
depsshow:			# Show the dependency graph
	uv tree

.PHONY: shell
shell:			# Start shell inside of .venv
	$(run) bash
##############################################################################
# Checking/testing/linting/etc.
.PHONY: format
format:                         # Reformat the code with ruff.
	$(ruff) format src/$(lib_dir)

.PHONY: lint
lint:                           # Run ruff lint over the library
	$(ruff) check src/$(lib_dir) --fix

.PHONY: lint-unsafe
lint-unsafe:                           # Run ruff lint over the library
	$(ruff) check src/$(lib_dir) --fix --unsafe-fixes

.PHONY: typecheck
typecheck:			# Perform static type checks with pyright
	$(pyright)

.PHONY: typecheck-stats
typecheck-stats:			# Perform static type checks with pyright and print stats
	$(pyright) --stats

.PHONY: checkall
checkall: format lint typecheck test 	        # Check all the things

.PHONY: test
test:                           # Run tests with pytest
	$(run) pytest tests/ -v

.PHONY: test-cov
test-cov:                       # Run tests with coverage report
	$(run) pytest tests/ --cov=src/$(lib_dir) --cov-report=html --cov-report=term -v

.PHONY: test-fast
test-fast:                      # Run tests without verbose output
	$(run) pytest tests/ -q

.PHONY: pre-commit	        # run pre-commit checks on all files
pre-commit:
	pre-commit run --all-files

.PHONY: pre-commit-update	        # run pre-commit and update hooks
pre-commit-update:
	pre-commit autoupdate

##############################################################################
# Package/publish.
.PHONY: package
package: clean			# Package the library
	$(build)

.PHONY: spackage
spackage:			# Create a source package for the library
	$(build) --sdist

.PHONY: test-publish
test-publish: package		# Upload to testpypi
	$(publish) upload --index testpypi --check-url

.PHONY: publish
publish: package		# Upload to pypi
	$(publish) upload --check-url

##############################################################################
# Utility.

.PHONY: get-venv-name
get-venv-name:		# get venv python location
	$(run) which python

.PHONY: repl
repl:				# Start a Python REPL
	$(python)

.PHONY: clean
clean:				# Clean the build directories
	rm -rf build dist $(lib_dir).egg-info

.PHONY: help
help:				# Display this help
	@grep -Eh "^[a-z]+:.+# " $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.+# "}; {printf "%-20s %s\n", $$1, $$2}'

##############################################################################
# Housekeeping tasks.
.PHONY: housekeeping
housekeeping:			# Perform some git housekeeping
	git fsck
	git gc --aggressive
	git remote update --prune

### Makefile ends here
