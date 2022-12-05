#!/usr/bin/python
# This file is part of Ansible
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


DOCUMENTATION = '''
---
module: terminator_compare_archives
short_description: Compare Zip files
description:
    - Extract archives on temporary directories and create new archives with a deterministic timestamp
      and assert that the resulting checksum if the same for both archives
options:
  zipfile_1:
    description:
      - Path to the first zip file.
    required: true
    type: path
  zipfile_2:
    description:
      - Path to a second zip file.
    type: path
    required: true
author:
    - "Aubin Bikouo (@abikouo)"
'''

EXAMPLES = '''
- name: Compare files from an archive with a local directory
  terminator_compare_archives:
    zipfile_1: archive.zip
    zipfile_2: another_archive.zip
'''

RETURN = '''
equals:
  description: Returns true if all files from archive are located in the directory with the same content
  returned: always
  type: bool
checksum_1:
  description: Deterministic checksum of the first zip file
  returned: always
  type: str
  sample: rwAY/nvkdHpZqLMyMNbh/GU3AE3SpR3eUOXU8ZgU2kw=
checksum_2:
  description: Deterministic checksum of the second zip file
  returned: always
  type: str
  sample: rwAY/nvkdUEIJDNFJGKFNGU3AE3SpR3eUOXU8ZgU2kw=
len_1:
  description: Length of the first zip file
  returned: always
  type: str
  sample: 95648213
len_2:
  description: Length of the second zip file
  returned: always
  type: str
  sample: 95648000
'''

import zipfile
import os
import tempfile
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import BytesIO
import base64
import hashlib


class TerminatorZipFileCompare(AnsibleModule):

    def __init__(self):

        argument_spec = {
            "zipfile_1": {"type": "path", "required": True},
            "zipfile_2": {"type": "path", "required": True},
        }

        super(TerminatorZipFileCompare, self).__init__(argument_spec=argument_spec)
        self.execute()

    def get_checksum_for_deterministic_archive(self, path):
        with tempfile.TemporaryDirectory() as tmpdirname:
            with zipfile.ZipFile(path) as zip_r:
                zip_r.extractall(path=tmpdirname)
                paths = []
                for root, dirs, files in os.walk(tmpdirname):
                    for name in files:
                        paths.append(os.path.join(root, name))

                paths = sorted(paths)
                data = BytesIO()

                with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as zip_w:
                  for src_path in paths:
                      dst_path = os.path.relpath(tmpdirname, src_path)
                      zip_info = zipfile.ZipInfo(
                          dst_path,
                          (1980, 1, 1, 0, 0, 0),  # deterministic timestamp for idempotency
                      )

                      zip_info.compress_type = zipfile.ZIP_DEFLATED
                      zip_info.external_attr = 0o777 << 16  # give full access to included file

                      with open(src_path, 'rb') as src_file:
                          zip_w.writestr(zip_info, src_file.read())

                checksum = base64.b64encode(hashlib.sha256(data.getvalue()).digest()).decode('ascii')
                return checksum, len(data.getvalue())

    def execute(self):
        try:

            checksum_1, len_1 = self.get_checksum_for_deterministic_archive(self.params.get("zipfile_1"))
            checksum_2, len_2 = self.get_checksum_for_deterministic_archive(self.params.get("zipfile_2"))

            self.exit_json(
                equals=(checksum_1 == checksum_2 and len_1 == len_2),
                checksum_1=checksum_1,
                checksum_2=checksum_2,
                len_1=len_1,
                len_2=len_2
            )

        except Exception as exc:
            self.fail_json(msg="Module execution failed due to: {0}".format(exc))

def main():
    TerminatorZipFileCompare()


if __name__ == "__main__":
    main()
