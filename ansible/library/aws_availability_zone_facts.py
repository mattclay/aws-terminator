#!/usr/bin/python
# Copyright (C) 2016 Matt Clay <matt@mystile.com>
# GNU General Public License v3.0+ (see ansible/LICENSE.md or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.module_utils.basic import (
    AnsibleModule,
)

from ansible.module_utils.ec2 import (
    boto3_conn,
    camel_dict_to_snake_dict,
    ec2_argument_spec,
    get_aws_connection_info,
    HAS_BOTO3,
)


def main():
    argument_spec = ec2_argument_spec()

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    lm = AwsAvailabilityZoneFactsModule(module, module.check_mode, module.params)

    error, facts = lm.run()

    if error is None:
        module.exit_json(changed=False, ansible_facts=facts)
    else:
        module.fail_json(msg=error, ansible_facts=facts)


class AwsAvailabilityZoneFactsModule:
    def __init__(self, module, check_mode, params):
        self.module = module
        self.check_mode = check_mode
        self.params = params
        self.ec2 = None

    def run(self):
        if not HAS_BOTO3:
            return 'the boto3 python module is required to use this module', None, None

        region, ec2_url, aws_connect_kwargs = get_aws_connection_info(self.module, boto3=True)

        self.ec2 = boto3_conn(self.module, conn_type='client', resource='ec2', region=region, endpoint=ec2_url,
                              **aws_connect_kwargs)

        zones = self.ec2.describe_availability_zones()['AvailabilityZones']
        zones = [camel_dict_to_snake_dict(z) for z in zones]

        facts = dict(
            aws_availability_zones=zones,
        )

        return None, facts


if __name__ == '__main__':
    main()
