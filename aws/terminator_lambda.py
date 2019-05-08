import logging
import os

from terminator import (
    cleanup,
    logger,
)


# noinspection PyUnusedLocal
def lambda_handler(event, context):
    # pylint: disable=unused-argument
    logger.setLevel(logging.INFO)

    arn = context.invoked_function_arn.split(':')

    if len(arn) == 7:
        arn.append('prod')  # hack to set the stage for testing in the lambda console

    if len(arn) != 8 or arn[5] != 'function' or arn[6] != context.function_name:
        raise Exception(f'error: unexpected arn: {arn}')

    stage = arn[7]

    api_name = os.environ['API_NAME']
    test_account_id = os.environ['TEST_ACCOUNT_ID']

    cleanup(stage, check=False, force=False, api_name=api_name, test_account_id=test_account_id)
