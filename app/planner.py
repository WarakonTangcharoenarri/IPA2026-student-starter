_MANAGED_FIELDS = ("ipv4", "description", "admin_state")


def build_plan(desired_interface, current_interface):
    """
    Compare desired interface state with normalized current state
    and return a plan according to specs/plan-spec-v1.md.
    """
    if current_interface is None:
        changes = {
            field: {"to": desired_interface[field]}
            for field in _MANAGED_FIELDS
        }
        operation = "create"
    else:
        changes = {}
        for field in _MANAGED_FIELDS:
            current_value = current_interface[field]
            desired_value = desired_interface[field]
            if current_value != desired_value:
                changes[field] = {
                    "from": current_value,
                    "to": desired_value,
                }
        operation = "update" if changes else "no_change"

    return {
        "status": "ok",
        "result": "planned",
        "operation": operation,
        "changes": changes,
    }
