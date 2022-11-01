PYTHON3 ?= python3.9

EXTRA_VARS=ansible_connection=local ansible_python_interpreter=$(shell which python)
RUN_TEST_POLICY_PLAYBOOK=ansible-playbook -i localhost, -e '$(EXTRA_VARS)' deploy-test-policy.yml $(FLAGS)
RUN_TERMINATOR_PLAYBOOK=ansible-playbook -i localhost, -e '$(EXTRA_VARS)' terminator.yml $(FLAGS)

VAULT_ARGS := $(if $(ANSIBLE_VAULT_PASSWORD_FILE),,--ask-vault-pass)

.PHONY: default
default:
	@echo ">>> Deploy Terminator to the Lambda Account"
	@echo
	@echo "USAGE: make terminator|terminator_lambda AWS_PROFILE=lambda [FLAGS=flags]"
	@echo
	@echo ">>> Deploy to the Test Account"
	@echo
	@echo "USAGE: make test_policy AWS_PROFILE=test STAGE=dev|prod [FLAGS=flags]"
	@echo
	@echo ">>> Running Tests"
	@echo
	@echo "USAGE: make test|test-requirements|yamllint|pycodestyle|pylint [PYTHON3=$(PYTHON3)]"

.PHONY: terminator
terminator:
	$(RUN_TERMINATOR_PLAYBOOK)

.PHONY: terminator_lambda
terminator_lambda:
	$(RUN_TERMINATOR_PLAYBOOK) --tags=lambda

.PHONY: test_policy
test_policy:
	$(RUN_TEST_POLICY_PLAYBOOK)

.PHONY: test
test: yamllint pycodestyle pylint

.PHONY: test-requirements
test-requirements:
	"$(PYTHON3)" -m pip install -c ../constraints.txt -r requirements.txt -r test-requirements.txt --disable-pip-version-check $(FLAGS)

.PHONY: yamllint
yamllint:
	"$(PYTHON3)" -m yamllint --config-file ../.yamllint .

.PHONY: pycodestyle
pycodestyle:
	find . -name '*.py' | xargs "$(PYTHON3)" -m pycodestyle --config ../pycodestyle.ini

.PHONY: pylint
pylint:
	find . -name '*.py' | xargs "$(PYTHON3)" -m pylint --rcfile pylint.rc
