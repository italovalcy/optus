"""Main module of optus/mirror Kytos Network Application.

"""

from kytos.core import KytosNApp, log, rest
from napps.optus.mirror import settings
from flask import jsonify, request
from uuid import uuid4
import requests
import json
import copy


class Main(KytosNApp):

    def setup(self):
        self.mirrors = {"mirrors": {}}
        self.enabled_mirrors = {"enabled_mirrors": []}
        """
        mirrors = { "mirrors": {
            "mirror_id1" : {
                "name": "...",
                "type": "...",
                "status": "...",
                "target_port": "..."
                "...": "..."
                "original_flow": {},
                "mirror_flow": {}
            }
        }}
        """


    def execute(self):
        """Do nothing."""
        log.info("Mirror NApp running...")


    def validate_switch(self, switch):
        """Validates that the specified switch exists in the topology."""
        url = 'http://0.0.0.0:8181/api/kytos/topology/v3/switches'
        headers = {'Content-Type': 'application/json'}
        current_switches = requests.get(url, headers=headers).json()

        return switch in [current_switch for current_switch in current_switches["switches"]]


    def validate_circuit(self, circuit):
        """Validates that the specified circuit exists in mef_eline."""
        url = 'http://0.0.0.0:8181/api/kytos/mef_eline/v2/evc/'
        headers = {'Content-Type': 'application/json'}
        current_circuits = requests.get(url, headers=headers).json()

        return circuit in current_circuits.keys()


    def validate_interface(self, interface):
        """Validates that the specified interface exists in the topology."""
        url = 'http://0.0.0.0:8181/api/kytos/topology/v3/interfaces'
        headers = {'Content-Type': 'application/json'}
        current_interfaces = requests.get(url, headers=headers).json()

        return interface in [current_interfaces['interfaces'][key]['id'] for key in current_interfaces['interfaces']]


    def create_EVC_mirror(self, command):
        """Creates a mirror for a specified EVC."""
        try:
            name = command["name"]
            circuit_id = command["circuit_id"]
            switch = command["switch"]
            target_port = int(command["target_port"].split(":")[-1])

            if self.validate_switch(switch) and self.validate_circuit(circuit_id):
                
                #CREATE THE MIRROR
                cookie = int(circuit_id,16) if (len(circuit_id) == 16) else int(circuit_id[len(circuit_id)//2:],16)

                flow_NApp_url = f'http://0.0.0.0:8181/api/kytos/flow_manager/v2/flows/{switch}'
                headers = {'Content-Type': 'application/json'} 

                flow_response = requests.get(flow_NApp_url, headers=headers).json()

                original_flow = {"flows":[]}
                new_flow = {"flows": []}

                for flow in flow_response[switch]["flows"]:
                    if (flow["cookie"] == cookie):
                        for extraneous_key in ["stats","hard_timeout","priority","id","idle_timeout","switch"]:
                            flow.pop(extraneous_key,None)

                        original_flow['flows'].append(copy.deepcopy(flow))
                        flow["actions"].append({"action_type": "output", "port": target_port})
                        new_flow['flows'].append(flow)

                payload = json.dumps(new_flow)
                log.info(requests.post(flow_NApp_url, headers=headers, data=payload))

                #ADD MIRROR TO MAIN/ACTIVE MIRROR LIST
                mirror_id = uuid4().hex[:16]
                
                self.mirrors["mirrors"][mirror_id] = {
                    "name": name,
                    "type": "EVC",
                    "status": "Enabled",
                    "circuit_id": circuit_id,
                    "switch": switch,
                    "target_port": target_port,
                    "original_flow": original_flow,
                    "mirror_flow": new_flow
                }

                self.enabled_mirrors["enabled_mirrors"].append(mirror_id)

                return f"Mirror created: {mirror_id}\n", 200 

            else: 
                return jsonify(f"Switch not found: {switch}"), 400

        except KeyError:
            return jsonify("Invalid request"), 400


    def create_interface_mirror(self, command):
        """Creates a mirror for a specified interface."""
        try:
            name = command["name"]
            interface = command["interface"]
            target_port = int(command["target_port"].split(":")[-1])
            switch = ":".join(command["interface"].split(":")[:-1])
            interface_port = int(command["interface"].split(":")[-1])

            if self.validate_interface(interface):

                #CREATE THE MIRROR
                flow_NApp_url = f'http://0.0.0.0:8181/api/kytos/flow_manager/v2/flows/{switch}'
                headers = {'Content-Type': 'application/json'} 

                flow_response = requests.get(flow_NApp_url, headers=headers).json()

                original_flow = {"flows":[]}
                new_flow = {"flows": []}

                for flow in flow_response[switch]["flows"]:
                    if "in_port" in flow["match"]:
                        in_port = flow["match"]["in_port"]
                    else:
                        in_port = []

                    out_ports = [action["port"] for action in flow["actions"] if "port" in action]

                    if (interface_port == in_port) or (interface_port in out_ports):
                        for extraneous_key in ["stats","hard_timeout","priority","id","idle_timeout","switch"]:
                            flow.pop(extraneous_key,None)

                        original_flow['flows'].append(copy.deepcopy(flow))
                        flow["actions"].append({"action_type": "output", "port": target_port})
                        new_flow['flows'].append(flow)
 
                payload = json.dumps(new_flow)
                log.info(requests.post(flow_NApp_url, headers=headers, data=payload))

                #ADD MIRROR TO MAIN/ACTIVEMIRROR LIST
                mirror_id = uuid4().hex[:16]

                self.mirrors["mirrors"][mirror_id] = {
                    "name": name,
                    "type": "interface",
                    "status": "Enabled",
                    "switch": switch,
                    "interface": interface,
                    "target_port": target_port,
                    "original_flow": original_flow,
                    "mirror_flow": new_flow
                }

                self.enabled_mirrors["enabled_mirrors"].append(mirror_id)

                return f"Mirror created: {mirror_id}\n", 200
            else: 
                return jsonify(f"Interface not found: {interface}"), 400

        except KeyError as e:
            return jsonify(f"Invalid request: {e}"), 400


    '''def create_application_mirror(self, command):
        """Creates a mirror for a specified application."""
        try:
            match = command["match"]
            target_port = int(command["target_port"].split(":")[-1])

            return jsonify(command), 200

        except KeyError:
            return jsonify("Invalid request"), 400'''


    '''def create_rmtprt_vlan_target_mirror(self, command):
        """Creates a mirror with a remote port target and VLAN id."""
        try:
            circuit_id = command["circuit_id"]
            switch = command["switch"]
            target_port = int(command["target_port"].split(":")[-1])
            to_tag = command["to_tag"]

            return jsonify(command), 200

        except KeyError:
            return jsonify("Invalid request"), 400'''


    @rest('v1/', methods=['POST'])
    def create_mirror(self):
        """Creates a mirror, calling the appropriate function for the specified mirror type."""
        command = request.get_json()

        if "circuit_id" in command:      
            if "to_tag" in command:
                #return self.create_rmtprt_vlan_target_mirror(command)
                pass
            else:
                return self.create_EVC_mirror(command)

        elif "interface" in command:
            return self.create_interface_mirror(command)

        elif "match" in command:
            #return self.create_application_mirror(command)
            pass

        else:
            return jsonify("Invalid request"), 400


    @rest('v1/', methods=['GET'])
    def list_enabled_mirrors(self):
        """Returns a json with all the enabled mirrors."""
        return jsonify(self.enabled_mirrors), 200


    @rest('v1/all', methods=['GET'])
    def list_all_mirrors(self):
        """Returns a json with all the created mirrors."""
        return jsonify(self.mirrors), 200


    @rest('v1/<mirror_id>', methods=['POST'])
    def change_mirror_status(self, mirror_id):
        """Changes a mirror status, using the mirror_id specified in the API call url."""
        command = request.get_json()
        status_request = command["enable"].lower()

        if ("enable" in command) and (status_request in ["false", "true"]):

            if mirror_id in self.mirrors["mirrors"]:

                #DISABLE THE MIRROR BY REMOVING THE FLOW
                if self.mirrors["mirrors"][mirror_id]["type"] in ["EVC", "interface"]:
                    switch = self.mirrors["mirrors"][mirror_id]["switch"]
                    flow_NApp_url = f'http://0.0.0.0:8181/api/kytos/flow_manager/v2/flows/{switch}'
                    headers = {'Content-Type': 'application/json'}
                    current_status = self.mirrors["mirrors"][mirror_id]["status"]

                    if (status_request == "false") and (current_status == "Enabled"):
                        flow_to_send = self.mirrors["mirrors"][mirror_id]["original_flow"]
                        new_status = "Disabled"
                        self.enabled_mirrors["enabled_mirrors"].remove(mirror_id)

                    elif (status_request == "true") and (current_status == "Disabled"):
                        flow_to_send = self.mirrors["mirrors"][mirror_id]["mirror_flow"]
                        new_status = "Enabled"
                        self.enabled_mirrors["enabled_mirrors"].append(mirror_id)
                        
                    else:
                        return jsonify("Invalid request"), 400

                    payload = json.dumps(flow_to_send)
                    flow_response = requests.post(flow_NApp_url, headers=headers, data=payload).json()

                #REMOVE THE MIRROR FROM THE LIST AND CHANGE STATUS
                self.mirrors["mirrors"][mirror_id]["status"] = new_status

                return jsonify(f"{new_status} mirror: {mirror_id}"), 200

            else:
                return jsonify(f"Invalid mirror: {mirror_id}"), 400

        else:
            return jsonify("Invalid request"), 400



    def shutdown(self):
        """Do nothing."""
        log.info("NApp optus/mirror shutting down.")