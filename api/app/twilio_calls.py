"""
Twilio click-to-call integration for VendorSphere.

Places an outbound "click-to-call-and-connect" call using the Twilio REST API.
Twilio first rings the agent's phone (the VendorSphere user); when they answer,
it bridges them to the vendor's contact number using inline TwiML — so no public
webhook is required and this works from localhost.

Credentials are read from pydantic Settings (loaded from api/.env):
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, TWILIO_AGENT_NUMBER
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from xml.sax.saxutils import quoteattr, escape

from app.settings import get_settings

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


@dataclass
class TwilioConfig:
    account_sid: str
    auth_token: str
    from_number: str
    agent_number: str

    @property
    def configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_number)


def get_twilio_config() -> TwilioConfig:
    s = get_settings()
    return TwilioConfig(
        account_sid=(getattr(s, "twilio_account_sid", "") or "").strip(),
        auth_token=(getattr(s, "twilio_auth_token", "") or "").strip(),
        from_number=(getattr(s, "twilio_from_number", "") or "").strip(),
        agent_number=(getattr(s, "twilio_agent_number", "") or "").strip(),
    )


def get_call_status() -> dict:
    cfg = get_twilio_config()
    return {
        "configured": cfg.configured,
        "fromNumber": cfg.from_number or None,
        "agentNumber": cfg.agent_number or None,
        "accountSid": (cfg.account_sid[:10] + "…") if cfg.account_sid else None,
    }


def _normalise_number(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    cleaned = (
        raw.replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )
    if cleaned.startswith("+"):
        return "+" + "".join(ch for ch in cleaned[1:] if ch.isdigit())
    return "".join(ch for ch in cleaned if ch.isdigit())


def build_connect_twiml(vendor_name: str, vendor_phone: str, caller_id: str) -> str:
    """Inline TwiML: greet the agent, then dial the vendor and bridge the call."""
    safe_name = escape(vendor_name or "the vendor")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Say voice="alice">Connecting you to {safe_name}. Please hold.</Say>'
        f"<Dial callerId={quoteattr(caller_id)} timeout=\"30\">{escape(vendor_phone)}</Dial>"
        "</Response>"
    )


def place_click_to_call(
    vendor_name: str,
    vendor_phone: str,
    agent_number: str | None = None,
) -> dict:
    """
    Ring the agent's phone, then connect them to the vendor.

    Returns {"status": "QUEUED"|"FAILED", "sid": ..., "error": ..., ...}.
    """
    cfg = get_twilio_config()
    if not cfg.configured:
        return {
            "status": "FAILED",
            "error": (
                "Twilio is not configured. Set TWILIO_ACCOUNT_SID, "
                "TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER in api/.env."
            ),
        }

    to_number = _normalise_number(agent_number or cfg.agent_number)
    vendor_num = _normalise_number(vendor_phone)
    from_number = _normalise_number(cfg.from_number)

    if not to_number:
        return {
            "status": "FAILED",
            "error": "No agent phone number to ring. Set TWILIO_AGENT_NUMBER in api/.env.",
        }
    if not vendor_num:
        return {
            "status": "FAILED",
            "error": "This vendor has no contact phone number. Add one on the vendor record first.",
        }

    twiml = build_connect_twiml(vendor_name, vendor_num, from_number)
    url = f"{TWILIO_API_BASE}/Accounts/{cfg.account_sid}/Calls.json"
    form = urllib.parse.urlencode(
        {"To": to_number, "From": from_number, "Twiml": twiml, "Record": "true"}
    ).encode("utf-8")

    auth = base64.b64encode(
        f"{cfg.account_sid}:{cfg.auth_token}".encode("utf-8")
    ).decode("ascii")
    req = urllib.request.Request(url, data=form, method="POST")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return {
            "status": "QUEUED",
            "sid": body.get("sid"),
            "to": to_number,
            "vendor": vendor_num,
            "twilioStatus": body.get("status"),
        }
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            return {
                "status": "FAILED",
                "error": err_body.get("message") or str(e),
                "code": err_body.get("code"),
                "more_info": err_body.get("more_info"),
            }
        except Exception:
            return {"status": "FAILED", "error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": "FAILED", "error": str(e)}


def _auth_header() -> str:
    cfg = get_twilio_config()
    token = base64.b64encode(
        f"{cfg.account_sid}:{cfg.auth_token}".encode("utf-8")
    ).decode("ascii")
    return f"Basic {token}"


def list_recordings(limit: int = 20) -> dict:
    cfg = get_twilio_config()
    if not cfg.configured:
        return {"configured": False, "recordings": []}
    url = f"{TWILIO_API_BASE}/Accounts/{cfg.account_sid}/Recordings.json?PageSize={int(limit)}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", _auth_header())
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"configured": True, "recordings": [], "error": str(e)}
    out = []
    for r in data.get("recordings", []):
        out.append({
            "sid": r.get("sid"),
            "call_sid": r.get("call_sid"),
            "duration": r.get("duration"),
            "date_created": r.get("date_created"),
            "status": r.get("status"),
        })
    return {"configured": True, "recordings": out}


def fetch_recording_media(rec_sid: str) -> bytes:
    cfg = get_twilio_config()
    url = f"{TWILIO_API_BASE}/Accounts/{cfg.account_sid}/Recordings/{rec_sid}.mp3"
    req = urllib.request.Request(url)
    req.add_header("Authorization", _auth_header())
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()
