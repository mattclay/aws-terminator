import datetime

import botocore.exceptions

from . import DbTerminator, Terminator, get_tag_dict_from_tag_list


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


class RedshiftSubnetGroup(DbTerminator):
    @staticmethod
    def create(credentials):
        def paginate_redshift_subnet_groups(client):
            return client.get_paginator('describe_cluster_subnet_groups').paginate().build_full_result()['ClusterSubnetGroups']

        return Terminator._create(credentials, RedshiftSubnetGroup, 'redshift', paginate_redshift_subnet_groups)

    @property
    def id(self):
        return self.instance['ClusterSubnetGroupName']

    @property
    def name(self):
        return self.instance['ClusterSubnetGroupName']

    def terminate(self):
        self.client.delete_cluster_subnet_group(ClusterSubnetGroupName=self.id)


class Elasticache(Terminator):
    @staticmethod
    def create(credentials):

        def get_available_clusters(client):
            # describe_cache_clusters does not have a parameter to filter results
            # The key "CacheClusterCreateTime" does not exist while the cluster is being created.
            ignore_states = ('creating', 'deleting',)
            clusters = client.describe_cache_clusters()['CacheClusters']
            return [cluster for cluster in clusters if cluster['CacheClusterStatus'] not in ignore_states]

        return Terminator._create(credentials, Elasticache, 'elasticache', get_available_clusters)

    @property
    def name(self):
        # Name is used like an ID
        return self.instance['CacheClusterId']

    @property
    def id(self):
        return self.instance['CacheClusterId']

    @property
    def created_time(self):
        return self.instance['CacheClusterCreateTime']

    def terminate(self):
        self.client.delete_cache_cluster(CacheClusterId=self.id)


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


class GlueCrawler(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, GlueCrawler, 'glue', lambda client: client.get_crawlers()['Crawlers'])

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
        self.client.delete_crawler(Name=self.name)


class GlueJob(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, GlueJob, 'glue', lambda client: client.get_jobs()['Jobs'])

    @property
    def id(self):
        return self.instance['Name']

    @property
    def name(self):
        return self.instance['Name']

    @property
    def created_time(self):
        return self.instance['CreatedOn']

    def terminate(self):
        self.client.delete_job(JobName=self.name)


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

    @property
    def ignore(self):
        return self.name.startswith('default')

    def terminate(self):
        self.client.delete_db_parameter_group(DBParameterGroupName=self.name)


class RdsDbClusterParameterGroup(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, RdsDbClusterParameterGroup, 'rds',
                                  lambda client: client.describe_db_cluster_parameter_groups()['DBClusterParameterGroups'])

    @property
    def id(self):
        return self.instance['DBClusterParameterGroupArn']

    @property
    def name(self):
        return self.instance['DBClusterParameterGroupName']

    @property
    def ignore(self):
        return self.name.startswith('default')

    def terminate(self):
        self.client.delete_db_cluster_parameter_group(DBClusterParameterGroupName=self.name)


class RdsDbInstance(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, RdsDbInstance, 'rds', lambda client: client.describe_db_instances()['DBInstances'])

    @property
    def id(self):
        return self.instance['DBInstanceArn']

    @property
    def name(self):
        return self.instance['DBInstanceIdentifier']

    @property
    def age_limit(self):
        return datetime.timedelta(minutes=60)

    def terminate(self):
        try:
            self.client.modify_db_instance(DBInstanceIdentifier=self.name, BackupRetentionPeriod=0, DeletionProtection=False)
        except botocore.exceptions.ClientError as ex:
            # The instance can't be modifed when it's part of a cluster
            if ex.response['Error']['Code'] != 'InvalidParameterCombination':
                pass
        self.client.delete_db_instance(DBInstanceIdentifier=self.name, SkipFinalSnapshot=True)


class RdsDbSnapshot(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, RdsDbSnapshot, 'rds',
                                  lambda client: client.describe_db_snapshots(SnapshotType='manual')['DBSnapshots'])

    @property
    def id(self):
        return self.instance['DBSnapshotArn']

    @property
    def name(self):
        return self.instance['DBSnapshotIdentifier']

    def terminate(self):
        self.client.delete_db_snapshot(DBSnapshotIdentifier=self.name)


class RdsDbCluster(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, RdsDbCluster, 'rds', lambda client: client.describe_db_clusters()['DBClusters'])

    @property
    def id(self):
        return self.instance['DBClusterArn']

    @property
    def name(self):
        return self.instance['DBClusterIdentifier']

    @property
    def age_limit(self):
        return datetime.timedelta(minutes=60)

    @property
    def created_time(self):
        return self.instance['ClusterCreateTime']

    def terminate(self):
        self.client.modify_db_cluster(DBClusterIdentifier=self.name, BackupRetentionPeriod=1, DeletionProtection=False)
        self.client.delete_db_cluster(DBClusterIdentifier=self.name, SkipFinalSnapshot=True)


class RdsDbClusterSnapshot(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, RdsDbClusterSnapshot, 'rds',
                                  lambda client: client.describe_db_cluster_snapshots(SnapshotType='manual')['DBClusterSnapshots'])

    @property
    def id(self):
        return self.instance['DBClusterSnapshotArn']

    @property
    def name(self):
        return self.instance['DBClusterSnapshotIdentifier']

    @property
    def created_time(self):
        return self.instance['SnapshotCreateTime']

    def terminate(self):
        self.client.delete_db_cluster_snapshot(DBClusterSnapshotIdentifier=self.name)


class RedshiftCluster(Terminator):
    @staticmethod
    def create(credentials):

        def get_available_clusters(client):
            # describe_clusters does not have a parameter to filter results
            # The key "ClusterCreateTime" does not exist while the cluster is being created.
            ignore_states = ('creating', 'deleting',)
            clusters = client.describe_clusters()['Clusters']
            return [cluster for cluster in clusters if cluster['ClusterStatus'] not in ignore_states]

        return Terminator._create(credentials, RedshiftCluster, 'redshift', get_available_clusters)

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


class RdsOptionGroup(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, RdsOptionGroup, 'rds', lambda client: client.describe_option_groups()['OptionGroupsList'])

    @property
    def id(self):
        return self.instance['OptionGroupArn']

    @property
    def name(self):
        return self.instance['OptionGroupName']

    @property
    def ignore(self):
        return self.name.startswith('default')

    def terminate(self):
        self.client.delete_option_group(OptionGroupName=self.name)


class KafkaConfiguration(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, KafkaConfiguration, 'kafka', lambda client: client.list_configurations()['Configurations'])

    @property
    def id(self):
        return self.instance['Arn']

    @property
    def name(self):
        return self.instance['Name']

    @property
    def created_time(self):
        return self.instance['CreationTime']

    @property
    def age_limit(self):
        return datetime.timedelta(minutes=60)

    def terminate(self):
        self.client.delete_configuration(Arn=self.id)


class KafkaCluster(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, KafkaCluster, 'kafka', lambda client: client.list_clusters()['ClusterInfoList'])

    @property
    def id(self):
        return self.instance['ClusterArn']

    @property
    def name(self):
        return self.instance['ClusterName']

    @property
    def created_time(self):
        return self.instance['CreationTime']

    @property
    def age_limit(self):
        return datetime.timedelta(minutes=60)

    def terminate(self):
        self.client.delete_cluster(ClusterArn=self.id)
