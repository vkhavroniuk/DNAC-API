from __future__ import annotations
from ipaddress import ip_network
import requests
import time
import urllib3
urllib3.disable_warnings()


class DNAC:
    session = requests.Session()

    def __init__(self, ip: str, username: str, password: str):
        self.ip = ip
        self.username = username
        self.password = password
        self.base_url = 'https://' + ip

    def auth(self) -> None:
        auth_url = '/dna/system/api/v1/auth/token'
        self.session.auth = (self.username, self.password)
        r = None
        try:
            r = self.session.post(self.base_url + auth_url, verify=False)
            if r.ok:
                token = r.json()['Token']
                self.session.headers.update({'X-Auth-Token': token,
                                             'Content-Type': 'application/json', 'Accept': 'application/json'})
            r.raise_for_status()
        except requests.ConnectionError as e:
            print('Connection Failed. Error:', e)
            exit(1)
        except requests.exceptions.HTTPError as e:
            if r:
                error = r.json()['response']
                print(f'HTTP Error: {e}. DNAC Said: {error}')
            else:
                print(f'HTTP Error: {e}')
            exit(1)

    def get_post_delete(self, action, url, data=None, params=None):
        r = None
        if params is None:
            params = {}
        if action not in ['GET', 'POST', 'DELETE']:
            raise ValueError
        try:
            if action == 'POST':
                r = self.session.post(self.base_url + url, json=data, params=params, verify=False)
            elif action == 'DELETE':
                r = self.session.delete(self.base_url + url, json=data, params=params, verify=False)
            elif action == 'GET':
                r = self.session.get(self.base_url + url, params=params, verify=False)
            if not r.ok:
                r.raise_for_status()
        except requests.ConnectionError:
            print('Connection Failed')
            exit(1)
        except requests.exceptions.HTTPError as e:
            if r:
                error = r.json()['response']
                print(f'HTTP Error: {e}. DNAC Said: {error}')
            else:
                print(f'HTTP Error: {e}')
        return r

    def post(self, url, data, params=None):
        return self.get_post_delete('POST', url, data, params)

    def delete_request(self, url, data, params=None):
        return self.get_post_delete('DELETE', url, data, params)

    def get(self, url, params=None):
        return self.get_post_delete('GET', url, data=None, params=params)

    def wait_for_task(self, task_id) -> None:
        """
        Receives task id and waits for execution. Reports status.
        :param task_id:
        :return: None
        """
        url = f'/dna/intent/api/v1/task/{task_id}'
        while True:
            r = self.get(url)
            status = r.json()['response']
            if 'endTime' in status:
                if not status['isError']:
                    print(f'Task {task_id} completed with no errors')
                else:
                    print(f'Task {task_id} completed with errors')
                    print(status)
                break
            else:
                print(f'Task {task_id} still in progress')
                time.sleep(1)

    def get_sites(self) -> dict:
        site_url = '/dna/intent/api/v2/site'
        r = self.get(site_url)
        sites = r.json()['response']
        sites_dict = {}
        for site in sites:
            site_name = site['name']
            site_id = site['id']
            site_hierarchy = site['groupNameHierarchy']
            sites_dict[site_name] = {'id': site_id, 'groupNameHierarchy': site_hierarchy}
        return sites_dict

    def get_global_creds_id(self) -> list:
        credentials_url = '/dna/intent/api/v1/global-credential'
        cred_type = ['CLI', 'SNMPV2_WRITE_COMMUNITY', 'HTTP_WRITE', 'NETCONF']
        cred_id_list = []
        for cred in cred_type:
            params = {'credentialSubType': cred}
            r = self.get(credentials_url, params=params)
            cred_resp = r.json()['response'][0]['id']
            cred_id_list.append(cred_resp)
        return cred_id_list

    def get_all_devices(self):
        device_url = '/dna/intent/api/v1/network-device'
        r = self.get(device_url)
        return r.json()['response']

    def get_anycast_gateways(self):
        gw_url = '/dna/intent/api/v1/sda/anycastGateways'
        r = self.get(gw_url)
        return r.json()['response']

    def get_fabric_id(self, site_id: str) -> str | None:
        url = '/dna/intent/api/v1/sda/fabricSites/'
        r = self.get(url)
        data = r.json()['response']
        for site in data:
            if site['siteId'] == site_id:
                return site['id']
        return

    def get_subnet_global_parent(self, subnet: str) -> str | None:
        global_pool_url = '/dna/intent/api/v1/global-pool'
        r = self.get(global_pool_url)
        global_pool = r.json()['response']
        global_pool_list = []
        for pool in global_pool:
            global_pool_list.append(ip_network(pool['ipPoolCidr']))
        ip_subnet = ip_network(subnet)
        for super_net in global_pool_list:
            if ip_subnet.subnet_of(super_net):
                return str(super_net)
        return None

    def get_site_subnets(self, site_id: str) -> dict:
        subnets_url = f'/dna/intent/api/v1/reserve-ip-subpool?siteId={site_id}'
        r = self.get(subnets_url)
        pools = r.json()['response']
        ip_pools = {}
        for pool in pools:
            ip_pools[pool['groupName']] = pool['ipPools'][0]['ipPoolCidr']
        return ip_pools

    def is_subnet_exit(self, site_id: str, subnet: str) -> bool:
        subnets = self.get_site_subnets(site_id)
        return True if subnet in subnets.values() else False

    def get_device_id(self, mgmt_ip: str) -> str:
        url = f'/dna/intent/api/v1/network-device?managementIpAddress={mgmt_ip}'
        r = self.get(url)
        return r.json()['response'][0]['id']

    def get_all_port_assignments(self):
        url = '/dna/intent/api/v1/sda/portAssignments'
        r = self.get(url)
        return r.json()['response']

    def get_port_assignment_info(self, mgmt_ip, interface):
        """ keep in mind that if port is not assigned DNAC returns HTTP Error """
        port_url = (f'/dna/intent/api/v1/business/sda/hostonboarding/'
                    f'user-device?interfaceName={interface}&deviceManagementIpAddress={mgmt_ip}')
        r = self.get(port_url)
        return r.json()['response']

    def is_port_assigned(self, mgmt_ip, interface) -> bool:
        device_id = self.get_device_id(mgmt_ip)
        assigned_ports = self.get_all_port_assignments()
        for assigned_port in assigned_ports:
            if assigned_port['networkDeviceId'] == device_id and assigned_port['interfaceName'] == interface:
                return True
        return False

    def delete_port_assignment(self, fabric_id, device_id, interface):
        assign_url = (f'/dna/intent/api/v1/sda/portAssignments?fabricId={fabric_id}&'
                      f'networkDeviceId={device_id}&interfaceName={interface}')
        r = self.delete_request(assign_url, data='')
        return r.json()['response']

    def assign_ports(self, fabric_id, device_id, ports_list):
        # USER_DEVICE, ACCESS_POINT, TRUNKING_DEVICE]
        assign_url = '/dna/intent/api/v1/sda/portAssignments'
        port_template = {
            "fabricId": fabric_id,
            "networkDeviceId": device_id,
            # "interfaceName": interface,
            # "connectedDeviceType": port_type,  # "USER_DEVICE",
            # "dataVlanName": data_vlan,  # "PC_VLAN",
            # "voiceVlanName": voice_vlan,  # "VOICE_VLAN",
            "authenticateTemplateName": "No Authentication",
            # "interfaceDescription": descr
        }
        ports_to_configure = []
        for new_port in ports_list:
            new_port_json = port_template.copy()
            connectedDeviceType = new_port['connectedDeviceType']
            if connectedDeviceType not in ['USER_DEVICE', 'ACCESS_POINT', 'TRUNKING_DEVICE']:
                raise ValueError(f'type {connectedDeviceType} is not allowed')
            new_port_json['interfaceName'] = new_port['interfaceName']
            new_port_json['interfaceDescription'] = new_port['interfaceDescription']
            new_port_json['connectedDeviceType'] = new_port['connectedDeviceType']
            new_port_json['dataVlanName'] = new_port['dataVlanName']
            new_port_json['voiceVlanName'] = new_port['voiceVlanName']
            ports_to_configure.append(new_port_json)
        r = self.post(assign_url, data=ports_to_configure)
        return r.json()['response']