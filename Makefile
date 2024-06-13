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
  pip_level_opts := -c minimum-constraints.txt -c minimum-constraints-develop.txt
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

# Python versions
python_version := $(shell $(PYTHON_CMD) -c "import sys; sys.stdout.write('{}.{}.{}'.format(*sys.version_info[0:3]))")
python_mn_version := $(shell $(PYTHON_CMD) -c "import sys; sys.stdout.write('{}.{}'.format(*sys.version_info[0:2]))")
python_m_version := $(shell $(PYTHON_CMD) -c "import sys; sys.stdout.write('{}'.format(sys.version_info[0]))")
pymn := py$(python_mn_version)

# Directory for the generated distribution files
dist_dir := dist

# Distribution archives (as built by 'build' tool)
bdist_file := $(dist_dir)/$(package_name_under)-$(package_version)-py2.py3-none-any.whl
sdist_file := $(dist_dir)/$(package_name_under)-$(package_version).tar.gz

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
test_log_file := test_$(pymn).log

# Source files with test code
test_py_files := \
    $(wildcard $(test_dir)/*.py) \
    $(wildcard $(test_dir)/*/*.py) \
    $(wildcard $(test_dir)/*/*/*.py) \

# Directory for .done files
done_dir := done

# Determine whether py.test has the --no-print-logs option.
pytest_no_log_opt := $(shell py.test --help 2>/dev/null |grep '\--no-print-logs' >/dev/null; if [ $$? -eq 0 ]; then echo '--no-print-logs'; else echo ''; fi)

# Safety policy files
safety_install_policy_file := .safety-policy.yml
safety_develop_policy_file := .safety-policy-develop.yml

# Flake8 config file
flake8_rc_file := .flake8

# PyLint config file
pylint_rc_file := .pylintrc

# Source files for check (with PyLint and Flake8)
check_py_files := \
    setup.py \
    $(package_py_files) \
    $(test_py_files) \

# Packages whose dependencies are checked using pip-missing-reqs
check_reqs_base_packages := pip_check_reqs pipdeptree build pytest coverage coveralls flake8 pylint safety twine
ifeq ($(python_m_version),2)
  check_reqs_packages := $(check_reqs_base_packages)
else ifeq ($(python_mn_version),3.5)
  check_reqs_packages := $(check_reqs_base_packages)
else ifeq ($(python_mn_version),3.6)
  check_reqs_packages := $(check_reqs_base_packages)
else ifeq ($(python_mn_version),3.7)
  check_reqs_packages := $(check_reqs_base_packages)
else
  check_reqs_packages := $(check_reqs_base_packages)
endif

ifdef TESTCASES
pytest_opts := $(TESTOPTS) -k $(TESTCASES)
else
pytest_opts := $(TESTOPTS)
endif

# Files to be built
build_files := $(bdist_file) $(sdist_file)

# Files the distribution archive depends upon.
# This is also used for 'include' statements in MANIFEST.in.
# Wildcards can be used directly (i.e. without wildcard function).
dist_included_files := \
    setup.py \
    LICENSE \
    README.md \
    requirements.txt \
    $(package_py_files) \

# No built-in rules needed:
.SUFFIXES:

.PHONY: help
help:
	@echo 'Makefile for $(package_name) project'
	@echo 'Package version will be: $(package_version)'
	@echo 'Uses the currently active Python environment with Python $(python_version)'
	@echo 'Valid targets are (they do just what is stated, i.e. no automatic prereq targets):'
	@echo '  install    - Install package in active Python environment'
	@echo '  develop    - Prepare the development environment by installing prerequisites'
	@echo "  check_reqs - Perform missing dependency checks"
	@echo '  check      - Run Flake8 on sources'
	@echo '  pylint     - Run PyLint on sources'
	@echo "  safety     - Run Safety tool"
	@echo '  test       - Run tests (and test coverage)'
	@echo '               Does not include install but depends on it, so make sure install is current.'
	@echo '               Env.var TESTCASES can be used to specify a py.test expression for its -k option'
	@echo '  build      - Build the distribution files in: $(dist_dir)'
	@echo '               Builds: $(bdist_file) $(sdist_file)'
	@echo '  builddoc   - Build documentation in: $(doc_build_dir)'
	@echo '  authors    - Generate AUTHORS.md file from git log'
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
	@echo '  TESTCASES=... - Testcase filter for pytest -k'
	@echo '  TESTOPTS=... - Options for pytest'

.PHONY: develop
develop: $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done
	@echo '$@ done.'

.PHONY: install
install: $(done_dir)/install_$(pymn)_$(PACKAGE_LEVEL).done
	@echo '$@ done.'

.PHONY: check
check: $(done_dir)/flake8_$(pymn)_$(PACKAGE_LEVEL).done
	@echo '$@ done.'

.PHONY: pylint
pylint: $(done_dir)/pylint_$(pymn)_$(PACKAGE_LEVEL).done
	@echo '$@ done.'

.PHONY: safety
safety: $(done_dir)/safety_develop_$(pymn)_$(PACKAGE_LEVEL).done $(done_dir)/safety_install_$(pymn)_$(PACKAGE_LEVEL).done
	@echo '$@ done.'

.PHONY: build
build: $(build_files)
	@echo '$@ done.'

.PHONY: builddoc
builddoc: $(doc_build_dir)/html/docs/index.html
	@echo '$@ done.'

.PHONY: all
all: install develop check_reqs check test build builddoc authors
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
	rm -Rf $(doc_build_dir) htmlcov .tox .pytest_cache
	rm -f test_*.log $(bdist_file) $(sdist_file) $(done_dir)/*.done $(dist_dir)/$(package_name)-$(package_version)*.egg
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

.PHONY: authors
authors: _check_version
	echo "# Authors of this project" >AUTHORS.md
	echo "" >>AUTHORS.md
	echo "Sorted list of authors derived from git commit history:" >>AUTHORS.md
	echo '```' >>AUTHORS.md
	git shortlog --summary --email | cut -f 2 | sort >>AUTHORS.md
	echo '```' >>AUTHORS.md
	@echo '$@ done.'

.PHONY: _check_version
_check_version:
ifeq (,$(package_version))
	$(error Package version could not be determined)
endif

$(done_dir)/base_$(pymn)_$(PACKAGE_LEVEL).done: requirements-base.txt minimum-constraints.txt minimum-constraints-develop.txt
	rm -fv $@
	@echo 'Installing/upgrading base packages with PACKAGE_LEVEL=$(PACKAGE_LEVEL)'
	$(PYTHON_CMD) -m pip install $(pip_level_opts) -r requirements-base.txt
	touch $@
	@echo 'Done: Installed/upgraded base packages'

$(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done: $(done_dir)/base_$(pymn)_$(PACKAGE_LEVEL).done requirements-develop.txt minimum-constraints.txt minimum-constraints-develop.txt
	rm -fv $@
	@echo 'Installing/upgrading development packages with PACKAGE_LEVEL=$(PACKAGE_LEVEL)'
	$(PIP_CMD) install $(pip_level_opts) -r requirements-develop.txt
	touch $@
	@echo 'Done: Installed/upgraded development packages'

$(done_dir)/install_$(pymn)_$(PACKAGE_LEVEL).done: $(done_dir)/base_$(pymn)_$(PACKAGE_LEVEL).done requirements.txt minimum-constraints.txt minimum-constraints-develop.txt setup.py $(package_py_files)
	rm -fv $@
	@echo 'Installing $(package_name) in edit mode with PACKAGE_LEVEL=$(PACKAGE_LEVEL)'
	$(PIP_CMD) install $(pip_level_opts) -r requirements.txt
	$(PIP_CMD) install -e .
	which zhmc_log_forwarder
	zhmc_log_forwarder --version
	touch $@
	@echo 'Done: Installed $(package_name) in edit mode'

$(doc_build_dir)/html/docs/index.html: Makefile $(doc_dependent_files)
ifeq ($(python_m_version),2)
	@echo "Makefile: Warning: Skipping creation of the HTML pages on Python $(python_version)" >&2
else ifeq ($(python_mn_version),3.5)
	@echo "Makefile: Warning: Skipping creation of the HTML pages on Python $(python_version)" >&2
else ifeq ($(python_mn_version),3.6)
	@echo "Makefile: Warning: Skipping creation of the HTML pages on Python $(python_version)" >&2
else ifeq ($(python_mn_version),3.7)
	@echo "Makefile: Warning: Skipping creation of the HTML pages on Python $(python_version)" >&2
else
	@echo "Makefile: Creating the HTML pages with top level file: $@"
	rm -fv $@
	$(doc_cmd) -b html $(doc_opts) $(doc_build_dir)/html
	@echo "Done: Created the HTML pages with top level file: $@"
endif

# Note: distutils depends on the right files specified in MANIFEST.in, even when
# they are already specified e.g. in 'package_data' in setup.py.
# We generate the MANIFEST.in file automatically, to have a single point of
# control (this Makefile) for what gets into the distribution archive.
MANIFEST.in: Makefile $(dist_included_files)
	@echo "Makefile: Creating the manifest input file"
	echo "# MANIFEST.in file generated by Makefile - DO NOT EDIT!!" >$@
ifeq ($(PLATFORM),Windows_native)
	for %%f in ($(dist_included_files)) do (echo include %%f >>$@)
else
	echo "$(dist_included_files)" | xargs -n 1 echo include >>$@
endif
	@echo "Makefile: Done creating the manifest input file: $@"

# Distribution archives.
# Note: Deleting MANIFEST causes distutils (setup.py) to read MANIFEST.in and to
# regenerate MANIFEST. Otherwise, changes in MANIFEST.in will not be used.
# Note: Deleting build is a safeguard against picking up partial build products
# which can lead to incorrect hashbangs in scripts in wheel archives.
$(bdist_file) $(sdist_file): Makefile MANIFEST.in $(dist_included_files)
	@echo 'Makefile: Creating distribution archives: $@'
	rm -fv MANIFEST
	rm -Rfv $(package_name).egg-info .eggs build
	$(PYTHON_CMD) -m build --outdir $(dist_dir)
	@echo 'Makefile: Done creating distribution archives: $@'

$(done_dir)/pylint_$(pymn)_$(PACKAGE_LEVEL).done: $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done Makefile $(pylint_rc_file) $(check_py_files)
ifeq ($(python_m_version),2)
	@echo "Makefile: Warning: Skipping Pylint on Python $(python_version)" >&2
else
	@echo "Makefile: Running Pylint"
	-$(call RM_FUNC,$@)
	pylint --disable=fixme --rcfile=$(pylint_rc_file) --output-format=text $(check_py_files)
	echo "done" >$@
	@echo "Makefile: Done running Pylint"
endif

$(done_dir)/flake8_$(pymn)_$(PACKAGE_LEVEL).done: $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done Makefile $(flake8_rc_file) $(check_py_files)
	-$(call RM_FUNC,$@)
	flake8 $(check_py_files)
	echo "done" >$@

$(done_dir)/safety_develop_$(pymn)_$(PACKAGE_LEVEL).done: $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done Makefile $(safety_develop_policy_file) minimum-constraints-develop.txt
ifeq ($(python_m_version),2)
	@echo "Makefile: Warning: Skipping Safety tool for development packages on Python $(python_version)" >&2
else ifeq ($(python_mn_version),3.5)
	@echo "Makefile: Warning: Skipping Safety tool for development packages on Python $(python_version)" >&2
else ifeq ($(python_mn_version),3.6)
	@echo "Makefile: Warning: Skipping Safety tool for development packages on Python $(python_version)" >&2
else
	@echo "Makefile: Running Safety tool for development packages"
	-$(call RM_FUNC,$@)
	bash -c "safety check --policy-file $(safety_develop_policy_file) -r minimum-constraints-develop.txt --full-report || test '$(RUN_TYPE)' != 'release' || exit 1"
	echo "done" >$@
	@echo "Makefile: Done running Safety tool for development packages"
endif

$(done_dir)/safety_install_$(pymn)_$(PACKAGE_LEVEL).done: $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done Makefile $(safety_install_policy_file) minimum-constraints.txt
ifeq ($(python_m_version),2)
	@echo "Makefile: Warning: Skipping Safety tool for installation packages on Python $(python_version)" >&2
else ifeq ($(python_mn_version),3.5)
	@echo "Makefile: Warning: Skipping Safety tool for installation packages on Python $(python_version)" >&2
else ifeq ($(python_mn_version),3.6)
	@echo "Makefile: Warning: Skipping Safety tool for installation packages on Python $(python_version)" >&2
else
	@echo "Makefile: Running Safety tool for installation packages"
	-$(call RM_FUNC,$@)
	safety check --policy-file $(safety_install_policy_file) -r minimum-constraints.txt --full-report
	echo "done" >$@
	@echo "Makefile: Done running Safety tool for installation packages"
endif

.PHONY: check_reqs
check_reqs: $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done requirements.txt minimum-constraints.txt minimum-constraints-develop.txt
ifeq ($(python_m_version),2)
	@echo "Makefile: Warning: Skipping the checking of missing dependencies on Python $(python_version)" >&2
else ifeq ($(python_mn_version),3.5)
	@echo "Makefile: Warning: Skipping the checking of missing dependencies on Python $(python_version)" >&2
else ifeq ($(python_mn_version),3.6)
	@echo "Makefile: Warning: Skipping the checking of missing dependencies on Python $(python_version)" >&2
else
	@echo "Makefile: Checking missing dependencies of this package"
	pip-missing-reqs $(package_name) --requirements-file=requirements.txt
	pip-missing-reqs $(package_name) --requirements-file=minimum-constraints.txt
	@echo "Makefile: Done checking missing dependencies of this package"
ifeq ($(PLATFORM),Windows_native)
# Reason for skipping on Windows is https://github.com/r1chardj0n3s/pip-check-reqs/issues/67
	@echo "Makefile: Warning: Skipping the checking of missing dependencies of site-packages directory on native Windows" >&2
else
	@echo "Makefile: Checking missing dependencies of some development packages in our minimum versions"
	bash -c "cat minimum-constraints-develop.txt minimum-constraints.txt >tmp_minimum-constraints-all.txt"
	@rc=0; for pkg in $(check_reqs_packages); do dir=$$($(PYTHON_CMD) -c "import $${pkg} as m,os; dm=os.path.dirname(m.__file__); d=dm if not dm.endswith('site-packages') else m.__file__; print(d)"); cmd="pip-missing-reqs $${dir} --requirements-file=tmp_minimum-constraints-all.txt"; echo $${cmd}; $${cmd}; rc=$$(expr $${rc} + $${?}); done; exit $${rc}
	rm -fv tmp_minimum-constraints-all.txt
	@echo "Makefile: Done checking missing dependencies of some development packages in our minimum versions"
endif
endif
	@echo "Makefile: $@ done."

.PHONY: test
test: $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done Makefile $(package_py_files) $(test_py_files) .coveragerc
	rm -Rf htmlcov
	pytest $(pytest_no_log_opt) -s $(test_dir) --cov $(module_name) --cov-config .coveragerc --cov-report=html $(pytest_opts)
	@echo '$@ done.'
