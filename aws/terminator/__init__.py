import abc
import datetime
import inspect
import logging
import os
import re

from boto3.dynamodb.conditions import Attr
import boto3
import botocore
import botocore.exceptions
import dateutil

logger = logging.getLogger('cleanup')

AWS_REGION = 'us-east-1'


def import_plugins():
    skip_files = ('__init__.py',)
    import_names = [os.path.splitext(name)[0] for name in os.listdir(os.path.dirname(__file__)) if name.endswith('.py') and name not in skip_files]
    for import_name in import_names:
        __import__(f'terminator.{import_name}')


def cleanup(stage, check, force, api_name, test_account_id):
    """
    :type stage: str
    :type check: bool
    :type force: bool
    :type api_name: str
    :type test_account_id: str
    """
    kvs.domain_name = re.sub(r'[^a-zA-Z0-9]+', '_', f'{api_name}-resources-{stage}')
    kvs.initialize()

    cleanup_test_account(stage, check, force, api_name, test_account_id)
    cleanup_database(check, force)



def assume_session(role, session_name):
    sts = boto3.client('sts')
    credentials = sts.assume_role(
        RoleArn=role, RoleSessionName=session_name).get('Credentials')
    return boto3.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'])


def cleanup_test_account(stage, check, force, api_name, test_account_id):
    """
    :type stage: str
    :type check: bool
    :type force: bool
    :type api_name: str
    :type test_account_id: str
    """

    role = f'arn:aws:iam::{test_account_id}:role/{api_name}-test-{stage}'
    credentials = assume_session(role, 'cleanup')

    for terminator_type in sorted(get_concrete_subclasses(Terminator), key=lambda value: value.__name__):
        # noinspection PyBroadException
        try:
            instances = terminator_type.create(credentials)

            for instance in instances:
                if instance.ignore:
                    status = 'ignored'
                elif force:
                    status = terminate(instance, check)
                elif instance.age is None:
                    status = 'unsupported'
                elif instance.stale:
                    status = terminate(instance, check)
                else:
                    status = 'skipped'

                if instance.ignore:
                    logger.debug('%s %s', status, instance)
                else:
                    logger.info('%s %s', status, instance)
        except Exception:
            logger.exception('exception processing resource type: %s', terminator_type)


def cleanup_database(check, force):
    """
    :type check: bool
    :type force: bool
    """
    scan_options = {}

    if not force:
        now = datetime.datetime.utcnow().replace(tzinfo=dateutil.tz.tz.tzutc(), microsecond=0) - datetime.timedelta(minutes=60)
        scan_options['FilterExpression'] = Attr('created_time').lt(now.isoformat())

    scan_options['ProjectionExpression'] = kvs.primary_key
    scan_options['Limit'] = 25
    scan_options['ConsistentRead'] = False

    result = kvs.table.scan(
        **scan_options
    )

    if 'Items' not in result:
        return

    items = result['Items']

    if items and not check:
        with kvs.table.batch_writer():
            for item in items:
                kvs.table.delete_item(Key=item)

    if check:
        status = 'checked'
    else:
        status = 'purged'

    for item in items:
        logger.info('%s database item: %s', status, item['id'])


def terminate(instance, check):
    """
    :type instance: Terminator
    :type check: bool
    :rtype: str
    """
    if check:
        return 'checked'

    # noinspection PyBroadException
    try:
        instance.terminate()
        instance.cleanup()
    except botocore.exceptions.ClientError as ex:
        error_code = ex.response['Error']['Code']

        if error_code == 'TooManyRequestsException':
            logger.warning('error "%s" terminating %s', error_code, instance, exc_info=1)
        else:
            logger.exception('error "%s" terminating %s', error_code, instance)
    except Exception:
        logger.exception('exception terminating %s', instance)

    return 'terminated'


def get_concrete_subclasses(class_type):
    """
    :type class_type: type
    :rtype: set[class]
    """
    subclasses = set()
    queue = [class_type]

    while queue:
        parent = queue.pop()

        for child in parent.__subclasses__():
            if child not in subclasses:
                queue.append(child)
                if not inspect.isabstract(child):
                    subclasses.add(child)

    return subclasses


def get_account_id(credentials):
    client = boto3.client(
        'sts',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=AWS_REGION,
    )
    return client.get_caller_identity()["Account"]


def get_tag_dict_from_tag_list(tag_list):
    """
    :type tag_list: list[dict[str, str]] | None
    :rtype: dict[str, str]
    """
    if tag_list is None:
        return {}

    return dict((tag['Key'], tag['Value']) for tag in tag_list)


class Terminator(abc.ABC):
    """Base class for classes which find and terminate AWS resources."""
    _default_vpc = None  # safe as long as executing only within a single region

    def __init__(self, client, instance):
        """
        :type client: any
        :type instance: any
        """
        self.client = client
        self.instance = instance
        self.now = datetime.datetime.utcnow().replace(tzinfo=dateutil.tz.tz.tzutc(), microsecond=0)

    @property
    def age_limit(self):
        return datetime.timedelta(minutes=10)

    @property
    def id(self):
        """
        :rtype: str | None
        """
        return None

    @property
    @abc.abstractmethod
    def name(self):
        """
        :rtype: str
        """

    @property
    @abc.abstractmethod
    def created_time(self):
        """
        :rtype: datetime.datetime | None
        """

    @property
    def ignore(self):
        """
        :rtype: bool
        """
        return False

    @abc.abstractmethod
    def terminate(self):
        """Terminate or delete the AWS resource."""

    def cleanup(self):
        """Cleanup to perform after termination."""

    @property
    def age(self):
        """
        :rtype: datetime.timedelta | None
        """
        return self.now - self.created_time if self.created_time else None

    @property
    def stale(self):
        """
        :rtype: bool
        """
        return self.age > self.age_limit if self.age else False

    def __str__(self):
        """
        :rtype: str
        """
        # noinspection PyBroadException
        try:
            if self.id:
                extra = f'id={self.id} '
            else:
                extra = ''

            return f'{type(self).__name__}: name={self.name}, {extra}age={self.age}, stale={self.stale}'
        except Exception:
            logger.exception('exception converting %s to string', type(self).__name__)
            return type(self).__name__

    @staticmethod
    def _create(session, instance_type, client_name, describe_lambda):
        """
        :type session: boto3.Session
        :type instance_type: type
        :type client_name: str
        :type describe_lambda: lambda
        :rtype: list[Terminator]
        """
        client = session.client(client_name, region_name=AWS_REGION)
        instances = describe_lambda(client)
        terminators = [instance_type(client, instance) for instance in instances]
        logger.debug('located %s: count=%d', instance_type.__name__, len(terminators))

        return terminators

    @property
    def default_vpc(self):
        """
        :rtype: dict[str, any]
        """
        if self._default_vpc is None:
            vpcs = self.client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])['Vpcs']

            if vpcs:
                self._default_vpc = vpcs[0]  # found default VPC
            else:
                self._default_vpc = {}  # no default VPC

        return self._default_vpc

    def is_vpc_default(self, vpc_id):
        """
        :type vpc_id: str
        :rtype: bool
        """
        return self.default_vpc.get('VpcId') == vpc_id


class DbTerminator(Terminator):
    """Base class for classes which find and terminate AWS resources with age tracked via DynamoDB."""
    def __init__(self, client, instance):
        """
        :type client: any
        :type instance: any
        """
        super(DbTerminator, self).__init__(client, instance)

        self._kvs_key = None
        self._kvs_value = None
        self._created_time = None

        if self.ignore:
            return

        # noinspection PyBroadException
        try:
            self._kvs_key = f'{type(self).__name__}:{self.id or self.name}'
            self._kvs_value = kvs.get(self._kvs_key)

            if not self._kvs_value:
                self._kvs_value = self.now.isoformat()
                kvs.set(self._kvs_key, self._kvs_value)

            self._created_time = datetime.datetime.strptime(self._kvs_value.replace('+00:00', ''), '%Y-%m-%dT%H:%M:%S').replace(tzinfo=dateutil.tz.tz.tzutc())
        except Exception:
            logger.exception('exception accessing key/value store: %s', self)

    @property
    @abc.abstractmethod
    def name(self):
        """
        :rtype: str
        """

    @property
    def created_time(self):
        """
        :rtype: datetime.datetime | None
        """
        return self._created_time

    @abc.abstractmethod
    def terminate(self):
        """Terminate or delete the AWS resource."""

    def cleanup(self):
        """Cleanup to perform after termination."""
        if not self._kvs_key or not self._kvs_value:
            logger.warning('skipping cleanup due to missing key/value data: %s', self)
            return

        kvs.delete(self._kvs_key, self._kvs_value)


class KeyValueStore:
    """ DynamoDB data store for the AWS terminator """
    def __init__(self, domain_name=None):
        """
        :type domain_name: str | None
        """
        self.ddb = boto3.resource('dynamodb', region_name=AWS_REGION)
        self.domain_name = domain_name
        self.table = None
        self.primary_key = 'id'
        self.initialized = False

    def initialize(self):
        """Deferred initialization of the DynamoDB database."""
        if self.initialized:
            return

        try:
            self.table = self.ddb.Table(self.domain_name)
            if self.table.table_status == 'DELETING':
                self.table.wait_until_not_exists()
                self.create_table()
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                self.create_table()
            else:
                raise e

        self.initialized = True

    def get(self, key):
        """
        :type key: str
        :rtype: str
        """
        self.initialize()

        item = self.table.get_item(
            Key={self.primary_key: key},
            ProjectionExpression='created_time',
        ).get('Item', {})

        return item.get('created_time')

    def set(self, key, value):
        """
        :type key: str
        :type value: str
        """
        self.initialize()

        # Don't replace an existing entry
        expression = Attr(self.primary_key).ne(key)

        attributes = {
            self.primary_key: key,
            'created_time': value,
        }

        self.table.put_item(
            Item=attributes,
            ConditionExpression=expression,
        )

    def create_table(self):
        """Creates a new DynamoDB database."""
        self.table = self.ddb.create_table(
            TableName=self.domain_name,
            AttributeDefinitions=[{
                'AttributeName': self.primary_key,
                'AttributeType': 'S'
            }],
            KeySchema=[{
                'AttributeName': self.primary_key,
                'KeyType': 'HASH'
            }],
            BillingMode='PAY_PER_REQUEST',
        )
        self.table.wait_until_exists()

    def delete(self, key, value):
        """
        :type key: str
        :type value: str
        """
        self.initialize()

        self.table.delete_item(
            Key={
                self.primary_key: key
            },
        )


import_plugins()

kvs = KeyValueStore()
