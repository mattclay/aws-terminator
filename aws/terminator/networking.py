import datetime

from . import DbTerminator, Terminator, get_tag_dict_from_tag_list


class Route53HostedZone(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Route53HostedZone, 'route53', lambda client: client.list_hosted_zones()['HostedZones'])

    @property
    def id(self):
        return self.instance['Id']

    @property
    def name(self):
        return self.instance['Name']

    def terminate(self):
        # remove any record sets that the zone contains
        record_sets = self.client.list_resource_record_sets(HostedZoneId=self.id)['ResourceRecordSets']
        remove_record_sets = [record_set for record_set in record_sets if record_set['Type'] not in ('SOA', 'NS')]
        if remove_record_sets:
            # Public hosted zones always contain an NS and SOA record, just try to remove the others
            self.client.change_resource_record_sets(
                HostedZoneId=self.id,
                ChangeBatch={
                    'Comment': 'Remove record sets',
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': record_set
                    } for record_set in remove_record_sets]
                }
            )
        self.client.delete_hosted_zone(Id=self.id)


class Ec2Eip(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2Eip, 'ec2', lambda client: client.describe_addresses()['Addresses'])

    @property
    def id(self):
        return self.instance['AllocationId']

    @property
    def name(self):
        return self.instance['AllocationId']

    def terminate(self):
        self.client.release_address(AllocationId=self.id)


class Ec2CustomerGateway(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2CustomerGateway, 'ec2', lambda client: client.describe_customer_gateways()['CustomerGateways'])

    @property
    def id(self):
        return self.instance['CustomerGatewayId']

    @property
    def name(self):
        return get_tag_dict_from_tag_list(self.instance.get('Tags')).get('Name')

    def terminate(self):
        self.client.delete_customer_gateway(CustomerGatewayId=self.id)


class DhcpOptionsSet(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, DhcpOptionsSet, 'ec2', lambda client: client.describe_dhcp_options()['DhcpOptions'])

    @property
    def id(self):
        return self.instance['DhcpOptionsId']

    @property
    def name(self):
        return self.instance['DhcpOptionsId']

    @property
    def ignore(self):
        return self.default_vpc.get('DhcpOptionsId') == self.id

    def terminate(self):
        self.client.delete_dhcp_options(DhcpOptionsId=self.id)


class Ec2Subnet(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2Subnet, 'ec2', lambda client: client.describe_subnets()['Subnets'])

    @property
    def id(self):
        return self.instance['SubnetId']

    @property
    def name(self):
        return get_tag_dict_from_tag_list(self.instance.get('Tags')).get('Name')

    @property
    def ignore(self):
        return self.instance['DefaultForAz']

    def terminate(self):
        self.client.delete_subnet(SubnetId=self.id)


class Ec2InternetGateway(DbTerminator):
    def __init__(self, client, instance):
        self._ignore = None
        super(Ec2InternetGateway, self).__init__(client, instance)

    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2InternetGateway, 'ec2', lambda client: client.describe_internet_gateways()['InternetGateways'])

    @property
    def id(self):
        return self.instance['InternetGatewayId']

    @property
    def name(self):
        return get_tag_dict_from_tag_list(self.instance.get('Tags')).get('Name')

    @property
    def ignore(self):
        if self._ignore is None:
            attachments = self._find_vpc_attachments()
            self._ignore = any([self.is_vpc_default(attachment_id) for attachment_id in attachments])
        return self._ignore

    def _find_vpc_attachments(self):
        return [attachment['VpcId'] for attachment in self.instance.get('Attachments', []) if attachment.get('VpcId')]

    def terminate(self):
        for attachment in self._find_vpc_attachments():
            self.client.detach_internet_gateway(InternetGatewayId=self.id, VpcId=attachment)

        self.client.delete_internet_gateway(InternetGatewayId=self.id)


class Ec2EgressInternetGateway(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2EgressInternetGateway, 'ec2',
                                  lambda client: client.describe_egress_only_internet_gateways()['EgressOnlyInternetGateways'])

    @property
    def id(self):
        return self.instance['EgressOnlyInternetGatewayId']

    @property
    def name(self):
        return self.instance['EgressOnlyInternetGatewayId']

    def terminate(self):
        self.client.delete_egress_only_internet_gateway(EgressOnlyInternetGatewayId=self.id)


class Ec2NatGateway(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2NatGateway, 'ec2', lambda client: client.describe_nat_gateways()['NatGateways'])

    @property
    def id(self):
        return self.instance['NatGatewayId']

    @property
    def name(self):
        return get_tag_dict_from_tag_list(self.instance.get('Tags')).get('Name')

    def terminate(self):
        self.client.delete_nat_gateway(NatGatewayId=self.id)


class Ec2NetworkAcl(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2NetworkAcl, 'ec2', lambda client: client.describe_network_acls()['NetworkAcls'])

    @property
    def id(self):
        return self.instance['NetworkAclId']

    @property
    def name(self):
        return get_tag_dict_from_tag_list(self.instance.get('Tags')).get('Name')

    @property
    def ignore(self):
        return self.instance['IsDefault']

    def terminate(self):
        self.client.delete_network_acl(NetworkAclId=self.id)


class Ec2Eni(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2Eni, 'ec2', lambda client: client.describe_network_interfaces()['NetworkInterfaces'])

    @property
    def id(self):
        return self.instance['NetworkInterfaceId']

    @property
    def name(self):
        return get_tag_dict_from_tag_list(self.instance.get('Tags')).get('Name')

    def terminate(self):
        self.client.delete_network_interface(NetworkInterfaceId=self.id)


class Ec2RouteTable(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2RouteTable, 'ec2', lambda client: client.describe_route_tables()['RouteTables'])

    @property
    def name(self):
        return get_tag_dict_from_tag_list(self.instance.get('Tags')).get('Name')

    @property
    def id(self):
        return self.instance['RouteTableId']

    @property
    def ignore(self):
        return any([association['Main'] for association in self.instance.get('Associations', [])])

    def terminate(self):
        for association in self.instance.get('Associations', []):
            self.client.disassociate_route_table(AssociationId=association['RouteTableAssociationId'])

        self.client.delete_route_table(RouteTableId=self.id)


class Ec2VpcEndpoint(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2VpcEndpoint, 'ec2', lambda client: client.describe_vpc_endpoints()['VpcEndpoints'])

    @property
    def id(self):
        return self.instance['VpcEndpointId']

    @property
    def name(self):
        return self.instance['ServiceName']

    @property
    def created_time(self):
        return self.instance['CreationTimestamp']

    def terminate(self):
        self.client.delete_vpc_endpoints(VpcEndpointIds=[self.id])


class Ec2Vpc(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2Vpc, 'ec2', lambda client: client.describe_vpcs()['Vpcs'])

    @property
    def age_limit(self):
        return datetime.timedelta(minutes=40)

    @property
    def id(self):
        return self.instance['VpcId']

    @property
    def name(self):
        return get_tag_dict_from_tag_list(self.instance.get('Tags')).get('Name')

    @property
    def ignore(self):
        return self.instance['IsDefault']

    def terminate(self):
        self.client.delete_vpc(VpcId=self.id)


class Ec2VpnConnection(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2VpnConnection, 'ec2', lambda client: client.describe_vpn_connections()['VpnConnections'])

    @property
    def id(self):
        return self.instance['VpnConnectionId']

    @property
    def name(self):
        return get_tag_dict_from_tag_list(self.instance.get('Tags')).get('Name')

    def terminate(self):
        self.client.delete_vpn_connection(VpnConnectionId=self.id)


class Ec2VpnGateway(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2VpnGateway, 'ec2', lambda client: client.describe_vpn_gateways()['VpnGateways'])

    @property
    def id(self):
        return self.instance['VpnGatewayId']

    @property
    def name(self):
        return get_tag_dict_from_tag_list(self.instance.get('Tags')).get('Name')

    def terminate(self):
        vpc_attachments = [attachment['VpcId'] for attachment in self.instance.get('VpcAttachments', []) if attachment['State'].startswith('attach')]
        for vpc_attachment in vpc_attachments:
            self.client.detach_vpn_gateway(
                VpcId=vpc_attachment,
                VpnGatewayId=self.id
            )
        self.client.delete_vpn_gateway(VpnGatewayId=self.id)


class Ec2SecurityGroup(DbTerminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, Ec2SecurityGroup, 'ec2', lambda client: client.describe_security_groups()['SecurityGroups'])

    @property
    def id(self):
        return self.instance['GroupId']

    @property
    def name(self):
        return self.instance['GroupName']

    @property
    def ignore(self):
        return self.name == 'default' or self.name.startswith('default_elb_')

    def terminate(self):
        self.client.delete_security_group(GroupId=self.id)


class ApiGatewayRestApi(Terminator):
    @staticmethod
    def create(credentials):
        return Terminator._create(credentials, ApiGatewayRestApi, 'apigateway', lambda client: client.get_rest_apis()['items'])

    @property
    def id(self):
        return self.instance['id']

    @property
    def name(self):
        return self.instance['name']

    @property
    def created_time(self):
        return self.instance['createdDate']

    def terminate(self):
        self.client.delete_rest_api(restApiId=self.id)
