import traceback
from typing import Any
from typing import Optional

import requests

from config import CRM_API_KEY, CRM_API_URL, CRM_SYNC_TIMEOUT

session = requests.Session()


def crm_sync_enabled() -> bool:
    return bool(CRM_API_URL)


def send_event(event_name: str, lead_payload: dict[str, Any], meta: Optional[dict[str, Any]] = None) -> bool:
    if not CRM_API_URL:
        return False

    payload = {
        "event": event_name,
        "source": "projectpress_bot",
        "lead": lead_payload,
        "meta": meta or {},
    }

    headers = {"Content-Type": "application/json"}
    if CRM_API_KEY:
        headers["X-CRM-API-Key"] = CRM_API_KEY

    try:
        response = session.post(
            CRM_API_URL,
            json=payload,
            headers=headers,
            timeout=CRM_SYNC_TIMEOUT,
        )
        response.raise_for_status()
        return True
    except Exception:
        traceback.print_exc()
        return False
