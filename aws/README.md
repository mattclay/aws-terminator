# Deploying to AWS
Deploying to AWS is done using an Ansible playbook, which can be easily run with make using the provided Makefile.

## Environment Variables

The playbook requires the following environment variables to be set:

- `AWS_REGION` - The recommended region is `us-east-1` as that is where Shippable instances run.
- `STAGE` - This must be either `dev` or `prod`.

## Deployment Process

Initial setup can be handled by an administrator, with further updates to the deployment by a power user.

### Administrator

An administrator can deploy the IAM roles and policies with `make terminator`.

### Power User

A power user can deploy everything else with `make terminator_lambda`.

This user should have the following AWS Managed Policies applied:

- IAMReadOnlyAccess
- PowerUserAccess

### Steps to update permissions and terminator for AWS pull requests

Use Python 2 (Python 3 not fully supported yet)

Modify IAM permissions:
  - update the appropriate test policy in the policy directory (policy groups are defined below)
  - export AWS_PROFILE=youraworksuser
  - assume arn:aws:iam::966509639900:role/administrator
  - export the sts credentials and unset AWS_PROFILE
  - deploy permissions to dev running `make test_policy STAGE=dev`

Check the permissions by running the integration tests:
  - make sure there is no test/integration/cloud-config-aws.yml (will override CI credentials)
  - make sure CI key is in ~/.ansible-core-ci.key
  - run tests with `ansible-test integration [module] --remote-stage dev --docker default -v`

If tests create a resource:
  - add a new class for the resource in the corresponding file in the terminator directory (use Terminator base class
    if resources have a created time, SimpleDbTerminator otherwise)
  - test terminator with `python cleanup.py --stage dev -c -v`, make sure modified terminator resource class shows up
    in the output

Make a pull request to CI

If tests pass and CI PR is ready to merge:
  - deploy to prod with `make test_policy STAGE=prod`

If there are modifications to the terminator:
  - after deploying to dev and prod run `make terminator_lambda` using aworks user credentials

## IAM Policy Organization

### Structure

Policy docs are in `aws/policy/{group}.json`, arranged by the test group.

### Policy Groups
- Application Services: CloudFormation, S3, SQS, SNS, SES
- Big Data: Glacier, Glue, Redshift, etc
- Compute: EC2, RDS, Lambda, etc
- Machine Learning: Lex, Polly, Macie, etc
- Networking: VPC, ACLs, route tables, NAT Gateways, IGW/VGW, security groups, etc
- Security Services: IAM, Shield, WAF, Config, Inspector, etc
