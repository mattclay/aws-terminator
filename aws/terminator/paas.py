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
        return self.instance['LatestMatchingVersion']['CreatedDate']

    def terminate(self):
        for version in self.client.list_layer_versions(LayerName=self.name)['LayerVersions']:
            self.client.delete_layer_version(LayerName=self.name, VersionNumber=version['Version'])
