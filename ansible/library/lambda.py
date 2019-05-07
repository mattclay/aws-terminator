#!/usr/bin/python
# Copyright (C) 2016 Matt Clay <matt@mystile.com>
# GNU General Public License v3.0+ (see ansible/LICENSE.md or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import base64
import hashlib
import os
import zipfile

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

from ansible.module_utils.six import (
    BytesIO,
)


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        function_name=dict(required=True, type='str', aliases=['name']),
        runtime=dict(required=True, type='str'),
        role=dict(required=True, type='str'),
        handler=dict(required=True, type='str'),
        code=dict(required=False, default=None, type='str'),
        local_path=dict(required=False, default=None, type='str'),
        s3_bucket=dict(required=False, default=None, type='str'),
        s3_key=dict(required=False, default=None, type='str'),
        s3_object_version=dict(required=False, default=None, type='str'),
        description=dict(required=False, default='', type='str'),
        timeout=dict(required=False, default=3, type='int'),
        memory_size=dict(required=False, default=128, type='int'),
        publish=dict(required=False, default=False, type='bool'),
        qualifier=dict(required=False, default=None, type='str'),
        state=dict(required=False, default='present', type='str', choices=['present', 'absent']),
        preserve_environment=dict(required=False, default=False, type='bool'),
        environment=dict(required=False, default=None, type='dict'),
        layers=dict(required=False, default=None, type='list'),
    ))

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        mutually_exclusive=[
            ['code', 'local_path', 's3_bucket'],
            ['code', 'local_path', 's3_key'],
            ['code', 'local_path', 's3_object_version'],
        ],
        required_together=[
            ['s3_bucket', 's3_key', 's3_object_version'],
        ],
    )

    lm = LambdaModule(module, module.check_mode, module.params)

    error, changed, result = lm.run()

    if error is None:
        module.exit_json(changed=changed, meta=result)
    else:
        module.fail_json(msg=error, meta=result)


class LambdaModule:
    def __init__(self, module, check_mode, params):
        self.module = module
        self.check_mode = check_mode
        self.params = params
        self.package = None
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

        if not self.params['role'].startswith('arn:aws:iam:'):
            self.params['role'] = 'arn:aws:iam::%s:role/%s' % (self.account_id, self.params['role'])

        choice_map = dict(
            present=self.function_present,
            absent=self.function_absent,
        )

        return choice_map.get(self.params['state'])()

    def function_present(self):
        qualifier = self.params['qualifier']
        remote_function = self.get_function(qualifier)

        if qualifier is not None and remote_function is None:
            # function not found by qualifier, look for $LATEST instead
            remote_function = self.get_function(None)

        if remote_function is None:
            return self.create_function()

        return self.update_function(remote_function)

    def function_absent(self):
        raise Exception('FIXME: not implemented')

    def get_function(self, qualifier):
        args = {}

        if qualifier is not None:
            args['Qualifier'] = qualifier

        try:
            result = self.al.get_function_configuration(
                FunctionName=self.params['function_name'],
                **args
            )
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] == 'ResourceNotFoundException':
                return None
            raise

        if result.get('Layers'):
            result['Layers'] = [layer['Arn'] for layer in result['Layers']]

        return result

    def get_package(self):
        if self.package is not None:
            return self.package

        if self.params['code'] is not None:
            self.package = self.create_package(self.params['code'])

        if self.params['local_path'] is not None:
            local_path = self.params['local_path']

            if self.check_mode and not os.path.exists(local_path):
                local_contents = ''
            else:
                with open(local_path, 'rb') as f:
                    local_contents = f.read()

            if os.path.splitext(local_path)[1] == '.zip':
                return local_contents

            self.package = self.create_package(local_contents)

        return self.package

    def create_package(self, code):
        data = BytesIO()
        zip_info = zipfile.ZipInfo(
            'lambda_function.py',
            (1980, 1, 1, 0, 0, 0),
        )
        zip_info.compress_type = zipfile.ZIP_DEFLATED
        zip_info.external_attr = 0o777 << 16  # give full access to included file

        with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as f:
            f.writestr(zip_info, code)

        return data.getvalue()

    def create_function(self):
        args = self.make_function_configuration()
        args['Code'] = self.make_function_code()
        args['Publish'] = self.params['publish']

        if not self.check_mode:
            if not args['Layers']:
                del args['Layers']

            if not args['Environment']:
                del args['Environment']

            api = self.al.create_function(**args)
            result = self.make_result(api)
        else:
            result = self.make_result(args)
            result['version'] = 1

        return None, True, result

    def update_function(self, remote_function):
        package = self.get_package()

        local_hash = base64.b64encode(hashlib.sha256(package).digest()).decode('ascii')
        remote_hash = remote_function['CodeSha256']

        local_config = self.make_function_configuration()

        if self.params['preserve_environment']:
            local_config['Environment'] = remote_function.get('Environment')

        remote_config = dict((k, remote_function.get(k, None)) for k in local_config)

        code_changed = local_hash != remote_hash
        config_changed = any([k for k in local_config if not self.are_equal(local_config[k], remote_config[k])])

        if self.params['publish'] and remote_function['Version'] == '$LATEST':
            # force code update (and publishing) since version found is $LATEST
            code_changed = True

        if self.params['publish'] and config_changed and not code_changed:
            # force code update (and publishing) since updating config alone doesn't support publishing
            code_changed = True

        if self.params['publish'] and remote_function['Version'] != '$LATEST' and (code_changed or config_changed):
            # when publishing changes we must update config and code since we can only publish from latest
            code_changed = True
            config_changed = True

        config = self.update_function_configuration(local_config, config_changed)
        code = self.update_function_code(code_changed)

        data = {}
        data.update(remote_function)
        data.update(config)
        data.update(code)

        result = self.make_result(data)

        if code_changed or config_changed:
            return None, True, result

        return None, False, result

    def are_equal(self, first, second):
        if isinstance(first, dict):
            if not isinstance(second, dict):
                return False

            for key in set(first) | set(second):
                if key not in first or key not in second:
                    return False

                if not self.are_equal(first[key], second[key]):
                    return False

        return first == second

    def update_function_configuration(self, args, changed):
        if changed and not self.check_mode:
            if not args['Layers']:
                del args['Layers']

            if not args['Environment']:
                del args['Environment']

            return self.al.update_function_configuration(**args)

        return args

    def update_function_code(self, changed):
        args = self.make_function_code()
        args['FunctionName'] = self.params['function_name']
        args['Publish'] = self.params['publish']

        if changed and not self.check_mode:
            return self.al.update_function_code(**args)

        return args

    def make_result(self, data):
        result = dict(
            function_name=data['FunctionName'],
            runtime=data['Runtime'],
            role=data['Role'],
            handler=data['Handler'],
            description=data['Description'],
            timeout=data['Timeout'],
            memory_size=data['MemorySize'],
            environment=(data.get('Environment') or {}).get('Variables') or {},
            layers=data.get('Layers'),
        )

        if 'CodeSha256' in data:
            more = dict(
                function_arn=data['FunctionArn'],
                code_size=data['CodeSize'],
                last_modified=data['LastModified'],
                code_sha_256=data['CodeSha256'],
                version=data['Version'],
                # VpcConfig not handled
            )

            result.update(more)

        return result

    def make_function_configuration(self):
        args = {
            'FunctionName': self.params['function_name'],
            'Runtime': self.params['runtime'],
            'Role': self.params['role'],
            'Handler': self.params['handler'],
            'Description': self.params['description'],
            'Timeout': self.params['timeout'],
            'MemorySize': self.params['memory_size'],
            'Environment': None,
            'Layers': self.params['layers'],
            # VpcConfig not implemented
        }

        if self.params['environment']:
            args['Environment'] = {
                'Variables': self.params['environment'],
            }

        return args

    def make_function_code(self):
        if self.params['s3_bucket'] is not None:
            return {
                'S3Bucket': self.params['s3_bucket'],
                'S3Key': self.params['s3_key'],
                'S3ObjectVersion': self.params['s3_object_version'],
            }

        return {
            'ZipFile': self.get_package(),
        }


if __name__ == '__main__':
    main()
