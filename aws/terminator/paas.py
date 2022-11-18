from datetime import datetime

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


def wait_until_deployed(client, Id, waiter_name, wait_timeout=1800):
    waiter = client.get_waiter(waiter_name)
    attempts = 1 + int(wait_timeout / 60)
    waiter.wait(Id=Id, WaiterConfig={'MaxAttempts': attempts})


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
                distribution['DistributionConfig']['Enabled'] = False
                self.client.update_distribution(DistributionConfig=distribution['DistributionConfig'], Id=self.Id, IfMatch=ETag)
                # wait until the distribution is deployed
                wait_until_deployed(self.client, self.Id, 'distribution_deployed')
                # Get ETag value after update
                distribution = self.client.get_distribution(Id=self.Id)
                ETag = distribution['ETag']
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
                streaming_distribution['StreamingDistributionConfig']['Enabled'] = False
                self.client.update_streaming_distribution(StreamingDistributionConfig=streaming_distribution['StreamingDistributionConfig'],
                                                          Id=self.Id,
                                                          IfMatch=ETag)
                # wait until the streaming distribution is deployed
                wait_until_deployed(self.client, self.Id, 'streaming_distribution_deployed')
                # Get ETag value after update
                streaming_distribution = self.client.get_streaming_distribution(Id=self.Id)
                ETag = streaming_distribution['ETag']
            self.client.delete_streaming_distribution(Id=self.Id, IfMatch=ETag)
