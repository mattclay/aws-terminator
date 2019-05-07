from datetime import timezone, datetime
import time

import botocore
import botocore.exceptions

from . import DbTerminator, Terminator


class CloudWatchLogGroup(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, CloudWatchLogGroup, 'logs', lambda client: client.describe_log_groups()['logGroups'])

    @property
    def name(self):
        return self.instance['logGroupName']

    @property
    def created_time(self):
        # self.instance['creationTime'] is the number of milliseconds after Jan 1, 1970 00:00:00 UTC
        milliseconds = self.instance['creationTime']
        return datetime.fromtimestamp(milliseconds/1000.0, tz=timezone.utc)

    def terminate(self):
        self.client.delete_log_group(logGroupName=self.name)


class CodeCommitRepository(DbTerminator):
    @staticmethod
    def create(credentials):
        def paginate_repositories(client):
            return client.get_paginator('list_repositories').paginate().build_full_result()['repositories']

        return Terminator._create(credentials, CodeCommitRepository, 'codecommit', paginate_repositories)

    @property
    def id(self):
        return self.instance['repositoryId']

    @property
    def name(self):
        return self.instance['repositoryName']

    def terminate(self):
        self.client.delete_repository(repositoryName=self.name)


class DmsSubnetGroup(DbTerminator):
    @staticmethod
    def create(credentials):
        def paginate_dms_subnet_groups(client):
            return client.get_paginator('describe_replication_subnet_groups').paginate().build_full_result()['ReplicationSubnetGroups']

        return Terminator._create(credentials, DmsSubnetGroup, 'dms', paginate_dms_subnet_groups)

    @property
    def id(self):
        return self.instance['ReplicationSubnetGroupIdentifier']

    @property
    def name(self):
        return self.instance['ReplicationSubnetGroupIdentifier']

    def terminate(self):
        self.client.delete_replication_subnet_group(ReplicationSubnetGroupIdentifier=self.id)


class Efs(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Efs, 'efs', lambda client: client.describe_file_systems()['FileSystems'])

    @property
    def id(self):
        return self.instance['FileSystemId']

    @property
    def name(self):
        return self.instance['Name']

    @property
    def created_time(self):
        return self.instance['CreationTime']

    def terminate(self):
        # Cannot delete file system if in use: delete mounts targets first
        for mt in self.client.describe_mount_targets(FileSystemId=self.id)['MountTargets']:
            self.client.delete_mount_target(MountTargetId=mt['MountTargetId'])
        self.client.delete_file_system(FileSystemId=self.id)


class S3Bucket(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, S3Bucket, 's3', lambda client: client.list_buckets()['Buckets'])

    @property
    def name(self):
        return self.instance['Name']

    @property
    def created_time(self):
        return self.instance['CreationDate']

    def terminate(self):
        def _paginated_list(bucket):
            pg = self.client.get_paginator('list_objects_v2')
            for page in pg.paginate(Bucket=bucket):
                yield [d['Key'] for d in page.get('Contents', [])]

        try:
            self.client.delete_bucket(Bucket=self.name)
        except botocore.exceptions.ClientError:
            for keys in _paginated_list(self.name):
                self.client.delete_objects(
                    Bucket=self.name,
                    Delete=dict(
                        Objects=[{'Key': k} for k in keys],
                        Quiet=True,
                    )
                )
            self.client.delete_bucket(Bucket=self.name)


class SesIdentity(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, SesIdentity, 'ses',
                                  lambda client: client.list_identities()['Identities'])

    @property
    def id(self):
        return self.instance

    @property
    def name(self):
        return self.instance

    def terminate(self):
        self.client.delete_identity(Identity=self.id)


class SesReceiptRuleSet(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_receipt_rule_sets(client):
            results = client.list_receipt_rule_sets()
            next_token = results.pop('NextToken', None)
            while next_token:
                # This operation can be made at most once/second, see
                # https://boto3.readthedocs.io/en/latest/reference/services/ses.html#SES.Client.list_receipt_rule_sets
                time.sleep(1)
                next_rule_sets = client.list_receipt_rule_sets(NextToken=next_token)
                results['RuleSets'].append(next_rule_sets['RuleSets'])
                next_token = next_rule_sets.pop('NextToken', None)
            return results['RuleSets']
        return Terminator._create(credentials, SesReceiptRuleSet, 'ses', _paginate_receipt_rule_sets)

    @property
    def name(self):
        return self.instance['Name']

    @property
    def created_time(self):
        return self.instance['CreatedTimestamp']

    def terminate(self):
        self.client.delete_receipt_rule_set(RuleSetName=self.name)


class Sns(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Sns, 'sns', lambda client: client.list_topics()['Topics'])

    @property
    def id(self):
        return self.instance['TopicArn']

    @property
    def name(self):
        return self.instance['TopicArn']

    def terminate(self):
        self.client.delete_topic(TopicArn=self.id)


class SqsQueue(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, SqsQueue, 'sqs', lambda client: client.list_queues().get('QueueUrls', []))

    @property
    def id(self):
        return self.instance

    @property
    def name(self):
        return self.instance

    def terminate(self):
        self.client.delete_queue(QueueUrl=self.id)


class SsmParameter(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, SsmParameter, 'ssm', lambda client: client.describe_parameters()['Parameters'])

    @property
    def id(self):
        return self.instance['Name']

    @property
    def name(self):
        return self.instance['Name']

    def terminate(self):
        self.client.delete_parameter(Name=self.id)
