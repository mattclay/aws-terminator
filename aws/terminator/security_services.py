import abc
import datetime

import botocore
import botocore.exceptions

from . import DbTerminator, Terminator


class IamRole(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, IamRole, 'iam', lambda client: client.list_roles()['Roles'])

    @property
    def id(self):
        return self.instance['RoleId']

    @property
    def name(self):
        return self.instance['RoleName']

    @property
    def ignore(self):
        return not self.name.startswith('ansible-test')

    @property
    def created_time(self):
        return self.instance['CreateDate']

    def terminate(self):
        try:
            self.client.delete_role(RoleName=self.name)
            return
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] != 'DeleteConflict':
                raise

        for policy in self.client.list_attached_role_policies(RoleName=self.name)['AttachedPolicies']:
            self.client.detach_role_policy(RoleName=self.name, PolicyArn=policy['PolicyArn'])

        self.client.delete_role(RoleName=self.name)


class IamInstanceProfile(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, IamInstanceProfile, 'iam', lambda client: client.list_instance_profiles()['InstanceProfiles'])

    @property
    def id(self):
        return self.instance['InstanceProfileId']

    @property
    def name(self):
        return self.instance['InstanceProfileName']

    @property
    def ignore(self):
        return not self.name.startswith('ansible-test-')

    @property
    def created_time(self):
        return self.instance['CreateDate']

    def terminate(self):
        for role in self.instance['Roles']:
            self.client.remove_role_from_instance_profile(InstanceProfileName=self.name, RoleName=role['RoleName'])

        self.client.delete_instance_profile(InstanceProfileName=self.name)


class Waf(DbTerminator):
    @property
    def age_limit(self):
        return datetime.timedelta(minutes=20)

    @property
    def change_token(self):
        return self.client.get_change_token()['ChangeToken']

    @property
    def name(self):
        return self.instance['Name']

    @abc.abstractmethod
    def terminate(self):
        """Terminate or delete the AWS resource."""


class WafWebAcl(Waf):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, WafWebAcl, 'waf', lambda client: client.list_web_acls()['WebACLs'])

    @property
    def age_limit(self):
        # Try to delete WafWebAcl first, because WafRule objects cannot be deleted if used in any WebACL
        return datetime.timedelta(minutes=10)

    @property
    def id(self):
        return self.instance['WebACLId']

    def terminate(self):
        updates = [{'Action': 'DELETE', 'ActivatedRule': i} for i in
                   self.client.get_web_acl(WebACLId=self.id)['WebACL']['Rules']]
        if updates:
            self.client.update_web_acl(WebACLId=self.id, ChangeToken=self.change_token, Updates=updates)
        self.client.delete_web_acl(WebACLId=self.id, ChangeToken=self.change_token)


class WafRule(Waf):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, WafRule, 'waf', lambda client: client.list_rules()['Rules'])

    @property
    def id(self):
        return self.instance['RuleId']

    def terminate(self):
        updates = [{'Action': 'DELETE', 'Predicates': i} for i in
                   self.client.get_rule(RuleId=self.id)['Rule']['Predicates']]
        if updates:
            self.client.update_rule(WebACLId=self.id, ChangeToken=self.change_token, Updates=updates)
        self.client.delete_rule(RuleId=self.id, ChangeToken=self.change_token)


class WafXssMatchSet(Waf):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, WafXssMatchSet, 'waf', lambda client: client.list_xss_match_sets()['XssMatchSets'])

    @property
    def id(self):
        return self.instance['XssMatchSetId']

    def terminate(self):
        updates = [{'Action': 'DELETE', 'XssMatchTuple': i} for i in
                   self.client.get_xss_match_set(XssMatchSetId=self.id)['XssMatchSet']['XssMatchTuples']]
        if updates:
            self.client.update_xss_match_set(XssMatchSetId=self.id, ChangeToken=self.change_token, Updates=updates)
        self.client.delete_xss_match_set(XssMatchSetId=self.id, ChangeToken=self.change_token)


class WafGeoMatchSet(Waf):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, WafGeoMatchSet, 'waf', lambda client: client.list_geo_match_sets()['GeoMatchSets'])

    @property
    def id(self):
        return self.instance['GeoMatchSetId']

    def terminate(self):
        updates = [{'Action': 'DELETE', 'GeoMatchConstraint': i} for i in
                   self.client.get_geo_match_set(GeoMatchSetId=self.id)['GeoMatchSet']['GeoMatchConstraints']]
        if updates:
            self.client.update_geo_match_set(GeoMatchSetId=self.id, ChangeToken=self.change_token, Updates=updates)
        self.client.delete_geo_match_set(GeoMatchSetId=self.id, ChangeToken=self.change_token)


class WafSqlInjectionMatchSet(Waf):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, WafSqlInjectionMatchSet, 'waf', lambda client: client.list_sql_injection_match_sets()['SqlInjectionMatchSets'])

    @property
    def id(self):
        return self.instance['SqlInjectionMatchSetId']

    def terminate(self):
        updates = [{'Action': 'DELETE', 'SqlInjectionMatchTuple': i} for i in
                   self.client.get_sql_injection_match_set(SqlInjectionMatchSetId=self.id)['SqlInjectionMatchSet']['SqlInjectionMatchTuples']]
        if updates:
            self.client.update_sql_injection_match_set(SqlInjectionMatchSetId=self.id, ChangeToken=self.change_token, Updates=updates)
        self.client.delete_sql_injection_match_set(SqlInjectionMatchSetId=self.id, ChangeToken=self.change_token)


class WafIpSet(Waf):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, WafIpSet, 'waf', lambda client: client.list_ip_sets()['IPSets'])

    @property
    def id(self):
        return self.instance['IPSetId']

    def terminate(self):
        updates = [{'Action': 'DELETE', 'IPSetDescriptor': i} for i in
                   self.client.get_ip_set(IPSetId=self.id)['IPSet']['IPSetDescriptors']]
        if updates:
            self.client.update_ip_set(IPSetId=self.id, ChangeToken=self.change_token, Updates=updates)
        self.client.delete_ip_set(IPSetId=self.id, ChangeToken=self.change_token)


class WafSizeConstraintSet(Waf):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, WafSizeConstraintSet, 'waf', lambda client: client.list_size_constraint_sets()['SizeConstraintSets'])

    @property
    def id(self):
        return self.instance['SizeConstraintSetId']

    def terminate(self):
        updates = [{'Action': 'DELETE', 'SizeConstraint': i} for i in
                   self.client.get_size_constraint_set(SizeConstraintSetId=self.id)['SizeConstraintSet']['SizeConstraints']]
        if updates:
            self.client.update_size_constraint_set(SizeConstraintSetId=self.id, ChangeToken=self.change_token, Updates=updates)
        self.client.delete_size_constraint_set(SizeConstraintSetId=self.id, ChangeToken=self.change_token)


class WafByteMatchSet(Waf):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, WafByteMatchSet, 'waf', lambda client: client.list_byte_match_sets()['ByteMatchSets'])

    @property
    def id(self):
        return self.instance['ByteMatchSetId']

    def terminate(self):
        updates = [{'Action': 'DELETE', 'ByteMatchTuple': i} for i in
                   self.client.get_byte_match_set(ByteMatchSetId=self.id)['ByteMatchSet']['ByteMatchTuples']]
        if updates:
            self.client.update_byte_match_set(ByteMatchSetId=self.id, ChangeToken=self.change_token, Updates=updates)
        self.client.delete_byte_match_set(ByteMatchSetId=self.id, ChangeToken=self.change_token)


class WafRegexMatchSet(Waf):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, WafRegexMatchSet, 'waf', lambda client: client.list_regex_match_sets()['RegexMatchSets'])

    @property
    def id(self):
        return self.instance['RegexMatchSetId']

    def terminate(self):
        updates = [{'Action': 'DELETE', 'RegexMatchTuple': i} for i in
                   self.client.get_regex_match_set(RegexMatchSetId=self.id)['RegexMatchSet']['RegexMatchTuples']]
        if updates:
            self.client.update_regex_match_set(RegexMatchSetId=self.id, ChangeToken=self.change_token, Updates=updates)
        self.client.delete_regex_match_set(RegexMatchSetId=self.id, ChangeToken=self.change_token)


class WafRegexPatternSet(Waf):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, WafRegexPatternSet, 'waf', lambda client: client.list_regex_pattern_sets()['RegexPatternSets'])

    @property
    def id(self):
        return self.instance['RegexPatternSetId']

    def terminate(self):
        updates = [{'Action': 'DELETE', 'RegexPatternString': i} for i in
                   self.client.get_regex_pattern_set(RegexPatternSetId=self.id)['RegexPatternSet']['RegexPatternStrings']]
        if updates:
            self.client.update_regex_pattern_set(RegexPatternSetId=self.id, ChangeToken=self.change_token, Updates=updates)
        self.client.delete_regex_pattern_set(RegexPatternSetId=self.id, ChangeToken=self.change_token)


class InspectorAssessmentTemplate(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(
            credentials, InspectorAssessmentTemplate, 'inspector',
            lambda client: client.get_paginator('list_assessment_templates').paginate().build_full_result()['assessmentTemplateArns']
        )

    @property
    def id(self):
        return self.instance

    @property
    def name(self):
        return self.instance

    def terminate(self):
        self.client.delete_assessment_template(assessmentTemplateArn=self.id)


class InspectorAssessmentTarget(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(
            credentials, InspectorAssessmentTarget, 'inspector',
            lambda client: client.get_paginator('list_assessment_targets').paginate().build_full_result()['assessmentTargetArns']
        )

    @property
    def id(self):
        return self.instance

    @property
    def name(self):
        return self.instance

    def terminate(self):
        self.client.delete_assessment_target(assessmentTargetArn=self.id)


class ACMCertificate(DbTerminator):
    # ACM provides a created time, but there are cases where describe_certificate can fail
    # We need to be able to delete anyway, so use DbTerminator
    # https://github.com/ansible/ansible/issues/67788
    @staticmethod
    def create(credentials):
        return Terminator._create(
            credentials, ACMCertificate, 'acm',
            lambda client: client.get_paginator('list_certificates').paginate().build_full_result()['CertificateSummaryList']
        )

    @property
    def id(self):
        return self.instance['CertificateArn']

    @property
    def name(self):
        return self.instance['CertificateArn']

    def terminate(self):
        self.client.delete_certificate(CertificateArn=self.id)
