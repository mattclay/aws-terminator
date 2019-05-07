#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
"""Terminate or destroy stale resources in the AWS test account."""

import argparse
import logging
import os
import yaml

import boto3

try:
    import argcomplete
except ImportError:
    argcomplete = None

from terminator import (
    cleanup,
    get_concrete_subclasses,
    logger,
    Terminator,
    get_regions,
)


def main():
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    logger.addHandler(console)

    args = parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    base_path = os.path.dirname(__file__)
    config_path = os.path.join(base_path, 'config.yml')

    def default_ctor(_dummy, tag_suffix, node):
        return tag_suffix + ' ' + node.value

    yaml.add_multi_constructor('', default_ctor)

    with open(config_path) as config_fd:
        config = yaml.load(config_fd, Loader=yaml.BaseLoader)

    test_account_id = config['test_account_id']
    api_name = config['api_name']

    account_id = boto3.client('sts').get_caller_identity().get('Account')

    if account_id != config['lambda_account_id']:
        exit(f'The terminator must be run from the lambda account: {config["lambda_account_id"]}')

    if args.region in ('all', 'a'):
        aws_regions = get_regions()
    else:
        aws_regions = [args.region]
    for region in aws_regions:
        cleanup(args.stage, check=args.check, force=args.force, api_name=api_name, test_account_id=test_account_id, targets=args.target, region=region)


def parse_args():
    parser = argparse.ArgumentParser(description='Terminate or destroy stale resources in the AWS test account.')

    parser.add_argument('-r', '--region',
                        default='us-east-1',
                        help='regions to cleanup')

    parser.add_argument('-c', '--check',
                        action='store_true',
                        help='do not terminate resources')

    parser.add_argument('-f', '--force',
                        action='store_true',
                        help='do not skip unsupported or stale resources')

    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        help='increase logging verbosity')

    parser.add_argument('--stage',
                        choices=['prod', 'dev'],
                        required=True,
                        help='stage to use for database and policy access')

    parser.add_argument('--target',
                        choices=sorted([value.__name__ for value in get_concrete_subclasses(Terminator)] + ['Database']),
                        metavar='target',
                        action='append',
                        help='class to run')

    if argcomplete:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()

    return args


if __name__ == '__main__':
    main()
