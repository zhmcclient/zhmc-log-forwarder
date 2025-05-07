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

.. towncrier start
Version 1.0.2
^^^^^^^^^^^^^

Released: 2025-05-07

**Bug fixes:**

* Fixed missing package dependencies for development.

* Addressed safety issues up to 2025-02-26.

* Fixed a regression in the Syslog support that resulted in an AssertionError.
  The error had been introduced in PR 25 in version 0.12.0. (`#123 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/123>`_)

**Enhancements:**

* Dev: Started using the trusted publisher concept of Pypi in order to avoid
  dealing with Pypi access tokens. (`#115 <https://github.com/zhmcclient/zhmc-log-forwarder/issues/115>`_)


Version 1.0.1
^^^^^^^^^^^^^

Released: 2025-01-12

**Bug fixes:**

* Addressed safety issues up to 2025-01-12.

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
