from datetime import datetime, timedelta

from . import DbTerminator, Terminator


class LambdaEventSourceMapping(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, LambdaEventSourceMapping, 'lambda', lambda client: client.list_event_source_mappings()['EventSourceMappings'])

    @property
    def id(self):
        return self.instance['UUID']

    @property
    def name(self):
        return self.id

    @property
    def ignore(self) -> bool:
        return self.instance['State'] in ('Creating', 'Enabling', 'Disabling', 'Updating', 'Deleting')

    def terminate(self):
        self.client.delete_event_source_mapping(UUID=self.id)


class LambdaLayers(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, LambdaLayers, 'lambda', lambda client: client.list_layers()['Layers'])

    @property
    def id(self):
        return self.instance['LayerArn']

    @property
    def name(self):
        return self.instance['LayerName']

    @property
    def created_time(self):
        return datetime.strptime(self.instance['LatestMatchingVersion']['CreatedDate'], "%Y-%m-%dT%H:%M:%S.%f%z")

    def terminate(self):
        for version in self.client.list_layer_versions(LayerName=self.name)['LayerVersions']:
            self.client.delete_layer_version(LayerName=self.name, VersionNumber=version['Version'])


class CloudFrontDistribution(Terminator):
    @staticmethod
    def create(credentials):
        def list_cloudfront_distributions(client):
            result = client.get_paginator('list_distributions').paginate().build_full_result()
            return result.get('DistributionList', {}).get('Items', [])

        return Terminator._create(credentials, CloudFrontDistribution, 'cloudfront', list_cloudfront_distributions)

    @property
    def created_time(self):
        return self.instance['LastModifiedTime']

    @property
    def name(self):
        return self.instance['DomainName']

    @property
    def Id(self):
        return self.instance['Id']

    def terminate(self):

        distribution = self.client.get_distribution(Id=self.Id)
        ETag = distribution['ETag']
        distribution = distribution['Distribution']
        if distribution.get('Status') == "Deployed":
            if distribution['DistributionConfig']['Enabled']:
                # disable distribution
                distribution['DistributionConfig']['Enabled'] = False
                self.client.update_distribution(DistributionConfig=distribution['DistributionConfig'], Id=self.Id, IfMatch=ETag)
            else:
                # delete distribution
                self.client.delete_distribution(Id=self.Id, IfMatch=ETag)


class CloudFrontStreamingDistribution(Terminator):
    @staticmethod
    def create(credentials):
        def list_cloudfront_streaming_distributions(client):
            result = client.get_paginator('list_streaming_distributions').paginate().build_full_result()
            return result.get('StreamingDistributionList', {}).get('Items', [])

        return Terminator._create(credentials, CloudFrontStreamingDistribution, 'cloudfront', list_cloudfront_streaming_distributions)

    @property
    def created_time(self):
        return self.instance['LastModifiedTime']

    @property
    def name(self):
        return self.instance['DomainName']

    @property
    def Id(self):
        return self.instance['Id']

    def terminate(self):
        streaming_distribution = self.client.get_streaming_distribution(Id=self.Id)
        ETag = streaming_distribution['ETag']
        streaming_distribution = streaming_distribution['StreamingDistribution']
        if streaming_distribution.get('Status') == "Deployed":
            if streaming_distribution['StreamingDistributionConfig']['Enabled']:
                # disable streaming distribution
                streaming_distribution['StreamingDistributionConfig']['Enabled'] = False
                self.client.update_streaming_distribution(StreamingDistributionConfig=streaming_distribution['StreamingDistributionConfig'],
                                                          Id=self.Id,
                                                          IfMatch=ETag)
            else:
                # delete streaming distribution
                self.client.delete_streaming_distribution(Id=self.Id, IfMatch=ETag)


class CloudFrontOriginAccessIdentity(DbTerminator):
    @staticmethod
    def create(credentials):
        def list_cloud_front_origin_access_identities(client):
            identities = []
            result = client.get_paginator('list_cloud_front_origin_access_identities').paginate().build_full_result()
            for identity in result.get('CloudFrontOriginAccessIdentityList', {}).get('Items', []):
                identities.append(client.get_cloud_front_origin_access_identity(Id=identity['Id']))
            return identities

        return Terminator._create(credentials, CloudFrontOriginAccessIdentity, 'cloudfront', list_cloud_front_origin_access_identities)

    @property
    def id(self):
        return self.instance['ETag']

    @property
    def name(self):
        return self.instance['CloudFrontOriginAccessIdentity']['Id']

    def terminate(self):
        self.client.delete_cloud_front_origin_access_identity(Id=self.name, IfMatch=self.id)


class CloudFrontCachePolicy(DbTerminator):
    @staticmethod
    def create(credentials):
        def list_cloud_front_cache_policies(client):
            identities = []
            result = client.list_cache_policies(
                # Only retrieve the custom policies
                Type='custom'
            )
            for identity in result.get('CachePolicyList', {}).get('Items', []):
                identities.append(client.get_cache_policy(Id=identity['CachePolicy']['Id']))
            return identities

        return Terminator._create(credentials, CloudFrontCachePolicy, 'cloudfront', list_cloud_front_cache_policies)

    @property
    def id(self):
        return self.instance['ETag']

    @property
    def name(self):
        return self.instance['CachePolicy']['Id']

    @property
    def age_limit(self):
        return timedelta(minutes=30)

    def terminate(self):
        self.client.delete_cache_policy(Id=self.name, IfMatch=self.id)


class CloudFrontOriginRequestPolicy(DbTerminator):
    @staticmethod
    def create(credentials):
        def list_cloud_front_origin_request_policies(client):
            identities = []
            result = client.list_origin_request_policies(
                # Only retrieve the custom policies
                Type='custom'
            )
            for identity in result.get('OriginRequestPolicyList', {}).get('Items', []):
                identities.append(client.get_origin_request_policy(Id=identity['OriginRequestPolicy']['Id']))
            return identities

        return Terminator._create(credentials, CloudFrontOriginRequestPolicy, 'cloudfront', list_cloud_front_origin_request_policies)

    @property
    def id(self):
        return self.instance['ETag']

    @property
    def name(self):
        return self.instance['OriginRequestPolicy']['Id']

    @property
    def age_limit(self):
        return timedelta(minutes=30)

    def terminate(self):
        self.client.delete_origin_request_policy(Id=self.name, IfMatch=self.id)


class Ecs(DbTerminator):
    @property
    def age_limit(self):
        return timedelta(minutes=20)

    @property
    def name(self):
        return self.instance['clusterName']

    @staticmethod
    def create(credentials):
        def _paginate_cluster_results(client):
            names = client.get_paginator('list_clusters').paginate(
                PaginationConfig={
                    'PageSize': 100,
                }
            ).build_full_result()['clusterArns']

            if not names:
                return []

            return client.describe_clusters(clusters=names)['clusters']

        return Terminator._create(credentials, Ecs, 'ecs', _paginate_cluster_results)

    def terminate(self):
        def _paginate_task_results(container_instance=None):
            params = {
                'cluster': self.name,
                'PaginationConfig': {
                    'PageSize': 100,
                }
            }

            if container_instance:
                params['containerInstance'] = container_instance

            names = self.client.get_paginator('list_tasks').paginate(
                **params
            ).build_full_result()['taskArns']

            return [] if not names else names

        def _paginate_task_definition_results():
            names = self.client.get_paginator('list_task_definitions').paginate(
                PaginationConfig={
                    'PageSize': 100,
                }
            ).build_full_result()['taskDefinitionArns']

            return [] if not names else names

        def _paginate_container_instance_results():
            names = self.client.get_paginator('list_container_instances').paginate(
                cluster=self.name,
                PaginationConfig={
                    'PageSize': 100,
                }
            ).build_full_result()['containerInstanceArns']

            return [] if not names else names

        def _paginate_service_results():
            names = self.client.get_paginator('list_services').paginate(
                cluster=self.name,
                PaginationConfig={
                    'PageSize': 100,
                }
            ).build_full_result()['serviceArns']

            return [] if not names else names

        # If there are running services, delete them first
        services = _paginate_service_results()
        for each in services:
            self.client.delete_service(cluster=self.name, service=each, force=True)

        # Deregister container instances and stop any running task
        container_instances = _paginate_container_instance_results()
        for each in container_instances:
            self.client.deregister_container_instance(containerInstance=each['containerInstanceArn'], force=True)

        # Deregister task definitions
        task_definitions = _paginate_task_definition_results()
        for each in task_definitions:
            self.client.deregister_task_definition(taskDefinition=each)

        # Stop all the tasks
        tasks = _paginate_task_results()
        for each in tasks:
            self.client.stop_task(cluster=self.name, task=each)

        # Delete cluster
        try:
            self.client.delete_cluster(cluster=self.name)
        except (self.client.exceptions.ClusterContainsServicesException, self.client.exceptions.ClusterContainsTasksException):
            pass


class EcsCluster(DbTerminator):
    @property
    def age_limit(self):
        return timedelta(minutes=30)

    @property
    def name(self):
        return self.instance['clusterName']

    @staticmethod
    def create(credentials):
        def _paginate_cluster_results(client):
            names = client.get_paginator('list_clusters').paginate(
                PaginationConfig={
                    'PageSize': 100,
                }
            ).build_full_result()['clusterArns']

            if not names:
                return []

            return client.describe_clusters(clusters=names)['clusters']

        return Terminator._create(credentials, EcsCluster, 'ecs', _paginate_cluster_results)

    def terminate(self):
        self.client.delete_cluster(cluster=self.name)
