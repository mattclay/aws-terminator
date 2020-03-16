'Hacking' directory tools
=========================

aws_config
----------

AWS policy definitions for testing AWS modules.  These differ from the
policies in the aws/policy directory in that they are more broad,
not containing any region or account restrictions, and include policies
for modules not currently supported in CI.

These policies are provided as a guideline for permissions needed to
develop against the modules in the `community.amazon` and `ansible.amazon`
collections.

Usage
-----

Policies can be deployed to an AWS account using the `setup_iam.yml`
playbook.

```
export ADMIN_PROFILE=$your_profile_name
ansible-playbook hacking/aws_config/setup-iam.yml -e region=us-east-2 \
  -e profile=$ADMIN_PROFILE -e iam_group=ansible_test -vv
```
