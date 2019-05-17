from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):

        if not HAS_BOTOCORE:
            raise AnsibleError("The aws_regions lookup requires the botocore library")

        if not terms:
            client = boto3.client('ec2', 'us-east-1')
            # It's possible ec2 regions and regions of other resources could diverge but this is currently not the case.
            ret = [region['RegionName'] for region in client.describe_regions()['Regions']]
            ret = list(endpoint_data['partitions'][0]['regions'].keys())
        else:
            ret = []
            for service in terms:
                regions = boto3.Session().get_available_regions(service)
                ret.append({service: regions})

        return ret
