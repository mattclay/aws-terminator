#!/usr/bin/python
# Copyright (C) 2019 Matt Clay <matt@mystile.com>
# GNU General Public License v3.0+ (see LICENSE.md or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
---
module: terminator_lambda_package
short_description: Package files in a ZIP archive for deployment as Lambda functions
description:
    - Package files in a ZIP archive for deployment as Lambda functions.
author:
    - Matt Clay (@mattclay) <matt@mystile.com>
options:
    src:
        description:
            - Path to the source files to package.
        type: path
        required: true
    dest:
        description:
            - Path to the package that should be created.
        type: path
        required: true
    include:
        description:
            - A list of patterns to include in the package.
        type: list
        elements: str
    exclude:
        description:
            - A list of patterns to exclude from the package.
        type: list
        elements: str
    rename:
        description:
            - Mapping of files that should be renamed in the package.
        type: dict
        default: {}
'''

EXAMPLES = '''
terminator_lambda_package:
    src: my_lambda_functions
    dest: my_lambda_functions.zip
    include:
        - "my_lambda_functions/*.py"
        - "my_lambda_functions/data/*.json"
'''

import errno
import os
import zipfile
import fnmatch

from ansible.module_utils.six import (
    BytesIO,
)

from ansible.module_utils.basic import (
    AnsibleModule,
)


class TerminatorLambdaPackage:
    def __init__(self, module):
        self.module = module
        self.check_mode = module.check_mode
        self.src = module.params['src']
        self.dest = module.params['dest']
        self.include = module.params['include']
        self.exclude = module.params['exclude']
        self.rename = module.params['rename']

    def run(self):
        try:
            with open(self.dest, 'rb') as f:
                current_package = f.read()
        except IOError as ex:
            if ex.errno != errno.ENOENT:
                raise

            current_package = None

        new_package, paths = self.create_package()

        changed = current_package != new_package

        if changed and not self.check_mode:
            with open(self.dest, 'wb') as f:
                f.write(new_package)

        result = dict(
            changed=changed,
            package=dict(
                size=len(new_package),
            ),
            files=[src_path for dst_path, src_path in paths]
        )

        return result

    def create_package(self):
        paths = []

        for root, _ignored, filenames in os.walk(self.src):
            for filename in filenames:
                src_path = os.path.join(root, filename)
                dst_path = os.path.relpath(src_path, self.src)

                if self.include:
                    if not any(fnmatch.fnmatch(src_path, pattern) for pattern in self.include):
                        continue

                if self.exclude:
                    if any(fnmatch.fnmatch(src_path, pattern) for pattern in self.exclude):
                        continue

                dst_path = self.rename.get(dst_path, dst_path)

                paths.append((dst_path, src_path))

        paths = sorted(paths)
        data = BytesIO()

        with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for dst_path, src_path in paths:
                zip_info = zipfile.ZipInfo(
                    dst_path,
                    (1980, 1, 1, 0, 0, 0),  # deterministic timestamp for idempotency
                )

                zip_info.compress_type = zipfile.ZIP_DEFLATED
                zip_info.external_attr = 0o777 << 16  # give full access to included file

                with open(src_path, 'rb') as src_file:
                    zip_file.writestr(zip_info, src_file.read())

        return data.getvalue(), paths


def main():
    argument_spec = dict(
        src=dict(type='path', required=True),
        dest=dict(type='path', required=True),
        include=dict(type='list', elements='str'),
        exclude=dict(type='list', elements='str'),
        rename=dict(type='dict', default={}),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    impl = TerminatorLambdaPackage(module)
    module.exit_json(**impl.run())

if __name__ == '__main__':
    main()
