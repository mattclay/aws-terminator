#!/usr/bin/python
# Copyright (C) 2019 Matt Clay <matt@mystile.com>
# GNU General Public License v3.0+ (see ansible/LICENSE.md or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

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


def main():
    argument_spec = dict(
        src=dict(type='path', required=True),
        dest=dict(type='path', required=True),
        include=dict(type='list'),
        exclude=dict(type='list'),
        rename=dict(type='dict'),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    impl = LambdaPackageModule(module, module.check_mode, module.params)
    module.exit_json(**impl.run())


class LambdaPackageModule:
    def __init__(self, module, check_mode, params):
        self.module = module
        self.check_mode = check_mode
        self.src = params['src']
        self.dest = params['dest']
        self.include = params['include']
        self.exclude = params['exclude']
        self.rename = params['rename'] or {}

    def run(self):
        try:
            with open(self.dest, 'rb') as f:
                current_package = f.read()
        except IOError as ex:
            if ex.errno != errno.ENOENT:
                raise

            current_package = None

        new_package = self.create_package()

        changed = current_package != new_package

        if changed and not self.check_mode:
            with open(self.dest, 'wb') as f:
                f.write(new_package)

        result = dict(
            changed=changed,
            package=dict(
                size=len(new_package),
            )
        )

        return result

    def create_package(self):
        data = BytesIO()

        with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, _dummy, filenames in os.walk(self.src):
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

                    zip_info = zipfile.ZipInfo(
                        dst_path,
                        (1980, 1, 1, 0, 0, 0),  # deterministic timestamp for idempotency
                    )

                    zip_info.compress_type = zipfile.ZIP_DEFLATED
                    zip_info.external_attr = 0o777 << 16  # give full access to included file

                    with open(src_path, 'rb') as src_file:
                        zip_file.writestr(zip_info, src_file.read())

        return data.getvalue()


if __name__ == '__main__':
    main()
