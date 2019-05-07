from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

try:
    from botocore.session import get_session
    HAS_BOTOCORE = True
except ImportError:
    HAS_BOTOCORE = False


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):

        if not HAS_BOTOCORE:
            raise AnsibleError("The aws_regions lookup requires the botocore library")

        loader = get_session().get_component('data_loader')
        endpoint_data = loader.load_data('endpoints')

        if not terms:
            ret = list(endpoint_data['partitions'][0]['regions'].keys())
        else:
            ret = []
            for service in terms:
                regions = list(endpoint_data['partitions'][0]['services'][service]['endpoints'].keys())
                ret.append({service: regions})

        return ret
