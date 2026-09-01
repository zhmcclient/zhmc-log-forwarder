.. Copyright 2024 IBM Corp. All Rights Reserved.
..
.. Licensed under the Apache License, Version 2.0 (the "License");
.. you may not use this file except in compliance with the License.
.. You may obtain a copy of the License at
..
..    http://www.apache.org/licenses/LICENSE-2.0
..
.. Unless required by applicable law or agreed to in writing, software
.. distributed under the License is distributed on an "AS IS" BASIS,
.. WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
.. See the License for the specific language governing permissions and
.. limitations under the License.


Change log
----------

.. ============================================================================
..
.. Do not add change records here directly, but create fragment files instead!
..
.. ============================================================================

.. only:: dev

   .. include:: tmp_changes.rst

.. towncrier start
Version 1.2.0
^^^^^^^^^^^^^

Released: 2026-09-01

**Incompatible changes:**

* Removed support for Python 3.8, because (1) Python 3.8 is out of service since
  2024-10-07, and (2) the license definition according to PEP 639 requires
  setuptools >= 77.0.3 which requires Python >= 3.9, and pyproject.toml does
  not support environment markers. (`#202 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/202>`_)

**Bug fixes:**

* Changed from the unmaintained GitHub action gsactions/commit-message-checker
  to its new fork ddev/commit-message-checker.

* Development: Fixed that pip-missing-reqs raised TypeError by pinning pip
  to <26.2.

* Fixed safety issues up to 2026-07-10.

* Dev: Fixed issue where the package version used for distribution archive file
  names were generated inconsistently between setuptools_scm (used in Makefile)
  and the 'build' module, by using no build isolation ('--no-isolation' option
  of the 'build' module) and increasing the minimum version of 'setuptools-scm'
  to 9.2.0, which fixes a number of version related issues.

* Upgrade nltk to 3.9.1 to fix the wordnet error, see https://github.com/nltk/nltk/issues/3416

* Dev: Circumvented safety issue with import of typer module by pinning typer
  to <0.17.0.

* Development: Fixed that squash merges of the release/start PRs did not work in
  the release/start process.

* Docs: Fixed broken links in the documentation. Fixed the description of
  commit message checking in the development section of the documentation to
  remove the mentioning of the GitCop service which is no longer used.

* Removed the pinning of typer version to <0.17.0 with the new release of safety 3.6.1 and
  also upgraded minimum version of safety to be 3.6.1 to fix the issue with typer>=0.17.0, see  https://github.com/pyupio/safety/issues/778

* Dev: Added dependencies for Sphinx.

* Relaxed the commit message length check in the test workflow so
  that it no longer requires an empty line after the title and that it
  ignores the PR ID created by squash commits when checking the length.

* Docs: Updates in Bibliography section: Collapsed the HMC WS-API books to a
  single version (2.17), Added link to HMC Help, Updated HMC Security book to
  2.17, Removed the HMC Operations Guide which no longer exists.

* Dev: Added handling of HTTP error 422 when creating a new stable branch in
  the GitHub Actions publish workflow.

* Test: Fixed new issues raised by pylint 4.0.0.

* Dev: Added Makefile as a dependent on rules that produce files. (`#147 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/147>`_)

* Dev: Made order of names in AUTHORS.md reliable. (`#149 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/149>`_)

**Enhancements:**

* Test: Added check for missing and extra dependencies in minimum constraints
  files based on installed packages. The result is displayed as a warning in
  the summary of the GitHub Actions run of the "test" workflow.

* Development: Added a GitHub Actions workflow named 'backport' that creates a
  backport PR to the latest stable branch stable_M.N when a PR labeled with the
  'backport' label is merged.

* Docs: The change log of the documentation on ReadTheDocs now shows the changes
  of the next functional release in the version for the 'master' branch.

* Dev: Added checking by Mend Renovate.

* Docs: Changed the version setup on ReadTheDocs to only show released versions
  and no longer branches such as 'latest' or 'stable'. Adjusted the verification
  steps in the release instructions accordingly.

* Docs: Added sections that describe how to handle GitHub Dependabot alerts
  and how to use the assisted backporting of PRs.

* Test: Enabled tests on Python 3.14.

* Dev: Added doclinkcheck to GitHub Actions test workflow, ignoring errors. (`#143 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/143>`_)

* Dev: Added commit message checker to test workflow. (`#144 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/144>`_)

* Test: Improved some settings for coverage measurement, and enabled branch
  coverage reporting. This lowered the overall coverage percentage somewhat.
  Increased the minimum version of the "coverage" package to support the
  newer properties in the coverage config. Along with that, increased the
  minimum version of the "coveralls" package. (`#208 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/208>`_)

**Cleanup:**

* Test: Added retries for sending coverage data to the coveralls.io site to
  address issues with the site.

* Dev: Changed default shell on Windows to use bash from WSL. Removed make macros
  that encapsulated differences between Windows and Linux/macOS. Removed 'bash -c'
  from commands in the Makefile.

* Test: Reduced the GitHub Actions test environments to save resources.

* Removed unused packages from minimum constraints files.

* Removed Travis control file (was used in IBM internal fork).

* Simplified pip dependency file requirements-develop.txt by removing any indirect
  package dependencies and leaving that to the requirements of the packages
  we use directly. Reorganized the minimum-constraints-develop.txt file
  accordingly.

* Resolved several issues reported by new ruff version 4.

* Used new license format defined in PEP 639 to accommodate upcoming removal
  of support for old format. (`#199 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/199>`_)


Version 1.1.0
^^^^^^^^^^^^^

Released: 2025-06-03

**Bug fixes:**

* Fixed missing package dependencies for development.

* Addressed safety issues up to 2025-06-03.

* Fixed a regression in the Syslog support that resulted in an AssertionError.
  The error had been introduced in PR 25 in version 0.12.0. (`#123 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/123>`_)

**Enhancements:**

* Added check for incorrectly named towncrier change fragment files.

* Added a new optional boolean config parameter 'selflog_debug' that when true
  includes debug messages in self-log messages. By default, they are
  not included.

* Added a new optional boolean config parameter 'selflog_jms' that when true
  includes HMC JMS notifications in self-log messages. By default, they are
  not included.

* Dev: Started using the trusted publisher concept of Pypi in order to avoid
  dealing with Pypi access tokens. (`#115 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/115>`_)

* Dev: Added display of environment variables and platform details in test
  workflow. (`#116 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/116>`_)

* Added timestamps to the start and stop messages of the log forwarder. (`#129 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/129>`_)

* Added support for logging the messages of the log forwarder itself as well
  as the HMC notifications to a log file. (`#129 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/129>`_)

**Cleanup:**

* Accommodated rollout of Ubuntu 24.04 on GitHub Actions by using ubuntu-22.04
  as the OS image for Python 3.8 based test runs.


Version 1.0.0
^^^^^^^^^^^^^

Released: 2024-10-10

**Bug fixes:**

* Addressed safety issues up to 2024-08-18.

* Test: Fixed coveralls not found on MacOS with Python 3.9-3.11.

* Test: Resolved new issues reported by Pylint 3.3.

* Dev: Fixed checks and missing removal of temp file in make targets for releasing
  and starting a version.

* Dev: In the make commands to create/update AUTHORS.md, added a reftag to the
  'git shortlog' command to fix the issue that without a terminal (e.g. in GitHub
  Actions), the command did not display any authors.

* Fixed incorrect check for start branch in 'make start_tag'. (`#88 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/88>`_)

**Enhancements:**

* Changed 'make install' to install in non-editable mode.

* Dev: Relaxed the conditions when safety issues are tolerated.

* Dev: The AUTHORS.md file is now updated when building the distribution
  archives.

* Migrated to pyproject.toml. (`#48 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/48>`_)

* Added support for running the 'ruff' checker via "make ruff" and added that
  to the test workflow. (`#58 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/58>`_)

* Added support for running the 'bandit' checker with a new make target
  'bandit', and added that to the GitHub Actions test workflow.
  Adjusted the code in order to pass the bandit check. (`#59 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/59>`_)

* Support for and test of Python 3.13.0-rc.1. Needed to increase the minimum
  versions of PyYAML to 6.0.2. (`#62 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/62>`_)

* Test: Added tests for Python 3.13 (final version). (`#63 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/63>`_)

* Dev: Encapsulated the starting of a new version into new 'start_branch' and
  'start_tag' make targets. See the development documentation for details. (`#70 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/70>`_)

* Dev: Encapsulated the releasing of a version to PyPI into new 'release_branch'
  and 'release_publish' make targets. See the development documentation for
  details. (`#70 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/70>`_)

* Added support for building a Docker container that runs the log forwarder. (`#81 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/81>`_)

* Increased zhmcclient to 1.18.0 to pick up fixes. (`#85 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/85>`_)

**Cleanup:**

* Dev: Dropped the 'make upload' target, because the release to PyPI has
  been migrated to using a publish workflow. (`#70 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/70>`_)


Version 0.12.0
^^^^^^^^^^^^^^

Released: 2024-06-14

Version 0.11.0
^^^^^^^^^^^^^^

Released: 2024-06-12

Version 0.10.0
^^^^^^^^^^^^^^

Released: 2024-03-18
