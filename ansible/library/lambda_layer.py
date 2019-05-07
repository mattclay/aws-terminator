#!/usr/bin/python
# Copyright (C) 2019 Matt Clay <matt@mystile.com>
# GNU General Public License v3.0+ (see ansible/LICENSE.md or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

import base64
import hashlib
import datetime

from ansible.module_utils.basic import (
    AnsibleModule,
)

from ansible.module_utils.common.dict_transformations import (
    camel_dict_to_snake_dict,
)

from ansible.module_utils.ec2 import (
    boto3_conn,
    ec2_argument_spec,
    get_aws_connection_info,
)


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        name=dict(type='str', required=True),
        description=dict(type='str'),
        compatible_runtimes=dict(type='list'),
        path=dict(type='path', required=True),
        license_info=dict(type='str'),
        state=dict(default='present', type='str', choices=['present', 'absent']),
    ))

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    impl = LambdaLayerModule(module, module.check_mode, module.params)
    module.exit_json(**impl.run())


class LambdaLayerModule:
    def __init__(self, module, check_mode, params):
        self.module = module
        self.check_mode = check_mode
        self.zip_file = None
        self.lambda_client = None

        self.name = params['name']
        self.description = params['description']
        self.state = params['state']
        self.compatible_runtimes = params['compatible_runtimes']
        self.license_info = params['license_info']
        self.path = params['path']

    def run(self):
        self.lambda_client = LambdaClient(self.module)

        choice_map = dict(
            present=self.layer_present,
            absent=self.layer_absent,
        )

        return choice_map.get(self.state)()

    def layer_present(self):
        latest_layer_version = {}
        version_numbers_to_delete = []

        for layer_version in self.lambda_client.enumerate_layer_versions(self.name):
            version_numbers_to_delete.append(layer_version['Version'])

            if not latest_layer_version or layer_version['Version'] > latest_layer_version['Version']:
                latest_layer_version = layer_version

        if latest_layer_version:
            layer_version = self.lambda_client.get_layer_version(self.name, latest_layer_version['Version'])

            local_hash = self.get_zip_file_hash()
            remote_hash = layer_version['Content']['CodeSha256']

            if local_hash == remote_hash:  # probably should compare more than just the hash
                return self.make_result(False, layer_version)

        if self.check_mode:
            if latest_layer_version:
                account_id = latest_layer_version['LayerVersionArn'].split(':')[4]
                version = latest_layer_version['Version'] + 1
            else:
                account_id = '0'  # this could be retrieved for a more accurate result in check mode
                version = 1

            layer_arn = "arn:aws:lambda:%s:%s:layer:%s" % (self.lambda_client.region, account_id, self.name)
            layer_version_arn = "%s:%d" % (layer_arn, version)

            layer_version = dict(
                Content=dict(
                    Location=None,
                    CodeSha256=self.get_zip_file_hash(),
                    CodeSize=len(self.get_zip_file()),
                ),
                LayerArn=layer_arn,
                LayerVersionArn=layer_version_arn,
                Description=self.description,
                CreatedDate=datetime.datetime.utcnow().isoformat(),  # close, but not exact, AWS returns "2019-03-30T08:52:06.009+0000"
                Version=version,
                CompatibleRuntimes=self.compatible_runtimes,
                LicenseInfo=self.license_info,
            )
        else:
            content = self.get_layer_content()

            layer_version = self.lambda_client.publish_layer_version(self.name, content, self.description, self.compatible_runtimes, self.license_info)

            for version_number_to_delete in version_numbers_to_delete:
                self.lambda_client.delete_layer_version(self.name, version_number_to_delete)

        return self.make_result(True, layer_version)

    def layer_absent(self):
        changed = False

        for layer_version in self.lambda_client.enumerate_layer_versions(self.name):
            changed = True

            if not self.check_mode:
                self.lambda_client.delete_layer_version(self.name, layer_version['Version'])

        return self.make_result(changed, {})

    def make_result(self, changed, layer_version):
        """
        :type changed: bool
        :type layer_version: dict[str, any]
        :rtype: bool, dict[str, any]
        """
        result = dict(
            changed=changed,
        )

        if layer_version:
            if 'ResponseMetadata' in layer_version:
                del layer_version['ResponseMetadata']

            content = layer_version.get('Content')

            if content:
                if 'Location' in content:
                    del content['Location']

            layer = camel_dict_to_snake_dict(layer_version)

            result.update(dict(
                layer=layer,
            ))

        return result

    def get_layer_content(self):
        return dict(
            ZipFile=self.get_zip_file(),
        )

    def get_zip_file_hash(self):
        return base64.b64encode(hashlib.sha256(self.get_zip_file()).digest()).decode('ascii')

    def get_zip_file(self):
        if not self.zip_file:
            with open(self.path, 'rb') as f:
                self.zip_file = f.read()

        return self.zip_file


class LambdaClient(object):
    def __init__(self, module):
        region, endpoint, boto_params = get_aws_connection_info(module, boto3=True)

        self.client = boto3_conn(module, conn_type='client', resource='lambda', region=region, endpoint=endpoint, **boto_params)
        self.region = region

    def publish_layer_version(self, layer_name, content, description, compatible_runtimes, license_info):
        """
        :type layer_name: str
        :type content: dict[str, any]
        :type description: str | None
        :type compatible_runtimes: List[str] | None
        :type license_info: str | None
        :rtype: dict[str, any]
        """
        response = self.client.publish_layer_version(
            LayerName=layer_name,
            Content=content,
            Description=description,
            CompatibleRuntimes=compatible_runtimes,
            LicenseInfo=license_info,
        )

        return response

    def delete_layer_version(self, layer_name, version_number):
        """
        :type layer_name: str
        :type version_number: int
        """
        self.client.delete_layer_version(
            LayerName=layer_name,
            VersionNumber=version_number,
        )

    def get_layer_version(self, layer_name, version_number):
        """
        :type layer_name: str
        :type version_number: int
        :rtype: dict[str, any]
        """
        layer_version = self.client.get_layer_version(
            LayerName=layer_name,
            VersionNumber=version_number,
        )

        return layer_version

    def enumerate_layer_versions(self, layer_name):
        """
        :type layer_name: str
        :rtype: Iterable[dict[str, any]]
        """
        marker = None

        while True:
            request = dict(
                LayerName=layer_name,
            )

            if marker:
                request.update(dict(
                    Marker=marker,
                ))

            response = self.client.list_layer_versions(**request)

            marker = response.get('NextMarker')

            for layer_version in response['LayerVersions']:
                yield layer_version

            if not marker:
                break


if __name__ == '__main__':
    main()
