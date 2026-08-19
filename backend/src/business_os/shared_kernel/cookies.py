"""Session-cookie SameSite/Secure policy shared by every cookie-issuing
session (tenant `sf_session`, Vendor Control Plane `sf_platform_session`).

A cross-origin deployment (frontend and backend as separate Render services)
only gets the session cookie attached to its `fetch(..., credentials:
"include")` calls if the cookie is `SameSite=None` — and browsers reject
`SameSite=None` outright unless it's paired with `Secure`. Local dev keeps
`SameSite=Lax` and drops `Secure` instead: `debug` traffic is plain-HTTP
`localhost`, where a `Secure` cookie would never be sent at all, and
same-origin (via the Vite proxy) makes `Lax` sufficient there anyway.
"""

from typing import Literal, TypedDict


class CookiePolicy(TypedDict):
    secure: bool
    samesite: Literal["lax", "none"]


def session_cookie_policy(*, debug: bool) -> CookiePolicy:
    if debug:
        return {"secure": False, "samesite": "lax"}
    return {"secure": True, "samesite": "none"}
