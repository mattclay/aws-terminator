from . import SimpleDbTerminator, Terminator, get_tag_dict_from_tag_list


class GlueConnection(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, GlueConnection, 'glue', lambda client: client.get_connections()['ConnectionList'])

    @property
    def id(self):
        return self.instance['Name']

    @property
    def name(self):
        return self.instance['Name']

    @property
    def created_time(self):
        return self.instance['CreationTime']

    def terminate(self):
        self.client.delete_connection(ConnectionName=self.name)


class Glacier(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Glacier, 'glacier', lambda client: client.list_vaults()['VaultList'])

    @property
    def id(self):
        return self.instance['VaultARN']

    @property
    def name(self):
        return self.instance['VaultName']

    @property
    def created_time(self):
        return self.instance['CreationDate']

    def terminate(self):
        self.client.delete_vault(vaultName=self.name)


class IotThing(SimpleDbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, IotThing, 'iot', lambda client: client.list_things()['things'])

    @property
    def id(self):
        return self.instance['thingArn']

    @property
    def name(self):
        return self.instance['thingName']

    @property
    def version(self):
        return self.instance['version']

    def terminate(self):
        self.client.delete_thing(thingName=self.name, expectedVersion=self.version)


class RedshiftCluster(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, RedshiftCluster, 'redshift', lambda client: client.describe_clusters()['Clusters'])

    @property
    def name(self):
        return get_tag_dict_from_tag_list(self.instance.get('Tags')).get('Name')

    @property
    def id(self):
        return self.instance['ClusterIdentifier']

    @property
    def created_time(self):
        return self.instance['ClusterCreateTime']

    def terminate(self):
        self.client.delete_cluster(ClusterIdentifier=self.id, SkipFinalClusterSnapshot=True)
