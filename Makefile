# ------------------------------------------------------------------------------
# Makefile for zhmc-log-forwarder project
#
# Basic prerequisites for running this Makefile, to be provided manually:
#   One of these OS platforms:
#     Windows with CygWin
#     Linux (any)
#     OS-X
#   These commands on all OS platforms:
#     make (GNU make)
#     bash
#     rm, mv, find, tee, which
#   These commands on all OS platforms in the active Python environment:
#     python (or python3 on OS-X)
#     pip (or pip3 on OS-X)
#     twine
#   These commands on Linux and OS-X:
#     uname
# Environment variables:
#   PYTHON_CMD: Python command to use (OS-X needs to distinguish Python 2/3)
#   PIP_CMD: Pip command to use (OS-X needs to distinguish Python 2/3)
#   PACKAGE_LEVEL: minimum/latest - Level of Python dependent packages to use
# Additional prerequisites for running this Makefile are installed by running:
#   make develop
# ------------------------------------------------------------------------------

# Python / Pip commands
ifndef PYTHON_CMD
  PYTHON_CMD := python
endif
ifndef PIP_CMD
  PIP_CMD := pip
endif

# Package level
ifndef PACKAGE_LEVEL
  PACKAGE_LEVEL := latest
endif
ifeq ($(PACKAGE_LEVEL),minimum)
  pip_level_opts := -c minimum-constraints.txt
else
  ifeq ($(PACKAGE_LEVEL),latest)
    pip_level_opts := --upgrade
  else
    $(error Error: Invalid value for PACKAGE_LEVEL variable: $(PACKAGE_LEVEL))
  endif
endif

# Determine OS platform make runs on
ifeq ($(OS),Windows_NT)
  PLATFORM := Windows
else
  # Values: Linux, Darwin
  PLATFORM := $(shell uname -s)
endif

# Name of this package on Pypi
package_name := zhmc-log-forwarder

# Pypi package name translated to underscore (e.g. used for .whl files)
package_name_under := zhmc_log_forwarder

# Name of top level Python namespace
module_name := zhmc_log_forwarder

# Package version (full version, including any pre-release suffixes, e.g. "0.1.0.dev1")
# Note: The package version is defined in zhmc_log_forwarder/version.py.
package_version := $(shell $(PYTHON_CMD) setup.py --version)

# Python major version
python_major_version := $(shell $(PYTHON_CMD) -c "import sys; sys.stdout.write('%s'%sys.version_info[0])")

# Python major+minor version for use in file names
python_version_fn := $(shell $(PYTHON_CMD) -c "import sys; sys.stdout.write('%s%s'%(sys.version_info[0],sys.version_info[1]))")

# Directory for the generated distribution files
dist_dir := dist

# Distribution archives (as built by setup.py)
bdist_file := $(dist_dir)/$(package_name_under)-$(package_version)-py2.py3-none-any.whl
sdist_file := $(dist_dir)/$(package_name)-$(package_version).tar.gz

dist_files := $(bdist_file) $(sdist_file)

# Source files in the package
package_py_files := \
    $(wildcard $(module_name)/*.py) \
    $(wildcard $(module_name)/*/*.py) \

# Directory for generated API documentation
doc_build_dir := build_doc

# Directory where Sphinx conf.py is located
doc_conf_dir := docs

# Documentation generator command
doc_cmd := sphinx-build
doc_opts := -v -d $(doc_build_dir)/doctrees -c $(doc_conf_dir) .

# Dependents for Sphinx documentation build
doc_dependent_files := \
    $(doc_conf_dir)/conf.py \
    $(wildcard $(doc_conf_dir)/*.rst) \
    $(package_py_files) \

# Directory with test source files
test_dir := tests

# Test log
test_log_file := test_$(python_version_fn).log

# Source files with test code
test_py_files := \
    $(wildcard $(test_dir)/*.py) \
    $(wildcard $(test_dir)/*/*.py) \
    $(wildcard $(test_dir)/*/*/*.py) \

# Determine whether py.test has the --no-print-logs option.
pytest_no_log_opt := $(shell py.test --help 2>/dev/null |grep '\--no-print-logs' >/dev/null; if [ $$? -eq 0 ]; then echo '--no-print-logs'; else echo ''; fi)

# Flake8 config file
flake8_rc_file := .flake8

# PyLint config file
pylint_rc_file := .pylintrc

# Source files for check (with PyLint and Flake8)
check_py_files := \
    setup.py \
    $(package_py_files) \
    $(test_py_files) \

ifdef TESTCASES
pytest_opts := -k $(TESTCASES)
else
pytest_opts :=
endif

# Files to be built
build_files := $(bdist_file) $(sdist_file)

# Files the distribution archive depends upon.
dist_dependent_files := \
    setup.py \
    README.rst \
    requirements.txt \
    $(package_py_files) \

# No built-in rules needed:
.SUFFIXES:

.PHONY: help
help:
	@echo 'Makefile for $(package_name) project'
	@echo 'Package version will be: $(package_version)'
	@echo 'Uses the currently active Python environment: Python $(python_version_fn)'
	@echo 'Valid targets are (they do just what is stated, i.e. no automatic prereq targets):'
	@echo '  develop    - Prepare the development environment by installing prerequisites'
	@echo '  install    - Install package in active Python environment'
	@echo '  check      - Run Flake8 on sources and save results in: flake8.log'
	@echo '  pylint     - Run PyLint on sources and save results in: pylint.log'
	@echo '  test       - Run tests (and test coverage) and save results in: $(test_log_file)'
	@echo '               Does not include install but depends on it, so make sure install is current.'
	@echo '               Env.var TESTCASES can be used to specify a py.test expression for its -k option'
	@echo '  build      - Build the distribution files in: $(dist_dir)'
	@echo '               Builds: $(bdist_file) $(sdist_file)'
	@echo '  builddoc   - Build documentation in: $(doc_build_dir)'
	@echo '  all        - Do all of the above'
	@echo '  uninstall  - Uninstall package from active Python environment'
	@echo '  upload     - Upload the distribution files to PyPI (includes uninstall+build)'
	@echo '  clean      - Remove any temporary files'
	@echo '  clobber    - Remove any build products (includes uninstall+clean)'
	@echo '  pyshow     - Show location and version of the python and pip commands'
	@echo 'Environment variables:'
	@echo '  PACKAGE_LEVEL="minimum" - Install minimum version of dependent Python packages'
	@echo '  PACKAGE_LEVEL="latest" - Default: Install latest version of dependent Python packages'
	@echo '  PYTHON_CMD=... - Name of python command. Default: python'
	@echo '  PIP_CMD=... - Name of pip command. Default: pip'

.PHONY: develop
develop: develop_$(python_version_fn).done
	@echo '$@ done.'

.PHONY: install
install: install_$(python_version_fn).done
	@echo '$@ done.'

.PHONY: check
check: flake8.log
	@echo '$@ done.'

.PHONY: pylint
pylint: pylint.log
	@echo '$@ done.'

.PHONY: test
test: $(test_log_file)
	@echo '$@ done.'

.PHONY: build
build: $(build_files)
	@echo '$@ done.'

.PHONY: builddoc
builddoc: $(doc_build_dir)/html/docs/index.html
	@echo '$@ done.'

.PHONY: all
all: develop install check test build builddoc
	@echo '$@ done.'

.PHONY: upload
upload: _check_version uninstall $(dist_files)
ifeq (,$(findstring .dev,$(package_version)))
	@echo '==> This will upload $(package_name) version $(package_version) to PyPI!'
	@echo -n '==> Continue? [yN] '
	@bash -c 'read answer; if [ "$$answer" != "y" ]; then echo "Aborted."; false; fi'
	twine upload $(dist_files)
	@echo 'Done: Uploaded $(package_name) version to PyPI: $(package_version)'
	@echo '$@ done.'
else
	@echo 'Error: A development version $(package_version) of $(package_name) cannot be uploaded to PyPI!'
	@false
endif

.PHONY: uninstall
uninstall:
	bash -c '$(PIP_CMD) show $(package_name) >/dev/null; if [ $$? -eq 0 ]; then $(PIP_CMD) uninstall -y $(package_name); fi'
	@echo '$@ done.'

.PHONY: clobber
clobber: clean
	rm -Rf $(doc_build_dir) htmlcov .tox
	rm -f pylint.log flake8.log test_*.log $(bdist_file) $(sdist_file) *.done $(dist_dir)/$(package_name)-$(package_version)*.egg
	@echo 'Done: Removed all build products to get to a fresh state.'
	@echo '$@ done.'

.PHONY: clean
clean:
	rm -Rf build .cache $(package_name_under).egg-info .eggs
	rm -f MANIFEST MANIFEST.in AUTHORS ChangeLog .coverage
	find . -name "*.pyc" -delete -o -name "__pycache__" -delete -o -name "*.tmp" -delete -o -name "tmp_*" -delete
	@echo 'Done: Cleaned out all temporary files.'
	@echo '$@ done.'

.PHONY: pyshow
pyshow:
	which $(PYTHON_CMD)
	$(PYTHON_CMD) --version
	which $(PIP_CMD)
	$(PIP_CMD) --version
	@echo '$@ done.'

.PHONY: _check_version
_check_version:
ifeq (,$(package_version))
	$(error Package version could not be determined)
endif

pip_$(python_version_fn).done:
	rm -fv $@
	@echo 'Installing/upgrading pip, setuptools and wheel with PACKAGE_LEVEL=$(PACKAGE_LEVEL)'
	$(PYTHON_CMD) -m pip install $(pip_level_opts) pip setuptools wheel
	touch $@

develop_$(python_version_fn).done: pip_$(python_version_fn).done dev-requirements.txt requirements.txt
	rm -fv $@
	@echo 'Installing runtime and development requirements with PACKAGE_LEVEL=$(PACKAGE_LEVEL)'
	$(PIP_CMD) install $(pip_level_opts) -r dev-requirements.txt
	touch $@
	@echo 'Done: Installed runtime and development requirements'

install_$(python_version_fn).done: pip_$(python_version_fn).done requirements.txt setup.py $(package_py_files)
	rm -fv $@
	@echo 'Installing $(package_name) (editable) with PACKAGE_LEVEL=$(PACKAGE_LEVEL)'
	$(PIP_CMD) install $(pip_level_opts) -r requirements.txt
	$(PIP_CMD) install -e .
	which zhmc_log_forwarder
	zhmc_log_forwarder --version
	touch $@
	@echo 'Done: Installed $(package_name)'

$(doc_build_dir)/html/docs/index.html: Makefile $(doc_dependent_files)
	rm -fv $@
	$(doc_cmd) -b html $(doc_opts) $(doc_build_dir)/html
	@echo "Done: Created the HTML pages with top level file: $@"

$(bdist_file): Makefile $(dist_dependent_files)
ifneq ($(PLATFORM),Windows)
	rm -Rfv $(package_name).egg-info .eggs build
	$(PYTHON_CMD) setup.py bdist_wheel -d $(dist_dir) --universal
	@echo 'Done: Created binary distribution archive: $@'
else
	@echo 'Error: Creating binary distribution archive requires to run on Linux or OSX'
	@false
endif

$(sdist_file): Makefile $(dist_dependent_files)
ifneq ($(PLATFORM),Windows)
	rm -Rfv $(package_name).egg-info .eggs build
	$(PYTHON_CMD) setup.py sdist -d $(dist_dir)
	@echo 'Done: Created source distribution archive: $@'
else
	@echo 'Error: Creating source distribution archive requires to run on Linux or OSX'
	@false
endif

# TODO: Once PyLint has no more errors, remove the dash "-"
pylint.log: Makefile $(pylint_rc_file) $(check_py_files)
ifeq ($(python_major_version), 2)
	rm -fv $@
	-bash -c 'set -o pipefail; pylint --rcfile=$(pylint_rc_file) --output-format=text $(check_py_files) 2>&1 |tee $@.tmp'
	mv -f $@.tmp $@
	@echo 'Done: Created PyLint log file: $@'
else
	@echo 'Info: PyLint requires Python 2; skipping this step on Python $(python_major_version)'
endif

flake8.log: Makefile $(flake8_rc_file) $(check_py_files)
	rm -fv $@
	bash -c 'set -o pipefail; flake8 $(check_py_files) 2>&1 |tee $@.tmp'
	mv -f $@.tmp $@
	@echo 'Done: Created Flake8 log file: $@'

$(test_log_file): Makefile $(package_py_files) $(test_py_files) .coveragerc
	rm -fv $@
	bash -c 'set -o pipefail; PYTHONWARNINGS=ignore py.test $(pytest_no_log_opt) -s $(test_dir) --cov $(module_name) --cov-config .coveragerc --cov-report=html $(pytest_opts) 2>&1 |tee $@.tmp'
	mv -f $@.tmp $@
	@echo 'Done: Created test log file: $@'
