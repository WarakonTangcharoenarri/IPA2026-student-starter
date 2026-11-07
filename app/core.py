from collections.abc import Mapping

import yaml


_ALLOWED_ROUTERS = {
    "10.0.29.101",
    "10.0.29.102",
    "10.0.29.103",
    "10.0.29.104",
    "10.0.29.105",
}

_SUPPORTED_ACTIONS = {
    "restconf": {"status", "plan", "apply"},
    "netconf": {"status", "plan", "apply"},
    "ansible": {"apply"},
    "netmiko-textfsm": {"status", "delete"},
}


def _error(result):
    return {"status": "error", "result": result}


def validate_request(data):
    """
    Validate one IPA2026 desired-state request.

    Return a response dictionary according to
    specs/response-spec-v1.md.
    """
    if not isinstance(data, Mapping):
        return _error("invalid_yaml")

    version = data.get("version")
    if type(version) is not int or version != 1:
        return _error("invalid_version")

    if "router" not in data:
        return _error("missing_router")
    router = data["router"]
    if not isinstance(router, str) or router not in _ALLOWED_ROUTERS:
        return _error("invalid_router")

    if "method" not in data:
        return _error("missing_method")
    method = data["method"]
    if not isinstance(method, str) or method not in _SUPPORTED_ACTIONS:
        return _error("invalid_method")

    if "action" not in data:
        return _error("missing_action")
    action = data["action"]
    if not isinstance(action, str) or action not in _SUPPORTED_ACTIONS[method]:
        return _error("invalid_action")

    if "desired" not in data or data["desired"] is None:
        return _error("missing_desired")
    desired = data["desired"]
    if not isinstance(desired, Mapping) or "interface" not in desired:
        return _error("missing_interface")
    interface = desired["interface"]
    if not isinstance(interface, Mapping) or "name" not in interface:
        return _error("missing_interface_name")
    if interface["name"] is None:
        return _error("missing_interface_name")

    if action in {"plan", "apply"}:
        for field in ("ipv4", "description", "admin_state"):
            if field not in interface or interface[field] is None:
                return _error(f"missing_{field}")
        if interface["admin_state"] not in ("up", "down"):
            return _error("invalid_admin_state")

    return {"status": "ok", "result": "accepted"}


def process_request_file(path):
    """
    Read a YAML request file, validate it,
    and return a response dictionary.
    """
    try:
        with open(path, encoding="utf-8") as request_file:
            data = yaml.safe_load(request_file)
    except (yaml.YAMLError, UnicodeDecodeError):
        return _error("invalid_yaml")

    if not isinstance(data, Mapping):
        return _error("invalid_yaml")
    return validate_request(data)
