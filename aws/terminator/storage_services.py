import botocore
import botocore.exceptions

from . import Terminator, get_account_id


class S3Bucket(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, S3Bucket, 's3', lambda client: client.list_buckets()['Buckets'])

    @property
    def name(self):
        return self.instance['Name']

    @property
    def ignore(self):
        # Bucket encryption takes up to 24 hours to be enabled, so we use a persistent bucket
        # We'll empty the bucket contents in SSMBucketObjects
        return self.instance['Name'] == 'ssm-encrypted-test-bucket'

    @property
    def created_time(self):
        return self.instance['CreationDate']

    def terminate(self):
        def _paginated_list(bucket):
            paginator = self.client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket):
                yield [d['Key'] for d in page.get('Contents', [])]

        try:
            self.client.delete_bucket(Bucket=self.name)
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] == 'NoSuchBucket':
                return
            for keys in _paginated_list(self.name):
                self.client.delete_objects(
                    Bucket=self.name,
                    Delete=dict(
                        Objects=[{'Key': k} for k in keys],
                        Quiet=True,
                    )
                )
            self.client.delete_bucket(Bucket=self.name)


class SSMBucketObjects(Terminator):
    # We maintain a persistent encrypted bucket for the commmunity.aws SSM connection plugin.
    # Ensure it is kept clean of objects from past test runs.
    @staticmethod
    def create(credentials):
        def paginate_objects(client):
            list_bucket_objects_result = client.get_paginator('list_objects_v2').paginate(Bucket='ssm-encrypted-test-bucket').build_full_result()
            bucket_contents = {}
            if list_bucket_objects_result.get('Contents'):
                bucket_contents = list_bucket_objects_result['Contents']
            return bucket_contents

        return Terminator._create(credentials, SSMBucketObjects, 's3', paginate_objects)

    @property
    def created_time(self):
        return self.instance['LastModified']

    @property
    def name(self):
        return self.instance['Key']

    def terminate(self):
        self.client.delete_object(Bucket='ssm-encrypted-test-bucket', Key=self.name)


class S3AccessPoint(Terminator):
    @staticmethod
    def create(credentials):
        account = get_account_id(credentials)
        def list_access_points(client):
            results = []
            access_points = client.list_access_points(AccountId=account).get("AccessPointList", [])
            for ap in access_points:
                results.append(client.get_access_point(AccountId=account, Name=ap['Name']))
            return results
        terminators = Terminator._create(credentials, S3AccessPoint, 's3control', list_access_points)
        for terminator in terminators:
            terminator._account_id = account
        return terminators

    @property
    def name(self):
        return self.instance['Name']

    @property
    def created_time(self):
        return self.instance['CreationDate']

    def terminate(self):
        self.client.delete_access_point(AccountId=self._account_id, Name=self.name)


class S3AccessPointForObjectLambda(Terminator):
    @staticmethod
    def create(credentials):
        account = get_account_id(credentials)
        def list_access_points(client):
            results = []
            access_points = client.list_access_points_for_object_lambda(AccountId=account).get("ObjectLambdaAccessPointList", [])
            for ap in access_points:
                results.append(client.get_access_point_for_object_lambda(AccountId=account, Name=ap['Name']))
            return results
        terminators = Terminator._create(credentials, S3AccessPointForObjectLambda, 's3control', list_access_points)
        for terminator in terminators:
            terminator._account_id = account
        return terminators

    @property
    def name(self):
        return self.instance['Name']

    @property
    def created_time(self):
        return self.instance['CreationDate']

    def terminate(self):
        self.client.delete_access_point_for_object_lambda(AccountId=self._account_id, Name=self.name)
