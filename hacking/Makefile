PYTHON3 ?= python3.7

EXTRA_VARS=ansible_connection=local ansible_python_interpreter=$(shell which python)
RUN_TEST_POLICY_PLAYBOOK=ansible-playbook -i localhost, -e '$(EXTRA_VARS)' deploy-test-policy.yml $(FLAGS)
RUN_TERMINATOR_PLAYBOOK=ansible-playbook -i localhost, -e '$(EXTRA_VARS)' terminator.yml $(FLAGS)

VAULT_ARGS := $(if $(ANSIBLE_VAULT_PASSWORD_FILE),,--ask-vault-pass)

.PHONY: default
default:
	@echo ">>> Running Tests"
	@echo
	@echo "USAGE: make test|test-requirements|yamllint|pycodestyle|pylint [PYTHON3=$(PYTHON3)]"

.PHONY: test_policy
test_policy:
	$(RUN_TEST_POLICY_PLAYBOOK)

.PHONY: test
test: yamllint

.PHONY: test-requirements
test-requirements:
	"$(PYTHON3)" -m pip install -c ../constraints.txt -r requirements.txt -r test-requirements.txt --disable-pip-version-check

.PHONY: yamllint
yamllint:
	"$(PYTHON3)" -m yamllint --config-file ../.yamllint .

.PHONY: pycodestyle
pycodestyle:
	find . -name '*.py' | xargs "$(PYTHON3)" -m pycodestyle --config ../pycodestyle.ini

.PHONY: pylint
pylint:
	find . -name '*.py' | xargs "$(PYTHON3)" -m pylint --rcfile pylint.rc
