#!/usr/bin/python
# Copyright (C) 2016 Matt Clay <matt@mystile.com>
# GNU General Public License v3.0+ (see ansible/LICENSE.md or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json

try:
    import botocore
except ImportError:
    botocore = None

from ansible.module_utils.basic import (
    AnsibleModule,
)

from ansible.module_utils.ec2 import (
    boto3_conn,
    ec2_argument_spec,
    get_aws_connection_info,
    HAS_BOTO3,
)


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        state=dict(required=False, default='present', type='str', choices=['present', 'absent']),
        swagger=dict(required=True, type='str'),
        api_name=dict(required=False, default=None, type='str'),
        stage_name=dict(required=True, type='str'),
        stage_description=dict(required=False, default='', type='str'),
        deployment_description=dict(required=False, default='', type='str'),
        mode=dict(required=False, default='merge', type='str', choices=['merge', 'overwrite']),
        fail_on_warnings=dict(required=False, default=True, type='bool'),
        stage_variables=dict(required=False, default={}, type='dict'),
    ))

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    ag = ApiGatewayModule(module, module.check_mode, module.params)

    error, changed, result = ag.run()

    if error is None:
        module.exit_json(changed=changed, meta=result)
    else:
        module.fail_json(msg=error, meta=result)


class ApiGatewayModule:
    def __init__(self, module, check_mode, params):
        self.module = module
        self.check_mode = check_mode
        self.params = params
        self.ag = None

    def run(self):
        if not HAS_BOTO3:
            return 'the boto3 python module is required to use this module', None, None

        region, ec2_url, aws_connect_kwargs = get_aws_connection_info(self.module, boto3=True)

        self.ag = boto3_conn(self.module, conn_type='client', resource='apigateway', region=region, endpoint=ec2_url,
                             **aws_connect_kwargs)

        choice_map = dict(
            present=self.api_present,
            absent=self.api_absent,
        )

        return choice_map.get(self.params['state'])()

    def api_present(self):
        local_swagger = self.params['swagger']
        api_name = self.params['api_name']
        stage_name = self.params['stage_name']
        stage_description = self.params['stage_description']
        deployment_description = self.params['deployment_description']
        mode = self.params['mode']
        fail_on_warnings = self.params['fail_on_warnings']
        stage_variables = self.params['stage_variables']

        if api_name is None:
            api_name = json.loads(local_swagger)['info']['title']

        apis = [api for api in self.ag.get_rest_apis()['items'] if api['name'] == api_name]

        if not apis:
            api_id = None
        elif len(apis) == 1:
            api_id = apis[0]['id']
        else:
            return 'api name "%s" is ambiguous' % api_name, None, None

        changed = False

        if api_id is None:
            if not self.check_mode:
                api = self.import_swagger(fail_on_warnings, local_swagger)
                api_id = api['id']
            changed = True
        else:
            remote_swagger = self.export_swagger(api_id, stage_name)

            if remote_swagger is None:
                changed = True
            else:
                local_obj = json.loads(local_swagger)
                remote_obj = json.loads(remote_swagger)

                local_obj['host'] = remote_obj['host']
                local_obj['info']['version'] = remote_obj['info']['version']

                local_compare = json.dumps(local_obj, indent=4, sort_keys=True)
                remote_compare = json.dumps(remote_obj, indent=4, sort_keys=True)

                if local_compare != remote_compare:
                    if not self.check_mode:
                        self.put_swagger(api_id, mode, fail_on_warnings, local_compare)

                    changed = True

        if changed and not self.check_mode:
            self.ag.create_deployment(
                restApiId=api_id,
                stageName=stage_name,
                stageDescription=stage_description,
                description=deployment_description,
                variables=stage_variables,
            )

        result = dict(
            id=api_id,
        )

        if changed:
            return None, True, result

        return None, False, result

    def api_absent(self):
        raise Exception('FIXME: not implemented')

    def put_swagger(self, api_id, mode, fail_on_warnings, body):
        return self.ag.put_rest_api(
            restApiId=api_id,
            mode=mode,
            failOnWarnings=fail_on_warnings,
            parameters={'extensions': 'integrations'},
            body=body,
        )

    def import_swagger(self, fail_on_warnings, body):
        return self.ag.import_rest_api(
            failOnWarnings=fail_on_warnings,
            parameters={'extensions': 'integrations'},
            body=body,
        )

    def export_swagger(self, api_id, stage_name):
        try:
            return self.ag.get_export(
                restApiId=api_id,
                stageName=stage_name,
                exportType='swagger',
                parameters={'extensions': 'integrations'},
            )['body'].read()
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] == 'NotFoundException':
                return None
            raise


if __name__ == '__main__':
    main()
