PYTHON3 ?= python3.9

EXTRA_VARS=ansible_connection=local ansible_python_interpreter=$(shell which python)
RUN_TEST_POLICY_PLAYBOOK=ansible-playbook -i localhost, -e '$(EXTRA_VARS)' deploy-test-policy.yml $(FLAGS)
RUN_TERMINATOR_PLAYBOOK=ansible-playbook -i localhost, -e '$(EXTRA_VARS)' terminator.yml $(FLAGS)

.PHONY: default
default:
	@echo ">>> Deploy Terminator to the Lambda Account"
	@echo
	@echo "USAGE: make terminator|terminator_lambda AWS_PROFILE=lambda [FLAGS=flags]"
	@echo
	@echo ">>> Deploy to the Test Account"
	@echo
	@echo "USAGE: make test_policy AWS_PROFILE=test STAGE=dev|prod [FLAGS=flags]"

.PHONY: terminator
terminator:
	$(RUN_TERMINATOR_PLAYBOOK)

.PHONY: terminator_lambda
terminator_lambda:
	$(RUN_TERMINATOR_PLAYBOOK) --tags=lambda

.PHONY: test_policy
test_policy:
	$(RUN_TEST_POLICY_PLAYBOOK)
