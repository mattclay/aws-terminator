"""Tests for cleanup.py config loading."""

import os
import tempfile

# Import only the config loader — no boto3/terminator side effects needed
from cleanup import load_config


def test_load_config_renders_templates():
    """Verify that Jinja2 templates in config are resolved against sibling values."""
    config = load_config(os.path.join(os.path.dirname(__file__), 'config.yml'))

    # ssm_bucket_name should have {{ test_account_id }} resolved
    assert '{{' not in config['ssm_bucket_name'], \
        f"Unresolved template in ssm_bucket_name: {config['ssm_bucket_name']}"
    assert config['ssm_bucket_name'] == f"ssm-encrypted-test-bucket-{config['test_account_id']}"


def test_load_config_preserves_plain_values():
    """Verify that non-templated values pass through unchanged."""
    config = load_config(os.path.join(os.path.dirname(__file__), 'config.yml'))

    assert config['test_account_id'] == '208851973884'
    assert config['api_name'] == 'ansible-core-ci'
    assert config['aws_region'] == 'eu-west-1'


def test_load_config_with_synthetic_file():
    """Verify rendering works for an arbitrary config with cross-references."""
    raw = (
        "account: '12345'\n"
        "bucket: 'my-bucket-{{ account }}'\n"
    )
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(raw)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)
    assert config['bucket'] == 'my-bucket-12345'


if __name__ == '__main__':
    test_load_config_renders_templates()
    test_load_config_preserves_plain_values()
    test_load_config_with_synthetic_file()
    print('All tests passed.')
