import ipaddress

from app.backends._common import (
    error_response,
    loopback_number,
    router_credentials,
)


def _canonical_interface(name):
    if not isinstance(name, str):
        return None
    if name.startswith("Loopback") and name[len("Loopback"):].isdigit():
        return name
    if name.startswith("Lo") and name[len("Lo"):].isdigit():
        return f"Loopback{name[len('Lo'):]}"
    return name


def _default_netmiko_get(router, interface_name):
    from netmiko import ConnectHandler

    username, password = router_credentials()
    connection = ConnectHandler(
        device_type="cisco_ios",
        host=router,
        username=username,
        password=password,
        timeout=10,
    )
    try:
        ip_info = connection.send_command(
            f"show ip interface {interface_name}",
            use_textfsm=True,
        )
        descriptions = connection.send_command(
            "show interfaces description",
            use_textfsm=True,
        )
        return ip_info, descriptions
    finally:
        connection.disconnect()


def _as_records(value):
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(
        isinstance(item, dict) for item in value
    ):
        return value
    raise ValueError("TextFSM response is malformed")


def _first_value(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _find_field(record, *names):
    normalized = {
        key.lower().replace(" ", "_"): value
        for key, value in record.items()
    }
    for name in names:
        value = normalized.get(name.lower().replace(" ", "_"))
        if value is not None:
            return value
    return None


def get_interface_state(
    router,
    interface_name,
    netmiko_get=None,
):
    """Return normalized interface status using Netmiko + TextFSM."""
    try:
        loopback_number(interface_name)
        ip_info, descriptions = (netmiko_get or _default_netmiko_get)(
            router,
            interface_name,
        )
        ip_records = _as_records(ip_info)
        matching = next(
            (
                record for record in ip_records
                if _canonical_interface(
                    _find_field(record, "interface")
                ) == _canonical_interface(interface_name)
            ),
            None,
        )
        if matching is None:
            return {
                "status": "ok",
                "result": "not_found",
                "interface": None,
            }

        ip_address = _first_value(
            _find_field(matching, "ip_address", "ip")
        )
        prefix = _first_value(
            _find_field(matching, "prefix_length", "prefix")
        )
        link_status = _find_field(matching, "link_status", "status")
        if not ip_address or prefix is None or link_status is None:
            raise ValueError("TextFSM interface data is incomplete")
        ipv4 = str(ipaddress.IPv4Interface(f"{ip_address}/{prefix}"))

        description_records = _as_records(descriptions)
        description_record = next(
            (
                record for record in description_records
                if _canonical_interface(
                    _find_field(record, "port", "interface")
                ) == _canonical_interface(interface_name)
            ),
            None,
        )
        description = (
            _find_field(description_record, "description")
            if description_record is not None
            else None
        )

        return {
            "status": "ok",
            "result": "found",
            "interface": {
                "name": interface_name,
                "ipv4": ipv4,
                "description": description,
                "admin_state": (
                    "down"
                    if "administratively down" in str(link_status).lower()
                    else "up"
                ),
            },
        }
    except Exception as exc:
        return error_response(exc)


def _default_netmiko_delete(router, interface_name):
    from netmiko import ConnectHandler

    username, password = router_credentials()
    connection = ConnectHandler(
        device_type="cisco_ios",
        host=router,
        username=username,
        password=password,
        timeout=10,
    )
    try:
        connection.send_config_set([f"no interface {interface_name}"])
    finally:
        connection.disconnect()


def delete_interface(
    router,
    interface_name,
    netmiko_delete=None,
):
    """Delete an interface using Netmiko."""
    try:
        loopback_number(interface_name)
    except Exception as exc:
        return error_response(exc)

    if netmiko_delete is not None:
        try:
            result = netmiko_delete(router, interface_name)
        except Exception as exc:
            return error_response(exc)
        if result == "deleted":
            return {"status": "ok", "result": "deleted"}
        if result == "not_found":
            return {
                "status": "ok",
                "result": "not_found",
                "interface": None,
            }
        return {"status": "error", "result": "backend_failed"}

    current = get_interface_state(router, interface_name)
    if current["status"] == "error":
        return current
    if current["result"] == "not_found":
        return current

    try:
        _default_netmiko_delete(router, interface_name)
    except Exception as exc:
        return error_response(exc)

    verification = get_interface_state(router, interface_name)
    if verification["status"] == "error":
        return verification
    if verification["result"] == "not_found":
        return {"status": "ok", "result": "deleted"}
    return {"status": "error", "result": "backend_failed"}
