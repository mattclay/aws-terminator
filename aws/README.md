# Contributor process

If you have a pull request that contains tests that need to be enabled in CI you can get the ball rolling by
submitting a pull request. Start by updating the appropriate test policy in the policy directory (policy
groups are defined below).

Good integration tests should be contained in a block with an always statement that cleans up any stray resources
if the integration tests fail. Despite this, bugs in the module and flaky AWS services could cause there to be leaked
resources. Because of this, if your tests create a resource and the tests are run in CI, that resource must also have
a terminator class. We deploy a lambda function that runs these terminator classes.

To create your terminator class, you'll need to decide whether to use the Terminator base class or the DbTerminator
base class.

We terminate resources found based on their age. Not all AWS resources return the creation date timestamp so those
resources get stored in a database with the time the terminator classes first found them and we approximate when to
delete them from that. If the resource has a creation date timestamp use the Terminator base class. Otherwise use
DbTerminator.

Your terminator class should have the staticmethod `create`, the properties `id` and `name` (and `created_time` if
you are using the Terminator base class), and the method `terminate`.

The create method returns the credentials to create the client, the class name, the boto3 resource name to create the
client, and a function for the client to use which will list all the given resources for that resource type.

Here's an example:

```python
class Ec2Instance(Terminator):

    @staticmethod
    def create(credentials):

        def get_instances(client):
            return [i for r in client.describe_instances()['Reservations'] for i in r['Instances']]

        return Terminator._create(credentials, Ec2Instance, 'ec2', get_instances)
```

The `id`, `name`, and `created_time` properties should return an appropriate value from self.instance which is
a dictionary from the list of resources returned by the function defined in `create`:

```python
    @property
    def id(self):
        return self.instance['InstanceId']

    @property
    def name(self):
        return self.instance['PrivateDnsName']

    @property
    def created_time(self):
        return self.instance['LaunchTime']
```

The `terminate` method should use self.client to delete the resource.

```python
    def terminate(self):
        self.client.terminate_instances(InstanceIds=[self.id])
```

If you want to test the terminator class with your own account you can use the cleanup.py script.

Warning: Always use the --check (or -c) flag and the --target flag to avoid accidentally deleting wanted resources.

Using cleanup.py with your own account:
  - Ensure you're using Python 3.7+
  - Modify config.yml so that lambda_account_id and test_account_id are both set to your account.
    If you're just running the cleanup.py script these can be the same account; ignore the warning in config.yml.
  - Make sure you have a role called ansible-core-ci-test-dev that your AWS profile can assume. This role should have
    the permissions to use your cleanup.py class.
  - Set the environment variable AWS_PROFILE with the profile you want to use.
  - Run the cleanup.py script for the new target you added to find any stray resources in us-east-1: |
        $ python cleanup.py --stage dev --target Ec2Instance -v -c
        cleanup     : DEBUG    located Ec2Instance: count=2
        cleanup     : DEBUG    ignored Ec2Instance: name=, id=i-0c18f88091e78898e age=0 days, 0:05:32, stale=False
        cleanup     : DEBUG    ignored Ec2Instance: name=, id=i-0630e2ba640d7dbf1 age=1 days, 20:49:03, stale=True
  - Make sure your stray resources become stale. This indicates that when --check or -c isn't specified the terminator
    class will delete it.
  - Once the resources show stale=True you can test that they're terminated by your new class by removing the check
    mode flag: `python cleanup.py --stage dev --target Ec2Instance -v`

Submit your pull request. A core developer will review and deploy your changes as outlined below.

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
    if resources have a created time, DbTerminator otherwise)
  - test terminator with `python cleanup.py --stage dev -c -v`, make sure modified terminator resource class shows up
    in the output

Make a pull request to CI

If tests pass and CI PR is ready to merge:
  - deploy to prod with `make test_policy STAGE=prod`

If there are modifications to the terminator:
  - after deploying to dev and prod run `make terminator_lambda` using aworks user credentials

## IAM Policy Organization

### Structure

Policy docs are in `aws/policy/{group}.yaml`, arranged by the test group.

### Policy Groups
- Application Services: CloudFormation, S3, SQS, SNS, SES
- Big Data: Glacier, Glue, Redshift, etc
- Compute: EC2, EKS, RDS, Lambda, etc
- Machine Learning: Lex, Polly, Macie, etc
- Networking: VPC, ACLs, route tables, NAT Gateways, IGW/VGW, security groups, etc
- Security Services: IAM, Shield, WAF, Config, Inspector, etc
