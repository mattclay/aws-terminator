# Copyright (C) 2019 Matt Clay <matt@mystile.com>
# GNU General Public License v3.0+ (see ansible/LICENSE.md or https://www.gnu.org/licenses/gpl-3.0.txt)

PYTHON3 ?= python3.7

.PHONY: default
default:
	@echo ">>> Running Tests"
	@echo
	@echo "USAGE: make test|test-requirements|pycodestyle|pylint [PYTHON3=$(PYTHON3)]"

.PHONY: test
test: pycodestyle pylint

.PHONY: test-requirements
test-requirements:
	"$(PYTHON3)" -m pip install -c ../constraints.txt -r requirements.txt -r test-requirements.txt --disable-pip-version-check

.PHONY: pycodestyle
pycodestyle:
	find . -name '*.py' | xargs "$(PYTHON3)" -m pycodestyle --config ../pycodestyle.ini

.PHONY: pylint
pylint:
	find . -name '*.py' | xargs "$(PYTHON3)" -m pylint --rcfile pylint.rc
