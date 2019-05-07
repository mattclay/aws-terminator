#!/usr/bin/python
# Copyright (C) 2016 Matt Clay <matt@mystile.com>
# GNU General Public License v3.0+ (see ansible/LICENSE.md or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

try:
    import botocore
except ImportError:
    botocore = None

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
    argument_spec.update(dict(
        function_name=dict(required=True, type='str'),
        state=dict(required=False, default='present', type='str', choices=['present', 'absent']),
        version=dict(required=True, type='str'),
        name=dict(required=True, type='str'),
        description=dict(required=False, default='', type='str'),
    ))

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    lm = LambdaAliasModule(module, module.check_mode, module.params)

    error, changed, result = lm.run()

    if error is None:
        module.exit_json(changed=changed, meta=result)
    else:
        module.fail_json(msg=error, meta=result)


class LambdaAliasModule:
    def __init__(self, module, check_mode, params):
        self.module = module
        self.check_mode = check_mode
        self.params = params
        self.al = None
        self.iam = None
        self.region = None
        self.account_id = None

    def run(self):
        if not HAS_BOTO3:
            return 'the boto3 python module is required to use this module', None, None

        region, ec2_url, aws_connect_kwargs = get_aws_connection_info(self.module, boto3=True)

        self.region = region

        self.al = boto3_conn(self.module, conn_type='client', resource='lambda', region=region, endpoint=ec2_url,
                             **aws_connect_kwargs)

        self.iam = boto3_conn(self.module, conn_type='resource', resource='iam', region=region, endpoint=ec2_url,
                              **aws_connect_kwargs)

        self.account_id = self.iam.CurrentUser().arn.split(':')[4]

        choice_map = dict(
            present=self.alias_present,
            absent=self.alias_absent,
        )

        return choice_map.get(self.params['state'])()

    def alias_present(self):
        alias = self.get_alias()

        return self.create_or_update_alias(alias)

    def get_alias(self):
        try:
            return self.al.get_alias(
                FunctionName=self.params['function_name'],
                Name=self.params['name'],
            )
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] == 'ResourceNotFoundException':
                return None
            raise

    def alias_absent(self):
        raise Exception('FIXME: not implemented')

    def create_or_update_alias(self, remote_alias):
        local_alias = dict(
            Name=self.params['name'],
            FunctionVersion=self.params['version'],
            Description=self.params['description'],
        )

        if remote_alias is None:
            changed = True
        else:
            changed = any([k for k in local_alias if local_alias[k] != remote_alias[k]])

        args = dict(
            FunctionName=self.params['function_name'],
            **local_alias
        )

        if changed and not self.check_mode:
            if remote_alias is None:
                data = self.al.create_alias(**args)
            else:
                data = self.al.update_alias(**args)
        else:
            arn = 'arn:aws:lambda:%s:%s:function:%s:%s' % (
                self.region, self.account_id, self.params['function_name'], self.params['name'])

            data = dict(
                FunctionArn=arn,
                **args
            )

        result = camel_dict_to_snake_dict(data)

        return None, changed, result


if __name__ == '__main__':
    main()
