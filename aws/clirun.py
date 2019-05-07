"""
a simple front end for to terminator for checking in isolation.
"""
import click
import logging
import boto3

from terminator import (
    cleanup, get_concrete_subclasses, kvs, Terminator, process_instance)

log = logging.getLogger('aws-terminator')


@click.group()
@click.option('--verbose', is_flag=True, default=False)
def cli(verbose):
    """aws terminator cli
    """
    logging.basicConfig(level=verbose and logging.DEBUG or logging.INFO)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


@cli.command(name='run')
@click.option('--terminator', help='Which resource terminator to use')
@click.option('--table', default='Terminator', help='dynamodb table')
@click.option('--check', is_flag=True, default=False, help="dont delete")
@click.option('--force', is_flag=True, default=False)
def cli_run(terminator, table, check, force):
    """Run a single resource type's terminator
    """
    found = None
    avail = set()
    for klass in get_concrete_subclasses(Terminator):
        if klass.__name__ == terminator:
            found = klass
            break
        avail.add(klass.__name__)
    if not found:
        print("No Terminator named %s\n Available: %s" % (
            terminator, ", ".join(sorted(avail))))
        return

    kvs.domain_name = table or terminator
    log.info("Initializing Db")
    kvs.initialize()

    # will source from env vars
    s = boto3.Session()

    # will scan/describe / create classes and insert instances
    instances = klass.create(s)
    log.info("Found %d resources of %s", len(instances), klass.__name__)

    for i in instances:
        status = process_instance(i, check, force)
        log.info("%s %s", i.name, status)


@cli.command(name='cleanup')
@click.option('--api-name', required=True)
@click.option('--stage', required=True)
@click.option('--force', is_flag=True, default=False)
@click.option('--check', is_flag=True, default=False)
def cli_cleanup(stage, api_name, check, force):
    """Run the full cleanup in the same manner as the lambda."""
    account_id = boto3.client('sts').get_caller_identity().get('AccountId')
    cleanup(stage=stage, check=check, api_name=api_name,
            test_account_id=account_id)


if __name__ == '__main__':
    cli()
