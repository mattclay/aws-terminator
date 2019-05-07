#!/usr/bin/python
# Copyright (C) 2016 Matt Clay <matt@mystile.com>
# GNU General Public License v3.0+ (see ansible/LICENSE.md or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import uuid

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
        function_name=dict(required=True, type='str', aliases=['name']),
        state=dict(required=False, default='present', type='str', choices=['present', 'absent']),
        source_arn=dict(required=True, type='str'),
        qualifier=dict(required=False, default=None, type='str'),
        principal_service=dict(required=True, type='str'),
    ))

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    lm = LambdaPolicyModule(module, module.check_mode, module.params)

    error, changed, result = lm.run()

    if error is None:
        module.exit_json(changed=changed, meta=result)
    else:
        module.fail_json(msg=error, meta=result)


class LambdaPolicyModule:
    def __init__(self, module, check_mode, params):
        self.module = module
        self.check_mode = check_mode
        self.params = params
        self.al = None
        self.iam = None
        self.account_id = None

    def run(self):
        if not HAS_BOTO3:
            return 'the boto3 python module is required to use this module', None, None

        region, ec2_url, aws_connect_kwargs = get_aws_connection_info(self.module, boto3=True)

        self.al = boto3_conn(self.module, conn_type='client', resource='lambda', region=region, endpoint=ec2_url,
                             **aws_connect_kwargs)

        self.iam = boto3_conn(self.module, conn_type='resource', resource='iam', region=region, endpoint=ec2_url,
                              **aws_connect_kwargs)

        self.account_id = self.iam.CurrentUser().arn.split(':')[4]

        self.params['function_arn'] = 'arn:aws:lambda:%s:%s:function:%s' % (region, self.account_id, self.params['function_name'])

        if self.params['qualifier']:
            self.params['function_arn'] += ':%s' % self.params['qualifier']

        choice_map = dict(
            present=self.policy_present,
            absent=self.policy_absent,
        )

        return choice_map.get(self.params['state'])()

    def policy_present(self):
        remote_permissions = self.get_permissions()
        remote_permissions = [p for p in remote_permissions if
                              p['Action'] == 'lambda:InvokeFunction' and
                              p['Effect'] == 'Allow' and
                              p['Principal']['Service'] == self.params['principal_service'] and
                              p['Resource'] == self.params['function_arn'] and
                              p['Condition']['ArnLike']['AWS:SourceArn'] == self.params['source_arn']]

        remote_permission = remote_permissions[0] if remote_permissions else None

        if remote_permission is None:
            return self.create_permission()

        return self.update_permission(remote_permission)

    def policy_absent(self):
        raise Exception('FIXME: not implemented')

    def get_permissions(self):
        args = {}

        if self.params['qualifier'] is not None:
            args['Qualifier'] = self.params['qualifier']

        try:
            result = self.al.get_policy(
                FunctionName=self.params['function_name'],
                **args
            )
            policy = json.loads(result['Policy'])
            return policy['Statement']
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] == 'ResourceNotFoundException':
                return []
            raise

    def create_permission(self):
        args = dict(
            FunctionName=self.params['function_name'],
            StatementId=str(uuid.uuid4()),
            Action='lambda:InvokeFunction',
            Principal=self.params['principal_service'],
            SourceArn=self.params['source_arn'],
        )

        if self.params['qualifier'] is not None:
            args['Qualifier'] = self.params['qualifier']

        if self.check_mode:
            response = camel_dict_to_snake_dict(args)
        else:
            response = self.al.add_permission(**args)

        return None, True, response

    def update_permission(self, remote_permission):
        return None, False, remote_permission


if __name__ == '__main__':
    main()
