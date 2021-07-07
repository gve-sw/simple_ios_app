'''
Copyright (c) 2021 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
'''


import requests, yaml, json, urllib3
from flask import Flask, render_template, request, url_for, json, redirect
from netmiko import ConnectHandler

# get credentials
config = yaml.safe_load(open("credentials.yml"))
port_switches = config['port_switches']
port_username = config['port_switches_username']
port_password = config['port_switches_password']
endpoint_details = {}
switch_list = []
ports = []
port_details = {}
switch_ports_details = []
redirecting_port = False
copy_success = None
port_enabled = 1
speed_options = ['10', '100', '1000', '10000']
duplex_options = ['full', 'half', 'auto']
port_speed = ""
port_duplex = ""
port_statistics = {}
vlan_details = []
vlans_to_exclude = config['vlans_to_exclude']

# Suppressing warnings for non-secure connection
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# flask app
app = Flask(__name__)


@app.route('/',methods=['GET','POST'])
def index():
    return redirect(url_for('.port_config'))


# STEP 1: select a switch
@app.route('/port_config',methods=['GET','POST'])
def port_config():
    global switch_list
    global ports
    global port_details
    global port_enabled
    global speed_options
    global duplex_options
    global port_speed
    global port_duplex
    global port_statistics
    global vlan_details

    switch_list = []
    ports = []
    port_details = {}
    logic = 0
    alert = 0

    # Read in from the credentials.yml file
    switch_list = port_switches

    return render_template("port_config.html",switches=switch_list,endpoints=ports,
                            endpoint_details=port_details,logic=logic,alert=alert, vlan_details=vlan_details,
                            port_enabled=port_enabled, speed_options=speed_options, duplex_options=duplex_options, port_speed=port_speed,
                            port_duplex=port_duplex, port_statistics=port_statistics)


@app.route('/submit_port_switch', methods=['POST'])
def submit_port_switch():
    global redirecting_port
    redirecting_port = False
    req = request.form
    selected_switch = req['switch']
    return redirect(url_for('port',selected_switch=selected_switch))


# STEP 2: retrieve list of interfaces
@app.route('/port_config/<selected_switch>', methods=['GET'])
def port(selected_switch):
    global switch_list
    global ports
    global port_details
    global switch_ports_details
    global redirecting_port
    global port_enabled
    global speed_options
    global duplex_options
    global port_speed
    global port_duplex
    global port_statistics
    global vlan_details

    logic = 0
    alert = 0
    if redirecting_port == True:
        alert = 1


    if selected_switch in port_switches:
        switch_list = [selected_switch]
    else:
        return

    headers = {
        'Accept': 'application/yang-data+json'
    }
    get_ints = requests.get("https://" + selected_switch + "/restconf/data/ietf-interfaces:interfaces/interface", headers=headers, auth=(port_username, port_password), verify=False)
    switch_ports_details = get_ints.json()['ietf-interfaces:interface']
    ports = []
    for interface in switch_ports_details:
        ports.append(interface['name'])

    logic = 1

    return render_template("port_config.html",switches=switch_list,endpoints=ports,
                            endpoint_details=port_details,logic=logic,alert=alert, vlan_details=vlan_details,
                            port_enabled=port_enabled, speed_options=speed_options, duplex_options=duplex_options, port_speed=port_speed, port_duplex=port_duplex, port_statistics=port_statistics)


# STEP 3: select an interface of the list
@app.route('/submit_port', methods=['POST'])
def submit_port():
    req = request.form
    selected_port = req['endpoint']
    selected_port = selected_port.replace('/', '.')
    return redirect(url_for('switch_description',selected_switch=switch_list[0],selected_port=selected_port))


# STEP 4: show configuration options and switch/port information
@app.route('/port_config/<selected_switch>/<selected_port>', methods=['GET'])
def switch_description(selected_switch, selected_port):
    global switch_list
    global ports
    global port_details
    global switch_ports_details
    global redirecting_port
    global port_enabled
    global speed_options
    global duplex_options
    global port_speed
    global port_duplex
    global port_statistics
    global vlan_details
    global copy_success

    alert = 0
    if copy_success != None:
        if copy_success == True:
            alert = 2
        else:
            alert = 1
        copy_success = None

    logic = 2

    selected_port = selected_port.replace('.', '/')

    if selected_port in ports:
        port_details = {
            'selected_port': selected_port,
            'Switch SW Version': 'TBD',
        }

    headers = {
        'Accept': 'application/yang-data+json',
        'Content-Type': 'application/yang-data+json'
    }
    base_url = "https://" + selected_switch 

    get_ints = requests.get(f"{base_url}/restconf/data/ietf-interfaces:interfaces/interface", headers=headers, auth=(port_username, port_password), verify=False)
    switch_ports_details = get_ints.json()['ietf-interfaces:interface']
    for i in switch_ports_details:
        if i['name'] == selected_port:
            if i['enabled'] == True:
                port_enabled = 1
            else:
                port_enabled = 0
    
    # Get vlan details
    url = f"{base_url}/restconf/data/Cisco-IOS-XE-native:native/vlan"
    resp = requests.get(url, headers=headers, auth=(port_username, port_password), verify=False)

    try:
        vlan_details = resp.json()['Cisco-IOS-XE-native:vlan']['Cisco-IOS-XE-vlan:vlan-list']

        # Exclude the vlans from vlan details
        vlan_details[:] = [d for d in vlan_details if not d.get('id') in vlans_to_exclude]
    except:
        vlan_details = []

    ports = [selected_port]

    # Get duplex and speed details
    url = f"{base_url}/restconf/data/Cisco-IOS-XE-native:native/interface"
    resp = requests.get(url, headers=headers, auth=(port_username, port_password), verify=False)
    duplex_speed_details = resp.json()['Cisco-IOS-XE-native:interface']

    for key in duplex_speed_details:
        if key[:10] == selected_port[:10]:
            target_key = key

            for interface in duplex_speed_details[target_key]:
                if interface['name'] in selected_port:
                    if 'Cisco-IOS-XE-ethernet:duplex' in interface:
                        port_duplex = interface['Cisco-IOS-XE-ethernet:duplex']
                    if 'Cisco-IOS-XE-ethernet:speed' in interface:
                        speed_key = interface['Cisco-IOS-XE-ethernet:speed'].keys()
                        speed_key = list(speed_key)[0]
                        port_speed = speed_key.split('-')[1]
                        port_speed = int(port_speed)

    # Get port_statistics
    url = f"{base_url}/restconf/data/ietf-interfaces:interfaces-state"
    resp = requests.get(url, headers=headers, auth=(port_username, port_password), verify=False)

    for intf in resp.json()['ietf-interfaces:interfaces-state']['interface']:
        if intf['name'] == selected_port:
            port_statistics = intf['statistics']

    selected_port = selected_port.replace('/', '.')

    return render_template("port_config.html", switches=switch_list,
                           endpoints=ports, endpoint_details=port_details, logic=logic,
                           alert=alert, port_enabled=port_enabled, switch_ports_details=switch_ports_details, vlan_details=vlan_details,
                           duplex_options=duplex_options, speed_options=speed_options, port_speed=port_speed, port_duplex=port_duplex, port_statistics=port_statistics)




# Submit button for enabling or disabling a port
@app.route('/submit_enable_port', methods=['POST'])
def submit_enable_port():
    # global endpoint_details
    # global port_enabled

    global port_details
    selected_port = port_details['selected_port']

    req = request.form
    

    #TODO Add logic to enable port
    headers = {
        'Accept': 'application/yang-data+json',
        'Content-Type': 'application/yang-data+json'
    }
    data = {
        "ietf-interfaces:enabled": True
    }
    if 'disable_port' in req:
        data["ietf-interfaces:enabled"] = False
    update_port = requests.put("https://" + switch_list[0] + "/restconf/data/ietf-interfaces:interfaces/interface=" + selected_port +  "/enabled", headers=headers, data=json.dumps(data), auth=(port_username, port_password), verify=False)

    selected_port = selected_port.replace('/', '.')
    return redirect(url_for('switch_description',selected_switch=switch_list[0],selected_port=selected_port))

# button and form for adding a VLAN
@app.route('/add_vlan', methods=['POST'])
def add_vlan():
    global port_details
    selected_port = port_details['selected_port']
    selected_port = selected_port.replace('/', '.')

    selected_switch = switch_list[0]

    req = request.form

    if not 'name' in req or not 'id' in req:
        raise ValueError("The form for adding VLANs should contain a name and id")

    if int(req['id']) < 0 or int(req['id']) > 4095:
        raise ValueError("The id of a VLAN should be between 0 and 4096")

    headers = {
        'Accept': 'application/yang-data+json',
        'Content-Type': 'application/yang-data+json'
    }

    base_url = "https://" + selected_switch 
    url = f"{base_url}/restconf/data/Cisco-IOS-XE-native:native/vlan"

    resp = requests.get(url, headers=headers, auth=(port_username, port_password), verify=False)

    data = resp.json()

    data['Cisco-IOS-XE-native:vlan']['Cisco-IOS-XE-vlan:vlan-list'].append({'id': int(req['id']),
    'name': req['name']})

    resp = requests.patch(url, data = json.dumps(data), headers=headers, auth=(port_username, port_password), verify=False)

    return redirect(url_for('switch_description',selected_switch=switch_list[0],selected_port=selected_port))

# button for deleting a vlan
@app.route('/delete_vlan', methods=['POST'])
def delete_vlan():
    global port_details
    selected_port = port_details['selected_port']
    selected_port = selected_port.replace('/', '.')

    selected_switch = switch_list[0]

    req = request.form

    headers = {
        'Accept': 'application/yang-data+json',
        'Content-Type': 'application/yang-data+json'
    }

    base_url = "https://" + selected_switch 
    url = f"{base_url}/restconf/data/Cisco-IOS-XE-native:native/vlan"

    resp = requests.get(url, headers=headers, auth=(port_username, port_password), verify=False)

    data = resp.json()

    id_to_delete = int(req['vlan'])

    data['Cisco-IOS-XE-native:vlan']['Cisco-IOS-XE-vlan:vlan-list'][:] = [d for d in data['Cisco-IOS-XE-native:vlan']['Cisco-IOS-XE-vlan:vlan-list'] if d.get('id') != id_to_delete]  

    resp = requests.put(url, data = json.dumps(data), headers=headers, auth=(port_username, port_password), verify=False)

    return redirect(url_for('switch_description',selected_switch=switch_list[0],selected_port=selected_port))


# button for submitting duplex and speed setting
@app.route('/submit_duplex_speed', methods=['POST'])
def submit_duplex_speed():
    global port_details
    selected_port = port_details['selected_port']

    selected_switch = switch_list[0]

    req = request.form

    headers = {
        'Accept': 'application/yang-data+json',
        'Content-Type': 'application/yang-data+json'
    }

    base_url = "https://" + selected_switch 
    url = f"{base_url}/restconf/data/Cisco-IOS-XE-native:native/interface"

    resp = requests.get(url, headers=headers, auth=(port_username, port_password), verify=False)

    data = resp.json()

    for key in data['Cisco-IOS-XE-native:interface']:
        if key[:10] == selected_port[:10]:
            target_key = key

    speed = req['speed']
    duplex = req['duplex']

    counter = 0 
    for interface in data['Cisco-IOS-XE-native:interface'][target_key]:
        if interface['name'] in selected_port:
            temp_dict = interface
            temp_dict['Cisco-IOS-XE-ethernet:speed'] = {f'value-{speed}':[None]}
            temp_dict['Cisco-IOS-XE-ethernet:duplex'] = duplex
            data['Cisco-IOS-XE-native:interface'][target_key][counter] = temp_dict
        counter += 1

    resp = requests.put(url, data = json.dumps(data), headers=headers, auth=(port_username, port_password), verify=False)
    selected_port = selected_port.replace('/', '.')
    return redirect(url_for('switch_description',selected_switch=switch_list[0],selected_port=selected_port))


# button for copying run to start config
@app.route('/copy_run_start', methods=['POST'])
def copy_run_start():
    global port_details
    global copy_success
    selected_port = port_details['selected_port']

    ch = ConnectHandler(device_type='cisco_ios', host=switch_list[0], username=port_username,
                        password=port_password, secret=port_password)
    print('connected')
    ch.enable()
    output = ch.send_command('write memory')
    print(output)

    if "[OK]" in output:
        copy_success = True
    else:
        copy_success = False

    return redirect(url_for('switch_description',selected_switch=switch_list[0],selected_port=selected_port))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=True)