#!/usr/bin/python
# Copyright (C) 2016 Matt Clay <matt@mystile.com>
# GNU General Public License v3.0+ (see ansible/LICENSE.md or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

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
    ec2_argument_spec,
    get_aws_connection_info,
    HAS_BOTO3,
)


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        rule_name=dict(required=True, type='str'),
        function_name=dict(required=True, type='str'),
        schedule_expression=dict(required=True, type='str'),
        description=dict(required=False, default='', type='str'),
        state=dict(required=False, default='enabled', type='str', choices=['enabled', 'disabled', 'absent']),
    ))

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    em = EventsModule(module, module.check_mode, module.params)

    error, changed, result = em.run()

    if error is None:
        module.exit_json(changed=changed, meta=result)
    else:
        module.fail_json(msg=error, meta=result)


class EventsModule:
    def __init__(self, module, check_mode, params):
        self.module = module
        self.check_mode = check_mode
        self.params = params
        self.events = None
        self.iam = None
        self.account_id = None

    def run(self):
        if not HAS_BOTO3:
            return 'the boto3 python module is required to use this module', None, None

        region, ec2_url, aws_connect_kwargs = get_aws_connection_info(self.module, boto3=True)

        self.events = boto3_conn(self.module, conn_type='client', resource='events', region=region, endpoint=ec2_url,
                                 **aws_connect_kwargs)

        self.iam = boto3_conn(self.module, conn_type='resource', resource='iam', region=region, endpoint=ec2_url,
                              **aws_connect_kwargs)

        self.account_id = self.iam.CurrentUser().arn.split(':')[4]

        if not self.params['function_name'].startswith('arn:aws:iam:'):
            self.params['function_name'] = 'arn:aws:lambda:%s:%s:function:%s' % (region, self.account_id, self.params['function_name'])

        choice_map = dict(
            enabled=self.function_present,
            disabled=self.function_present,
            absent=self.function_absent,
        )

        return choice_map.get(self.params['state'])()

    def function_present(self):
        remote_rule = self.get_rule()

        if remote_rule is None:
            return self.put_rule()

        return self.put_rule(remote_rule)

    def function_absent(self):
        raise Exception('FIXME: not implemented')

    def get_rule(self):
        try:
            return self.events.describe_rule(Name=self.params['rule_name'])
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] == 'ResourceNotFoundException':
                return None
            raise

    def put_rule(self, remote_rule=None):
        local_rule = dict(
            Name=self.params['rule_name'],
            ScheduleExpression=self.params['schedule_expression'],
            State=self.params['state'].upper(),
            Description=self.params['description'],
        )

        data = {}

        if remote_rule is None:
            rule_changed = True
            target_changed = True
        else:
            rule_changed = any([k for k in local_rule if local_rule[k] != remote_rule.get(k, '')])
            targets = self.events.list_targets_by_rule(Rule=self.params['rule_name'])['Targets']
            targets = [t for t in targets if t['Arn'] == self.params['function_name']]
            target_changed = not bool(targets)
            data.update(remote_rule)

        data.update(local_rule)

        if rule_changed and not self.check_mode:
            self.events.put_rule(**local_rule)

        if target_changed and not self.check_mode:
            self.events.put_targets(
                Rule=self.params['rule_name'],
                Targets=[
                    dict(
                        Id=str(uuid.uuid4()),
                        Arn=self.params['function_name'],
                    ),
                ],
            )

        results = dict(
            rule_name=data['Name'],
            schedule_expression=data['ScheduleExpression'],
            state=data['State'].lower(),
            description=data['Description'],
        )

        if 'Arn' in data:
            more = dict(
                rule_arn=data['Arn'],
            )

            results.update(more)

        if rule_changed or target_changed:
            return None, True, results

        return None, False, results


if __name__ == '__main__':
    main()
