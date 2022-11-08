import botocore
import botocore.exceptions

from . import DbTerminator, Terminator


class IamRole(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, IamRole, 'iam', lambda client: client.list_roles()['Roles'])

    @property
    def id(self):
        return self.instance['RoleId']

    @property
    def name(self):
        return self.instance['RoleName']

    @property
    def ignore(self):
        return not self.name.startswith('ansible-test')

    @property
    def created_time(self):
        return self.instance['CreateDate']

    def terminate(self):
        try:
            self.client.delete_role(RoleName=self.name)
            return
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] != 'DeleteConflict':
                raise

        for policy in self.client.list_attached_role_policies(RoleName=self.name)['AttachedPolicies']:
            self.client.detach_role_policy(RoleName=self.name, PolicyArn=policy['PolicyArn'])
        for policy in self.client.list_role_policies(RoleName=self.name)['PolicyNames']:
            self.client.delete_role_policy(RoleName=self.name, PolicyName=policy)

        self.client.delete_role(RoleName=self.name)


class IamInstanceProfile(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, IamInstanceProfile, 'iam', lambda client: client.list_instance_profiles()['InstanceProfiles'])

    @property
    def id(self):
        return self.instance['InstanceProfileId']

    @property
    def name(self):
        return self.instance['InstanceProfileName']

    @property
    def ignore(self):
        return not self.name.startswith('ansible-test-')

    @property
    def created_time(self):
        return self.instance['CreateDate']

    def terminate(self):
        for role in self.instance['Roles']:
            self.client.remove_role_from_instance_profile(InstanceProfileName=self.name, RoleName=role['RoleName'])

        self.client.delete_instance_profile(InstanceProfileName=self.name)


class IamServerCertificate(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, IamServerCertificate, 'iam', lambda client: client.list_server_certificates()['ServerCertificateMetadataList'])

    @property
    def id(self):
        return self.instance['ServerCertificateId']

    @property
    def name(self):
        return self.instance['ServerCertificateName']

    @property
    def ignore(self):
        return not self.name.startswith('ansible-test-')

    @property
    def created_time(self):
        return self.instance['UploadDate']

    def terminate(self):
        self.client.delete_server_certificate(ServerCertificateName=self.name)


class ACMCertificate(DbTerminator):
    # ACM provides a created time, but there are cases where describe_certificate can fail
    # We need to be able to delete anyway, so use DbTerminator
    # https://github.com/ansible/ansible/issues/67788
    @staticmethod
    def create(credentials):
        return Terminator._create(
            credentials, ACMCertificate, 'acm',
            lambda client: client.get_paginator('list_certificates').paginate().build_full_result()['CertificateSummaryList']
        )

    @property
    def id(self):
        return self.instance['CertificateArn']

    @property
    def name(self):
        return self.instance['CertificateArn']

    def terminate(self):
        self.client.delete_certificate(CertificateArn=self.id)


class IAMSamlProvider(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(
            credentials, IAMSamlProvider, 'iam',
            lambda client: client.list_saml_providers()['SAMLProviderList']
        )

    @property
    def id(self):
        return self.instance['Arn']

    @property
    def name(self):
        return self.instance['Arn'].split('/')[-1]

    @property
    def ignore(self):
        return not self.name.startswith('ansible-test-')

    @property
    def created_time(self):
        return self.instance['CreateDate']

    def terminate(self):
        self.client.delete_saml_provider(SAMLProviderArn=self.id)


class KMSKey(Terminator):
    @staticmethod
    def create(credentials):
        def get_paginated_keys(client):
            return client.get_paginator('list_keys').paginate().build_full_result()['Keys']

        def get_key_details(client, key):
            metadata = client.describe_key(KeyId=key['KeyId'])['KeyMetadata']
            _aliases = client.list_aliases(KeyId=key['KeyId'])['Aliases']
            aliases = []
            for alias in _aliases:
                aliases.append(alias['AliasName'])
            metadata['Aliases'] = aliases
            return metadata

        def get_detailed_keys(client):
            detailed_keys = []
            for key in get_paginated_keys(client):
                metadata = get_key_details(client, key)
                if metadata:
                    detailed_keys.append(metadata)
            return detailed_keys

        return Terminator._create(credentials, KMSKey, 'kms', get_detailed_keys)

    @property
    def ignore(self):
        # The key is already in a 'pending deletion' state, and doesn't need
        # anything more done to it.
        if self.instance['KeyState'] == 'PendingDeletion':
            return True
        # Don't try deleting the AWS managed keys (they're not charged for)
        for alias in self.instance['Aliases']:
            if alias.startswith('alias/aws/'):
                return True
        return False

    @property
    def created_time(self):
        return self.instance['CreationDate']

    @property
    def id(self):
        return self.instance['KeyId']

    @property
    def name(self):
        return self.instance['Aliases']

    def terminate(self):
        self.client.schedule_key_deletion(KeyId=self.id, PendingWindowInDays=7)


class Secret(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Secret, 'secretsmanager', lambda client: client.list_secrets()['SecretList'])

    @property
    def id(self):
        return self.instance['ARN']

    @property
    def name(self):
        return self.instance['Name']

    @property
    def ignore(self):
        return not self.name.startswith('ansible-test')

    @property
    def created_time(self):
        return self.instance['CreatedDate']

    @property
    def age_limit(self):
        return datetime.timedelta(minutes=30)

    def terminate(self):
        self.client.delete_secret(SecretId=self.name, RecoveryWindowInDays=7)
