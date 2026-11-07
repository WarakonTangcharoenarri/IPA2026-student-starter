from app.planner import build_plan
from app.backends._common import error_response


def plan_interface(
    router,
    desired_interface,
    get_interface_state,
):
    """Build a Part 2 plan from backend status."""
    try:
        status = get_interface_state(router, desired_interface["name"])
    except Exception as exc:
        return error_response(exc)
    if not isinstance(status, dict):
        return {"status": "error", "result": "backend_failed"}
    if status.get("status") == "error":
        return status
    if status.get("result") == "not_found":
        current_interface = None
    elif status.get("result") == "found":
        current_interface = status.get("interface")
        if not isinstance(current_interface, dict):
            return {"status": "error", "result": "backend_failed"}
    else:
        return {"status": "error", "result": "backend_failed"}

    return build_plan(desired_interface, current_interface)
