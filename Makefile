# ------------------------------------------------------------------------------
# Makefile for zhmc-log-forwarder project
#
# make: GNU make
#
# Supported OS platforms:
#   Windows
#   Linux
#   MacOS

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
  pip_level_opts := -c minimum-constraints-install.txt -c minimum-constraints-develop.txt
else
  ifeq ($(PACKAGE_LEVEL),latest)
    pip_level_opts := --upgrade
  else
    $(error Error: Invalid value for PACKAGE_LEVEL variable: $(PACKAGE_LEVEL))
  endif
endif

# Run type (normal, scheduled, release, local)
ifndef RUN_TYPE
  RUN_TYPE := local
endif

# Make variables are case sensitive and some native Windows environments have
# ComSpec set instead of COMSPEC.
ifndef COMSPEC
  ifdef ComSpec
    COMSPEC = $(ComSpec)
  endif
endif

# Determine OS platform make runs on.
ifeq ($(OS),Windows_NT)
  ifdef PWD
    PLATFORM := Windows_UNIX
  else
    PLATFORM := Windows_native
    ifdef COMSPEC
      SHELL := $(subst \,/,$(COMSPEC))
    else
      SHELL := cmd.exe
    endif
    .SHELLFLAGS := /c
  endif
else
  # Values: Linux, Darwin
  PLATFORM := $(shell uname -s)
endif

ifeq ($(PLATFORM),Windows_native)
  # Note: The substituted backslashes must be doubled.
  # Remove files (blank-separated list of wildcard path specs)
  RM_FUNC = del /f /q $(subst /,\\,$(1))
  # Remove files recursively (single wildcard path spec)
  RM_R_FUNC = del /f /q /s $(subst /,\\,$(1))
  # Remove directories (blank-separated list of wildcard path specs)
  RMDIR_FUNC = rmdir /q /s $(subst /,\\,$(1))
  # Remove directories recursively (single wildcard path spec)
  RMDIR_R_FUNC = rmdir /q /s $(subst /,\\,$(1))
  # Copy a file, preserving the modified date
  CP_FUNC = copy /y $(subst /,\\,$(1)) $(subst /,\\,$(2))
  ENV = set
  WHICH = where
else
  RM_FUNC = rm -f $(1)
  RM_R_FUNC = find . -type f -name '$(1)' -delete
  RMDIR_FUNC = rm -rf $(1)
  RMDIR_R_FUNC = find . -type d -name '$(1)' | xargs -n 1 rm -rf
  CP_FUNC = cp -r $(1) $(2)
  ENV = env | sort
  WHICH = which -a
endif

# Name of this package on Pypi
package_name := zhmc-log-forwarder

# Pypi package name translated to underscore (e.g. used for .whl files)
package_name_under := zhmc_log_forwarder

# Name of top level Python namespace
module_name := zhmc_log_forwarder

# Package version (e.g. "1.0.0a1.dev10+gd013028e" during development, or "1.0.0"
# when releasing).
# Note: The package version is automatically calculated by setuptools_scm based
# on the most recent tag in the commit history, increasing the least significant
# version indicator by 1.
package_version := $(shell $(PYTHON_CMD) -m setuptools_scm)

# Python versions
python_version := $(shell $(PYTHON_CMD) -c "import sys; sys.stdout.write('{}.{}.{}'.format(*sys.version_info[0:3]))")
python_mn_version := $(shell $(PYTHON_CMD) -c "import sys; sys.stdout.write('{}.{}'.format(*sys.version_info[0:2]))")
python_m_version := $(shell $(PYTHON_CMD) -c "import sys; sys.stdout.write('{}'.format(sys.version_info[0]))")
pymn := py$(python_mn_version)

package_dir := $(package_name_under)

# The version file is recreated by setuptools-scm on every build, so it is
# excluded from git, and also from some dependency lists.
version_file := $(package_dir)/_version_scm.py

# Source files in the package
package_py_files := \
    $(filter-out $(version_file), $(wildcard $(package_dir)/*.py)) \
    $(wildcard $(package_dir)/*/*.py) \

# Directory with test source files
test_dir := tests

# Source files with test code
test_py_files := \
    $(wildcard $(test_dir)/*.py) \
    $(wildcard $(test_dir)/*/*.py) \
    $(wildcard $(test_dir)/*/*/*.py) \

# Directory for the generated distribution files
dist_dir := dist

# Distribution archives (as built by 'build' tool)
bdist_file := $(dist_dir)/$(package_name_under)-$(package_version)-py3-none-any.whl
sdist_file := $(dist_dir)/$(package_name_under)-$(package_version).tar.gz

# Dependencies of the distribution archives. Since the $(version_file) is
# created when building the distribution archives, this must not contain
# the $(version_file).
dist_dependent_files := \
    pyproject.toml \
    LICENSE \
    README.md \
    AUTHORS.md \
    requirements.txt \
    $(wildcard $(package_dir)/zhmc_log_messages.yml) \
    $(package_py_files) \

# Directory where docs files and conf.py are located
doc_dir := docs

# Directory for generated API documentation
doc_build_dir := build_docs
doc_build_file := $(doc_build_dir)/index.html

# Dependents for Sphinx documentation build
doc_dependent_files := \
    $(doc_dir)/conf.py \
    $(wildcard $(doc_dir)/*.rst) \
    $(package_py_files) \
    $(version_file) \

# Source files for checks (with PyLint and Flake8, etc.)
check_py_files := \
    $(package_py_files) \
    $(test_py_files) \
    $(doc_dir)/conf.py \

# Documentation generator command
doc_cmd := sphinx-build
doc_opts := -v -c $(doc_dir)

# Directory for .done files
done_dir := done

# Determine whether py.test has the --no-print-logs option.
pytest_no_log_opt := $(shell py.test --help 2>/dev/null |grep '\--no-print-logs' >/dev/null; if [ $$? -eq 0 ]; then echo '--no-print-logs'; else echo ''; fi)

# Safety policy files
safety_install_policy_file := .safety-policy-install.yml
safety_develop_policy_file := .safety-policy-develop.yml

# Flake8 config file
flake8_rc_file := .flake8

# PyLint config file
pylint_rc_file := .pylintrc

# Packages whose dependencies are checked using pip-missing-reqs
check_reqs_packages := pip_check_reqs pipdeptree build pytest coverage coveralls flake8 pylint safety twine towncrier

ifdef TESTCASES
pytest_opts := $(TESTOPTS) -k $(TESTCASES)
else
pytest_opts := $(TESTOPTS)
endif

# No built-in rules needed:
.SUFFIXES:

.PHONY: help
help:
	@echo 'Makefile for $(package_name) project'
	@echo 'Package version will be: $(package_version)'
	@echo 'Uses the currently active Python environment with Python $(python_version)'
	@echo 'Valid targets are (they do just what is stated, i.e. no automatic prereq targets):'
	@echo '  install    - Install package in active Python environment (non-editable)'
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
build: $(bdist_file) $(sdist_file)
	@echo '$@ done.'

.PHONY: builddoc
builddoc: $(doc_build_file)
	@echo '$@ done.'

.PHONY: all
all: install develop check_reqs check test build builddoc authors
	@echo '$@ done.'

.PHONY: upload
upload: _check_version uninstall $(bdist_file) $(sdist_file)
ifeq (,$(findstring .dev,$(package_version)))
	@echo '==> This will upload $(package_name) version $(package_version) to PyPI!'
	@echo -n '==> Continue? [yN] '
	@bash -c 'read answer; if [ "$$answer" != "y" ]; then echo "Aborted."; false; fi'
	twine upload $(bdist_file) $(sdist_file)
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
	-$(call RMDIR_R_FUNC,$(doc_build_dir))
	-$(call RMDIR_R_FUNC,htmlcov)
	-$(call RMDIR_R_FUNC,.pytest_cache)
	-$(call RMDIR_R_FUNC,.tox)
	-$(call RM_FUNC,test_*.log $(bdist_file) $(sdist_file) $(done_dir)/*.done $(dist_dir)/$(package_name)-$(package_version)*.egg)
	@echo 'Done: Removed all build products to get to a fresh state.'
	@echo '$@ done.'

.PHONY: clean
clean:
	-$(call RMDIR_R_FUNC,build)
	-$(call RMDIR_R_FUNC,__pycache__)
	-$(call RMDIR_R_FUNC,.cache)
	-$(call RMDIR_R_FUNC,$(package_name_under).egg-info)
	-$(call RMDIR_R_FUNC,.eggs)
	-$(call RM_FUNC,MANIFEST MANIFEST.in AUTHORS ChangeLog .coverage)
	-$(call RM_R_FUNC,*.pyc *.tmp tmp_*)
	@echo 'Done: Cleaned out all temporary files.'
	@echo '$@ done.'

.PHONY: pyshow
pyshow:
	which $(PYTHON_CMD)
	$(PYTHON_CMD) --version
	$(WHICH) $(PIP_CMD)
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

$(done_dir)/base_$(pymn)_$(PACKAGE_LEVEL).done: Makefile requirements-base.txt minimum-constraints-install.txt minimum-constraints-develop.txt
	-$(call RM_FUNC,$@)
	@echo 'Installing/upgrading base packages with PACKAGE_LEVEL=$(PACKAGE_LEVEL)'
	$(PYTHON_CMD) -m pip install $(pip_level_opts) -r requirements-base.txt
	touch $@
	@echo 'Done: Installed/upgraded base packages'

$(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done: $(done_dir)/base_$(pymn)_$(PACKAGE_LEVEL).done Makefile requirements-develop.txt minimum-constraints-install.txt minimum-constraints-develop.txt
	-$(call RM_FUNC,$@)
	@echo 'Installing/upgrading development packages with PACKAGE_LEVEL=$(PACKAGE_LEVEL)'
	$(PIP_CMD) install $(pip_level_opts) -r requirements-develop.txt
	touch $@
	@echo 'Done: Installed/upgraded development packages'

$(done_dir)/install_$(pymn)_$(PACKAGE_LEVEL).done: $(done_dir)/base_$(pymn)_$(PACKAGE_LEVEL).done Makefile requirements.txt minimum-constraints-install.txt minimum-constraints-develop.txt pyproject.toml $(dist_dependent_files)
	-$(call RM_FUNC,$@)
	@echo 'Installing $(package_name) (non-editable) with PACKAGE_LEVEL=$(PACKAGE_LEVEL)'
	$(PIP_CMD) install $(pip_level_opts) .
	which zhmc_log_forwarder
	zhmc_log_forwarder --version
	touch $@
	@echo 'Done: Installed $(package_name)'

$(doc_build_file): $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done Makefile $(doc_dependent_files)
	@echo "Makefile: Creating the HTML pages with top level file: $@"
	-$(call RM_FUNC,$@)
	$(doc_cmd) -b html $(doc_opts) $(doc_dir) $(doc_build_dir)
	@echo "Done: Created the HTML pages with top level file: $@"

$(sdist_file): $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done Makefile $(dist_dependent_files)
	@echo "Makefile: Building the source distribution archive: $(sdist_file)"
	$(PYTHON_CMD) -m build --sdist --outdir $(dist_dir) .
	@echo "Makefile: Done building the source distribution archive: $(sdist_file)"

$(bdist_file) $(version_file): $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done Makefile $(dist_dependent_files)
	@echo "Makefile: Building the wheel distribution archive: $(bdist_file)"
	$(PYTHON_CMD) -m build --wheel --outdir $(dist_dir) -C--universal .
	@echo "Makefile: Done building the wheel distribution archive: $(bdist_file)"

$(done_dir)/pylint_$(pymn)_$(PACKAGE_LEVEL).done: $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done Makefile $(pylint_rc_file) $(check_py_files)
	@echo "Makefile: Running Pylint"
	-$(call RM_FUNC,$@)
	pylint --disable=fixme --rcfile=$(pylint_rc_file) --output-format=text $(check_py_files)
	echo "done" >$@
	@echo "Makefile: Done running Pylint"

$(done_dir)/flake8_$(pymn)_$(PACKAGE_LEVEL).done: $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done Makefile $(flake8_rc_file) $(check_py_files)
	-$(call RM_FUNC,$@)
	flake8 $(check_py_files)
	echo "done" >$@

$(done_dir)/safety_develop_$(pymn)_$(PACKAGE_LEVEL).done: $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done Makefile $(safety_develop_policy_file) minimum-constraints-develop.txt
	@echo "Makefile: Running Safety for development packages (and tolerate safety issues when RUN_TYPE is normal or scheduled)"
	-$(call RM_FUNC,$@)
	bash -c "safety check --policy-file $(safety_develop_policy_file) -r minimum-constraints-develop.txt --full-report || test '$(RUN_TYPE)' == 'normal' || test '$(RUN_TYPE)' == 'scheduled' || exit 1"
	echo "done" >$@
	@echo "Makefile: Done running Safety for development packages"

$(done_dir)/safety_install_$(pymn)_$(PACKAGE_LEVEL).done: $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done Makefile $(safety_install_policy_file) minimum-constraints-install.txt
	@echo "Makefile: Running Safety for install packages (and tolerate safety issues when RUN_TYPE is normal)"
	-$(call RM_FUNC,$@)
	bash -c "safety check --policy-file $(safety_install_policy_file) -r minimum-constraints-install.txt --full-report || test '$(RUN_TYPE)' == 'normal' || exit 1"
	echo "done" >$@
	@echo "Makefile: Done running Safety for install packages"

.PHONY: check_reqs
check_reqs: $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done requirements.txt minimum-constraints-install.txt minimum-constraints-develop.txt
	@echo "Makefile: Checking missing dependencies of this package"
	pip-missing-reqs $(package_name) --requirements-file=requirements.txt
	pip-missing-reqs $(package_name) --requirements-file=minimum-constraints-install.txt
	@echo "Makefile: Done checking missing dependencies of this package"
ifeq ($(PLATFORM),Windows_native)
# Reason for skipping on Windows is https://github.com/r1chardj0n3s/pip-check-reqs/issues/67
	@echo "Makefile: Warning: Skipping the checking of missing dependencies of site-packages directory on native Windows" >&2
else
	@echo "Makefile: Checking missing dependencies of some development packages in our minimum versions"
	bash -c "cat minimum-constraints-develop.txt minimum-constraints-install.txt >tmp_minimum-constraints-all.txt"
	@rc=0; for pkg in $(check_reqs_packages); do dir=$$($(PYTHON_CMD) -c "import $${pkg} as m,os; dm=os.path.dirname(m.__file__); d=dm if not dm.endswith('site-packages') else m.__file__; print(d)"); cmd="pip-missing-reqs $${dir} --requirements-file=tmp_minimum-constraints-all.txt"; echo $${cmd}; $${cmd}; rc=$$(expr $${rc} + $${?}); done; exit $${rc}
	-$(call RM_FUNC,tmp_minimum-constraints-all.txt)
	@echo "Makefile: Done checking missing dependencies of some development packages in our minimum versions"
endif
	@echo "Makefile: $@ done."

.PHONY: test
test: $(done_dir)/develop_$(pymn)_$(PACKAGE_LEVEL).done Makefile $(package_py_files) $(test_py_files) .coveragerc
	-$(call RM_FUNC,htmlcov)
	pytest $(pytest_no_log_opt) -s $(test_dir) --cov $(module_name) --cov-config .coveragerc --cov-report=html $(pytest_opts)
	@echo '$@ done.'
