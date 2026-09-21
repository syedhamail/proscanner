"""
Plan definitions and scan-quota logic.

Basic    -> $3 / 7 days -> 25 scans per rolling 7 days
Advanced -> $10 / month -> 100 scans per rolling 30 days
Premium  -> $100 / year -> unlimited scans, plan itself expires after 365 days
"""
from datetime import datetime, timedelta

PLAN_LIMITS = {
    "basic": {
        "label": "Basic",
        "price_display": "$3",
        "cadence": "7 days",
        "window": timedelta(days=7),
        "max_scans": 25,
    },
    "advanced": {
        "label": "Advanced",
        "price_display": "$10",
        "cadence": "month",
        "window": timedelta(days=30),
        "max_scans": 100,
    },
    "premium": {
        "label": "Premium",
        "price_display": "$100",
        "cadence": "year",
        "window": timedelta(days=365),
        "max_scans": None,  # unlimited within the window
    },
}


def plan_config(plan):
    return PLAN_LIMITS.get(plan)


def scan_status(user):
    """
    Read-only check: can this user run a scan right now?
    Returns a dict describing status + usage info (used by both the
    scan endpoint and the dashboard page).
    """
    now = datetime.utcnow()
    cfg = plan_config(user.plan) if user.plan else None

    if not cfg:
        return {"allowed": False, "reason": "no_plan"}

    if user.plan == "premium":
        started = user.plan_started_at or now
        expires_at = started + cfg["window"]
        if now > expires_at:
            return {"allowed": False, "reason": "plan_expired", "expires_at": expires_at}
        return {
            "allowed": True,
            "unlimited": True,
            "expires_at": expires_at,
        }

    # Basic / Advanced — rolling window
    window_start = user.scan_window_start
    if not window_start or now - window_start > cfg["window"]:
        used = 0
        remaining = cfg["max_scans"]
        window_reset_at = now + cfg["window"]
    else:
        used = user.scan_count
        remaining = max(0, cfg["max_scans"] - used)
        window_reset_at = window_start + cfg["window"]

    return {
        "allowed": remaining > 0,
        "reason": None if remaining > 0 else "limit_reached",
        "used": used,
        "remaining": remaining,
        "max_scans": cfg["max_scans"],
        "window_reset_at": window_reset_at,
    }


def register_scan(user):
    """
    Call only once scan_status(user)['allowed'] is True.
    Increments/rolls the usage window. Caller is responsible for db.session.commit().
    """
    now = datetime.utcnow()
    if user.plan == "premium":
        return  # unlimited — nothing to track

    cfg = plan_config(user.plan)
    if not user.scan_window_start or now - user.scan_window_start > cfg["window"]:
        user.scan_window_start = now
        user.scan_count = 1
    else:
        user.scan_count += 1
