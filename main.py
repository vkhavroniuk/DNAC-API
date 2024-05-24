from dnac import DNAC
import time
import os

if __name__ == '__main__':
    try:
        USERNAME = os.environ['DNAC_USERNAME']
        PASSWORD = os.environ['DNAC_PASSWORD']
        DNAC_IP = os.environ['DNAC_IP']
    except KeyError:
        print('Switch ENV Variables Not Found. Exiting...')
        exit(1)

    dnac = DNAC(DNAC_IP, USERNAME, PASSWORD)
    dnac.auth()

    # working with:
    # fabric_site_name = '' # SDA Fabric Site Name. String.
    # my_switch_ip = '' # Switch IP Address.

    # no github publishing ;)
    fabric_site_name = os.environ['fabric_site_name']
    my_switch_ip = os.environ['my_switch_ip']

    # define ports to be added.
    # DNAC uses VLAN names instead of VLAN ID to assign port
    # later, for easier, manipulation we can list of the VLANs, crete dict, and get proper name using ID.
    # for now I will use known names

    # example for AP, ACCESS, and Trunk ports:
    ports = [
        {'interfaceName': 'GigabitEthernet1/0/10', 'interfaceDescription': 'TEST1',
         'connectedDeviceType': 'USER_DEVICE', 'dataVlanName': 'PC_VLAN', 'voiceVlanName': 'VOICE_VLAN'},
        {'interfaceName': 'GigabitEthernet1/0/11', 'interfaceDescription': 'TEST2',
         'connectedDeviceType': 'ACCESS_POINT', 'dataVlanName': 'AP_VLAN_2200', 'voiceVlanName': ''},
        {'interfaceName': 'GigabitEthernet1/0/12', 'interfaceDescription': 'TEST3',
         'connectedDeviceType': 'TRUNKING_DEVICE', 'dataVlanName': '', 'voiceVlanName': ''},
    ]

    # get DNAC sites
    dnac_sites = dnac.get_sites()

    # get fabric ID using site ID
    my_site_id = dnac_sites[fabric_site_name]['id']
    my_fabric_id = dnac.get_fabric_id(my_site_id)

    # get device ID for B535 SW:
    my_switch_id = dnac.get_device_id(my_switch_ip)

    # remove if assigned. One by one. Each task should be completed before submitting new one.
    for port in ports:
        interface_name = port['interfaceName']
        if dnac.is_port_assigned(my_switch_ip, interface_name):
            ret = dnac.delete_port_assignment(my_fabric_id, my_switch_id, interface_name)
            taskId = ret['taskId']
            print(f'Port Deletion task {taskId} was submitted. Waiting for execution')
            dnac.wait_for_task(taskId)

    # wait two minutes, to test id, I want to go to DNAC and SW and see that ports were removed
    print('wait 120 seconds')
    time.sleep(120)

    # add ports. Bulk operations. Single Task.
    ret = dnac.assign_ports(my_fabric_id, my_switch_id, ports)
    taskId = ret['taskId']
    print(f'Port assignment task {taskId} was submitted. Waiting for execution')
    dnac.wait_for_task(taskId)
