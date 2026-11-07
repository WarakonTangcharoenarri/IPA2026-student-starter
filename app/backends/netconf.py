import xml.etree.ElementTree as ET
from ipaddress import IPv4Interface, IPv4Network

from app.backends._common import (
    applied_response,
    error_response,
    loopback_number,
    router_credentials,
    validate_interface_values,
)
from app.backends.planning import plan_interface as _plan_interface


_NETCONF_NS = "urn:ietf:params:xml:ns:netconf:base:1.0"
_IETF_INTERFACES_NS = "urn:ietf:params:xml:ns:yang:ietf-interfaces"
_IETF_IP_NS = "urn:ietf:params:xml:ns:yang:ietf-ip"
_CISCO_NATIVE_NS = "http://cisco.com/ns/yang/Cisco-IOS-XE-native"


def _connect(router):
    from ncclient import manager

    username, password = router_credentials()
    return manager.connect(
        host=router,
        port=830,
        username=username,
        password=password,
        hostkey_verify=False,
        device_params={"name": "iosxe"},
        timeout=10,
    )


def _default_get_config(router, filter_xml):
    with _connect(router) as session:
        reply = session.get_config(
            source="running",
            filter=("subtree", filter_xml),
        )
        return reply.data_xml


def _default_edit_config(router, config_xml):
    with _connect(router) as session:
        reply = session.edit_config(
            target="running",
            config=config_xml,
        )
        if getattr(reply, "errors", None):
            raise RuntimeError("NETCONF edit-config failed")


def _filter_xml(interface_name):
    root = ET.Element(f"{{{_IETF_INTERFACES_NS}}}interfaces")
    interface = ET.SubElement(
        root,
        f"{{{_IETF_INTERFACES_NS}}}interface",
    )
    ET.SubElement(
        interface,
        f"{{{_IETF_INTERFACES_NS}}}name",
    ).text = interface_name
    return ET.tostring(root, encoding="unicode")


def _status_from_xml(xml_text):
    root = ET.fromstring(xml_text)
    interface = root.find(f".//{{{_IETF_INTERFACES_NS}}}interface")
    if interface is None:
        return {
            "status": "ok",
            "result": "not_found",
            "interface": None,
        }

    name = interface.findtext(f"{{{_IETF_INTERFACES_NS}}}name")
    enabled = interface.findtext(f"{{{_IETF_INTERFACES_NS}}}enabled")
    if not name or enabled not in {"true", "false"}:
        raise ValueError("NETCONF interface response is incomplete")

    ipv4 = interface.find(f"{{{_IETF_IP_NS}}}ipv4")
    address = (
        ipv4.find(f"{{{_IETF_IP_NS}}}address")
        if ipv4 is not None
        else None
    )
    primary = (
        address.find(f"{{{_IETF_IP_NS}}}ip")
        if address is not None
        else None
    )
    netmask = (
        address.find(f"{{{_IETF_IP_NS}}}netmask")
        if address is not None
        else None
    )
    if primary is None or netmask is None or not primary.text or not netmask.text:
        raise ValueError("NETCONF IPv4 address is incomplete")
    prefix = IPv4Network(f"0.0.0.0/{netmask.text}").prefixlen

    return {
        "status": "ok",
        "result": "found",
        "interface": {
            "name": name,
            "ipv4": str(IPv4Interface(f"{primary.text}/{prefix}")),
            "description": interface.findtext(
                f"{{{_IETF_INTERFACES_NS}}}description"
            ),
            "admin_state": "up" if enabled == "true" else "down",
        },
    }


def get_interface_state(
    router,
    interface_name,
    netconf_get_config=None,
):
    """Return normalized interface status using NETCONF."""
    get_config = netconf_get_config or _default_get_config
    try:
        return _status_from_xml(
            get_config(router, _filter_xml(interface_name))
        )
    except Exception as exc:
        return error_response(exc)


def plan_interface(
    router,
    desired_interface,
    netconf_get_config=None,
):
    """Return create/update/no_change plan using NETCONF status."""
    return _plan_interface(
        router,
        desired_interface,
        lambda target, name: get_interface_state(
            target,
            name,
            netconf_get_config,
        ),
    )


def _native_config(desired_interface):
    validate_interface_values(
        desired_interface["name"],
        desired_interface["ipv4"],
        desired_interface["description"],
        desired_interface["admin_state"],
    )
    number = loopback_number(desired_interface["name"])
    address = IPv4Interface(desired_interface["ipv4"])

    config = ET.Element(f"{{{_NETCONF_NS}}}config")
    native = ET.SubElement(config, f"{{{_CISCO_NATIVE_NS}}}native")
    interface = ET.SubElement(native, f"{{{_CISCO_NATIVE_NS}}}interface")
    loopback = ET.SubElement(
        interface,
        f"{{{_CISCO_NATIVE_NS}}}Loopback",
        {f"{{{_NETCONF_NS}}}operation": "replace"},
    )
    ET.SubElement(loopback, f"{{{_CISCO_NATIVE_NS}}}name").text = str(number)
    ET.SubElement(
        loopback,
        f"{{{_CISCO_NATIVE_NS}}}description",
    ).text = desired_interface["description"]

    ip = ET.SubElement(loopback, f"{{{_CISCO_NATIVE_NS}}}ip")
    address_node = ET.SubElement(ip, f"{{{_CISCO_NATIVE_NS}}}address")
    primary = ET.SubElement(
        address_node,
        f"{{{_CISCO_NATIVE_NS}}}primary",
    )
    ET.SubElement(
        primary,
        f"{{{_CISCO_NATIVE_NS}}}address",
    ).text = str(address.ip)
    ET.SubElement(
        primary,
        f"{{{_CISCO_NATIVE_NS}}}mask",
    ).text = str(address.network.netmask)

    if desired_interface["admin_state"] == "down":
        ET.SubElement(loopback, f"{{{_CISCO_NATIVE_NS}}}shutdown")

    return ET.tostring(config, encoding="unicode")


def apply_interface(
    router,
    desired_interface,
    netconf_edit_config=None,
):
    """Apply complete desired interface state using NETCONF."""
    try:
        edit_config = netconf_edit_config or _default_edit_config
        edit_config(router, _native_config(desired_interface))
        return applied_response()
    except Exception as exc:
        return error_response(exc)
