# Contributor process

[This repository](https://github.com/mattclay/aws-terminator) is used by [Ansible](https://github.com/ansible/ansible) to deploy policies for AWS integration tests.

To enable new integration tests for the CI account, you can start the process by opening a pull request here.

There are two things you may need to do:
1. Update the permissions in the [policy directory](https://github.com/mattclay/aws-terminator/tree/master/aws/policy) with those needed to run your integration tests (policy groups are defined below). Check the existing policies to avoid adding duplicates.
   The [AWS module developer guidelines](https://docs.ansible.com/ansible/devel/dev_guide/platforms/aws_guidelines.html#aws-permissions-for-integration-tests) contains some tips on finding the minimum IAM policy needed for running the integration tests.
2. Add a terminator class in the corresponding file in the [terminator directory](https://github.com/mattclay/aws-terminator/tree/master/aws/terminator) if you are adding permissions to create a new type of AWS resource. Skip this step and submit your pull request if you are only adding permissions to modify resources that are already supported.

The rest of this section is about creating and testing your terminator class.

If your integration tests fail there could be stray resources left in the CI account. To mitigate the risk, integration tests should always be contained in a block with an always statement that cleans up if the tests fail. In case that also fails (such as due to a flaky AWS service or broken module) we deploy a lambda function that runs the terminator classes to find and delete stray resources.

To begin, you need to use the Terminator base class or the DbTerminator base class. We terminate resources found based on their age. Not all AWS resources return the creation date timestamp so those resources are stored in a database with the time when the terminator class located them and we approximate when to delete them from that.
* If the resource has a creation date timestamp use the Terminator base class.
* If the resource does not have a creation date timestamp use the DbTerminator base class.

Your terminator class requires the following:
* the staticmethod `create`
* the property `name`
* the property `created_time` (only if you are using the Terminator base class)
* the method `terminate`

You can include the property `id` if there is a unique identifier in addition to a human readable name.

The `create` method should return the base class `_create` method called with the credentials to create the client, the class name, the boto3 resource name to create the client, and a function for the client to use. The function should list all the given resources for that resource type.

Here's an example for an EC2 instance terminator class:

```python
class Ec2Instance(Terminator):

    @staticmethod
    def create(credentials):

        def get_instances(client):
            return [i for r in client.describe_instances()['Reservations'] for i in r['Instances']]

        return Terminator._create(credentials, Ec2Instance, 'ec2', get_instances)
```

`self.instance` is an item from the list returned by the base class `_create` method and should be used by the `id`, `name`, and `created_time` properties.

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

To test the terminator class with your own account you can use the [cleanup.py](https://github.com/mattclay/aws-terminator/blob/master/aws/cleanup.py) script.

Warning: Always use the --check (or -c) flag and the --target flag to avoid accidentally deleting wanted resources.
It is safest to use `cleanup.py` in an empty/dev account.

To start using `cleanup.py` you will need to:
* Use Python 3.7+
* Modify config.yml to use your own accounts. These can be the same account if you're just using `cleanup.py`.
  If you use two separate accounts, `lambda_account_id` is the account of the profile that will assume the IAM role in the `test_account_id`. The `test_account_id` is where the terminator class(es) will locate/remove resources.
* Create a role called `ansible-core-ci-test-dev` that your AWS profile can assume. Give this role the permissions required by the terminator class you are testing.
* Set the environment variable `AWS_PROFILE` with the profile you want to use.
* Run `cleanup.py` using the class name as the target to locate the resources in us-east-1:

      python cleanup.py --stage dev --target Ec2Instance -v -c
      cleanup     : DEBUG    located Ec2Instance: count=2
      cleanup     : DEBUG    ignored Ec2Instance: name=, id=i-0c18f88091e78898e age=0 days, 0:05:32, stale=False
      cleanup     : DEBUG    checked Ec2Instance: name=, id=i-0630e2ba640d7dbf1 age=1 days, 20:49:03, stale=True

* The class property `age_limit` determines when a resource becomes stale. This is 10 minutes by default. Once a resource is stale, the terminator can delete it. Use check mode (-c or --check) to see what your class would delete without actually removing it.
* Once a resource is stale you can test that it can be cleaned up by removing the check mode flag.
  For example, `python cleanup.py --stage dev --target Ec2Instance -v`.
* You can forcibly delete resources that are not stale by using --force (or -f). Be aware that this can also remove resources that do not use the Terminator or DbTerminator base classes. Such unsupported resources will not be cleaned up by the CI account.

After you have tested that your terminator class can be used by `cleanup.py`, submit your pull request. A core developer will review and deploy your changes as outlined below.

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
