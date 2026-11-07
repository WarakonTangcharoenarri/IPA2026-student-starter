"""Part 4 student implementation."""

from app.backends import ansible, netconf, netmiko_textfsm, restconf


def dispatch_request(data):
    router = data["router"]
    method = data["method"]
    action = data["action"]
    interface = data["desired"]["interface"]

    if method == "restconf":
        backend = restconf
    elif method == "netconf":
        backend = netconf
    elif method == "ansible":
        backend = ansible
    elif method == "netmiko-textfsm":
        backend = netmiko_textfsm
    else:
        return {"status": "error", "result": "invalid_method"}

    if action == "status":
        operation = getattr(backend, "get_interface_state", None)
        arguments = (router, interface["name"])
    elif action == "plan":
        operation = getattr(backend, "plan_interface", None)
        arguments = (router, interface)
    elif action == "apply":
        operation = getattr(backend, "apply_interface", None)
        arguments = (router, interface)
    elif action == "delete":
        operation = getattr(backend, "delete_interface", None)
        arguments = (router, interface["name"])
    else:
        return {"status": "error", "result": "invalid_action"}

    if operation is None:
        return {"status": "error", "result": "invalid_action"}
    return operation(*arguments)
