from __future__ import annotations

from ansible.plugins.lookup import LookupBase


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        import boto3  # pylint: disable=import-outside-toplevel

        return [boto3.session.Session().region_name]
