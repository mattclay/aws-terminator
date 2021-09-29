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
