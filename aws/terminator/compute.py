import datetime

import botocore
import botocore.exceptions
import dateutil.tz

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
            tzinfo=dateutil.tz.tzutc(), microsecond=0)

    def terminate(self):
        self.client.deregister_image(ImageId=self.id)


class Ec2Volume(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2Volume, 'ec2', lambda client: client.describe_volumes()['Volumes'])

    @property
    def age_limit(self):
        return datetime.timedelta(minutes=15)

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
        account = get_account_id(credentials)
        filters = [{
            'Name': 'owner-id',
            'Values': [account]
        }]
        return Terminator._create(credentials, Ec2TransitGateway, 'ec2',
                                  lambda client: client.describe_transit_gateways(Filters=filters)['TransitGateways'])

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
        except botocore.exceptions.ClientError as ex:
            if 'It is currently pending deletion.' not in ex.response['Error']['Message']:
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
            tzinfo=dateutil.tz.tzutc(), microsecond=0)

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


class EksCluster(Terminator):
    @staticmethod
    def create(credentials):
        def _build_cluster_results(client):
            cluster_list = client.list_clusters()['clusters']
            results = []
            for cluster in cluster_list:
                results.append(client.describe_cluster(name=cluster)['cluster'])
            return results
        return Terminator._create(credentials, EksCluster, 'eks', _build_cluster_results)

    @property
    def name(self):
        return self.instance['name']

    @property
    def created_time(self):
        return self.instance['createdAt']

    @property
    def age_limit(self):
        return datetime.timedelta(minutes=30)

    def terminate(self):
        try:
            self.client.delete_cluster(name=self.name)
        except botocore.exceptions.ClientError as ex:
            if not ex.response['Error']['Code'] == 'ResourceInUseException':
                raise


class EksFargateProfile(Terminator):
    @staticmethod
    def create(credentials):
        def _build_eks_fargate_profiles(client):
            results = []
            for cluster in client.list_clusters()['clusters']:
                for fargate_profile in client.list_fargate_profiles(clusterName=cluster)['fargateProfileNames']:
                    results.append(client.describe_fargate_profile(clusterName=cluster, fargateProfileName=fargate_profile)['fargateProfile'])
            return results
        return Terminator._create(credentials, EksFargateProfile, 'eks', _build_eks_fargate_profiles)

    @property
    def name(self):
        return self.instance['fargateProfileName']

    @property
    def age_limit(self):
        return datetime.timedelta(minutes=15)

    @property
    def created_time(self):
        return self.instance['createdAt']

    @property
    def ignore(self):
        return self.instance['status'] == ('DELETING')

    @property
    def cluster_name(self):
        return self.instance['clusterName']

    def terminate(self):
        try:
            self.client.delete_fargate_profile(clusterName=self.cluster_name, fargateProfileName=self.name)
        except botocore.exceptions.ClientError as ex:
            if not ex.response['Error']['Code'] == 'ResourceInUseException':
                raise


class ElasticLoadBalancing(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_elastic_lbs(client):
            return client.get_paginator(
                'describe_load_balancers').paginate().build_full_result()['LoadBalancerDescriptions']
        return Terminator._create(credentials, ElasticLoadBalancing, 'elb', _paginate_elastic_lbs)

    @property
    def name(self):
        return self.instance['LoadBalancerName']

    @property
    def created_time(self):
        return self.instance['CreatedTime']

    def terminate(self):
        self.client.delete_load_balancer(LoadBalancerName=self.name)


class ElasticLoadBalancingv2(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_elastic_lbs(client):
            return client.get_paginator(
                'describe_load_balancers').paginate().build_full_result()['LoadBalancers']
        return Terminator._create(credentials, ElasticLoadBalancingv2, 'elbv2', _paginate_elastic_lbs)

    @property
    def name(self):
        return self.instance['LoadBalancerArn']

    @property
    def created_time(self):
        return self.instance['CreatedTime']

    @property
    def age_limit(self):
        return datetime.timedelta(minutes=15)

    def _find_listeners(self):
        # Listeners can't be listed or described without providing an ELB or Listener ARN, so we have to handle them here
        return [listener['ListenerArn'] for listener in self.client.describe_listeners(LoadBalancerArn=self.name)['Listeners']]

    def terminate(self):
        self.client.delete_load_balancer(LoadBalancerArn=self.name)
        for listener in self._find_listeners():
            self.client.delete_listener(ListenerArn=listener)


class Elbv2TargetGroups(DbTerminator):
    @staticmethod
    def create(credentials):
        def _paginate_target_groups(client):
            return client.get_paginator(
                'describe_target_groups').paginate().build_full_result()['TargetGroups']
        return Terminator._create(credentials, Elbv2TargetGroups, 'elbv2', _paginate_target_groups)

    @property
    def age_limit(self):
        return datetime.timedelta(minutes=15)

    @property
    def id(self):
        return self.instance['TargetGroupArn']

    @property
    def name(self):
        return self.instance['TargetGroupName']

    def terminate(self):
        self.client.delete_target_group(TargetGroupArn=self.id)


class Lightsail(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_lightsail_instances(client):
            return client.get_paginator('get_instances').paginate().build_full_result()['instances']
        return Terminator._create(credentials, Lightsail, 'lightsail', _paginate_lightsail_instances)

    @property
    def name(self):
        return self.instance['name']

    @property
    def created_time(self):
        return self.instance['createdAt']

    def terminate(self):
        self.client.delete_instance(instanceName=self.name)


class LightsailKeyPair(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_lightsail_key_pairs(client):
            return client.get_paginator('get_key_pairs').paginate().build_full_result()['keyPairs']
        return Terminator._create(credentials, LightsailKeyPair, 'lightsail', _paginate_lightsail_key_pairs)

    @property
    def name(self):
        return self.instance['name']

    @property
    def created_time(self):
        return self.instance['createdAt']

    def terminate(self):
        self.client.delete_key_pair(keyPairName=self.name)


class LightsailStaticIp(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_lightsail_static_ips(client):
            return client.get_paginator('get_static_ips').paginate().build_full_result()['staticIps']
        return Terminator._create(credentials, LightsailStaticIp, 'lightsail', _paginate_lightsail_static_ips)

    @property
    def name(self):
        return self.instance['name']

    @property
    def created_time(self):
        return self.instance['createdAt']

    def terminate(self):
        self.client.release_static_ip(staticIpName=self.name)


class AutoScalingGroup(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, AutoScalingGroup, 'autoscaling', lambda client: client.describe_auto_scaling_groups()['AutoScalingGroups'])

    @property
    def id(self):
        return self.instance['AutoScalingGroupName']

    @property
    def name(self):
        return self.instance['AutoScalingGroupName']

    @property
    def created_time(self):
        return self.instance['CreatedTime']

    def terminate(self):
        self.client.delete_auto_scaling_group(AutoScalingGroupName=self.name, ForceDelete=True)


class LaunchConfiguration(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(
            credentials,
            LaunchConfiguration,
            'autoscaling',
            lambda client: client.describe_launch_configurations()['LaunchConfigurations']
        )

    @property
    def id(self):
        return self.instance['LaunchConfigurationName']

    @property
    def name(self):
        return self.instance['LaunchConfigurationName']

    @property
    def created_time(self):
        return self.instance['CreatedTime']

    def terminate(self):
        try:
            self.client.delete_launch_configuration(LaunchConfigurationName=self.name)
        except botocore.exceptions.ClientError as ex:
            if not ex.response['Error']['Code'] == 'ResourceInUseFault':
                raise


class LaunchTemplate(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(
            credentials,
            LaunchTemplate,
            'ec2',
            lambda client: client.describe_launch_templates()['LaunchTemplates']
        )

    @property
    def id(self):
        return self.instance['LaunchTemplateId']

    @property
    def name(self):
        return self.instance['LaunchTemplateName']

    @property
    def created_time(self):
        return self.instance['CreateTime']

    def terminate(self):
        self.client.delete_launch_template(LaunchTemplateId=self.id)


class Ec2SpotInstanceRequest(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2SpotInstanceRequest, 'ec2', lambda client: client.describe_spot_instance_requests()['SpotInstanceRequests'])

    @property
    def name(self):
        return self.instance['SpotInstanceRequestId']

    @property
    def id(self):
        return self.instance['SpotInstanceRequestId']

    @property
    def created_time(self):
        return self.instance['CreateTime']

    def terminate(self):
        self.client.cancel_spot_instance_requests(SpotInstanceRequestIds=[self.id])
