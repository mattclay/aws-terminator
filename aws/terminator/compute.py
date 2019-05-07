import datetime

import botocore
import botocore.exceptions
import dateutil

from . import DbTerminator, Terminator, get_tag_dict_from_tag_list, get_account_id


class Ec2KeyPair(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2KeyPair, 'ec2', lambda client: client.describe_key_pairs()['KeyPairs'])

    @property
    def name(self):
        return self.instance['KeyName']

    def terminate(self):
        self.client.delete_key_pair(KeyName=self.name)


class Ec2LoadBalancer(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2LoadBalancer, 'elb', lambda client: client.describe_load_balancers()['LoadBalancerDescriptions'])

    @property
    def name(self):
        return self.instance['LoadBalancerName']

    @property
    def created_time(self):
        return self.instance['CreatedTime']

    def terminate(self):
        self.client.delete_load_balancer(LoadBalancerName=self.name)


class Ec2Instance(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2Instance, 'ec2',
                                  lambda client: [i for r in client.describe_instances()['Reservations'] for i in r['Instances']])

    @property
    def id(self):
        return self.instance['InstanceId']

    @property
    def name(self):
        return self.instance['PrivateDnsName']

    @property
    def created_time(self):
        return self.instance['LaunchTime']

    @property
    def ignore(self):
        return self.instance['State']['Name'] == 'terminated'

    def terminate(self):
        try:
            self.client.terminate_instances(InstanceIds=[self.id])
            return
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] != 'OperationNotPermitted':
                raise

        self.client.modify_instance_attribute(InstanceId=self.id, Attribute='disableApiTermination', Value='False')
        self.client.terminate_instances(InstanceIds=[self.id])


class Ec2Snapshot(Terminator):
    @staticmethod
    def create(credentials):
        account = get_account_id(credentials)
        return Terminator._create(credentials, Ec2Snapshot, 'ec2', lambda client: client.describe_snapshots(OwnerIds=[account])['Snapshots'])

    @property
    def id(self):
        return self.instance['SnapshotId']

    @property
    def name(self):
        return self.instance['Description']

    @property
    def created_time(self):
        return self.instance['StartTime']

    def terminate(self):
        self.client.delete_snapshot(SnapshotId=self.id)


class Ec2Image(Terminator):
    @staticmethod
    def create(credentials):
        account = get_account_id(credentials)
        return Terminator._create(credentials, Ec2Image, 'ec2', lambda client: client.describe_images(Owners=[account])['Images'])

    @property
    def id(self):
        return self.instance['ImageId']

    @property
    def name(self):
        return self.instance['Name']

    @property
    def created_time(self):
        return datetime.datetime.strptime(self.instance['CreationDate'].replace('Z', ''), '%Y-%m-%dT%H:%M:%S.%f').replace(
            tzinfo=dateutil.tz.tz.tzutc(), microsecond=0)

    def terminate(self):
        self.client.deregister_image(ImageId=self.id)


class Ec2Volume(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2Volume, 'ec2', lambda client: client.describe_volumes()['Volumes'])

    @property
    def id(self):
        return self.instance['VolumeId']

    @property
    def name(self):
        return get_tag_dict_from_tag_list(self.instance.get('Tags')).get('Name')

    @property
    def created_time(self):
        return self.instance['CreateTime']

    def terminate(self):
        self.client.delete_volume(VolumeId=self.id)


class Ec2TransitGateway(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2TransitGateway, 'ec2', lambda client: client.describe_transit_gateways()['TransitGateways'])

    @property
    def id(self):
        return self.instance['TransitGatewayId']

    @property
    def name(self):
        return self.instance['TransitGatewayArn']

    @property
    def created_time(self):
        return self.instance['CreationTime']

    @property
    def ignore(self):
        # deleting and deleted are ignored because there is nothing more we can do with them
        # pending is ignored because deletion is not allowed in that state
        # modifying is assumed to behave like pending, although this has not been verified
        return self.instance['State'] in ('deleting', 'deleted', 'pending', 'modifying')

    def terminate(self):
        self.client.delete_transit_gateway(TransitGatewayId=self.id)


class ElasticBeanstalk(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, ElasticBeanstalk, 'elasticbeanstalk', lambda client: client.describe_applications()['Applications'])

    @property
    def id(self):
        return self.instance['ApplicationName']

    @property
    def name(self):
        return self.instance['ApplicationName']

    @property
    def created_time(self):
        return self.instance['DateCreated']

    def terminate(self):
        try:
            self.client.delete_application(ApplicationName=self.id)
        except botocore.exceptions.ClientError as e:
            if 'It is currently pending deletion.' not in e.response['Error']['Message']:
                raise


class NeptuneSubnetGroup(DbTerminator):
    @staticmethod
    def create(credentials):
        def _paginate_neptune_subnet_groups(client):
            return client.get_paginator('describe_db_subnet_groups').paginate().build_full_result()['DBSubnetGroups']
        return Terminator._create(credentials, NeptuneSubnetGroup, 'neptune', _paginate_neptune_subnet_groups)

    @property
    def id(self):
        return self.instance['DBSubnetGroupArn']

    @property
    def name(self):
        return self.instance['DBSubnetGroupName']

    @property
    def ignore(self):
        return self.name == 'default'

    def terminate(self):
        self.client.delete_db_subnet_group(DBSubnetGroupName=self.name)


class RdsDbParameterGroup(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, RdsDbParameterGroup, 'rds', lambda client: client.describe_db_parameter_groups()['DBParameterGroups'])

    @property
    def id(self):
        return self.instance['DBParameterGroupArn']

    @property
    def name(self):
        return self.instance['DBParameterGroupName']

    def terminate(self):
        self.client.delete_db_parameter_group(DBParameterGroupName=self.name)


class EcrRepository(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, EcrRepository, 'ecr', lambda client: client.describe_repositories()['repositories'])

    @property
    def name(self):
        return self.instance['repositoryName']

    @property
    def created_time(self):
        return self.instance['createdAt']

    def terminate(self):
        self.client.delete_repository(repositoryName=self.name, force=True)


class LambdaFunction(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, LambdaFunction, 'lambda', lambda client: client.list_functions()['Functions'])

    @property
    def name(self):
        return self.instance['FunctionName']

    @property
    def created_time(self):
        return datetime.datetime.strptime(self.instance['LastModified'].replace('+0000', ''), '%Y-%m-%dT%H:%M:%S.%f').replace(
            tzinfo=dateutil.tz.tz.tzutc(), microsecond=0)

    def terminate(self):
        self.client.delete_function(FunctionName=self.name)


class NeptuneCluster(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_neptune_clusters(client):
            results = client.describe_db_clusters()
            marker = results.pop('Marker', None)
            while marker is not None:
                next_clusters = client.describe_db_clusters(Marker=marker)
                results['DBClusters'].append(next_clusters['DBClusters'])
                marker = next_clusters.pop('Marker', None)
            return results['DBClusters']
        return Terminator._create(credentials, NeptuneCluster, 'neptune', _paginate_neptune_clusters)

    @property
    def name(self):
        return self.instance['DBClusterIdentifier']

    @property
    def created_time(self):
        return self.instance['ClusterCreateTime']

    def terminate(self):
        self.client.delete_db_cluster(DBClusterIdentifier=self.name, SkipFinalSnapshot=True)
