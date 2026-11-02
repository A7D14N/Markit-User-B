from __future__ import annotations

import base64
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
GUIDES_FILE = ROOT / "data" / "guides.json"
STOP_WORDS = {"a", "an", "and", "for", "from", "how", "in", "of", "on", "the", "to", "with"}
LOCAL_ALLOWED_DOMAINS = [
    "statom.co.uk",
    "frankifoundations.co.uk",
    "st-mep.co.uk",
    "slipform.co.uk",
]
SOFTWARE_OPTIONS = {
    "Bluebeam": "bluebeam",
    "Adobe": "adobe",
    "Other / New user": "other",
}

st.set_page_config(
    page_title="Markit PDF | Statom",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      :root { color-scheme: dark; }
      .stApp { background: #151515; color: #f4f4f4; }
      [data-testid="stHeader"] { background: rgba(21,21,21,0); }
      [data-testid="stMainBlockContainer"] { max-width: 1440px; padding-top: 1.2rem; padding-bottom: 4rem; }
      [data-testid="stToolbar"] { right: 1rem; }
      h1, h2, h3, p, label { color: #f4f4f4; }
      .section-heading { margin: 1.7rem 0 .75rem 0; }
      .section-kicker { color: #FFC72D; font-size: .72rem; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; margin-bottom: .3rem; }
      .section-title { color: #f5f5f5; font-size: 1.55rem; line-height: 1.25; font-weight: 680; margin: 0; }
      .section-hint { color: #A9A9A9; font-size: .92rem; margin-top: .35rem; }
      .download-link-wrap { display: flex; justify-content: center; margin: 1.15rem 0 2.45rem; }
      .download-link { display: inline-block; color: #F3F3F3 !important; font-size: 1rem; font-weight: 650; letter-spacing: .01em; text-decoration: none !important; padding: .35rem .1rem .42rem; border-bottom: 1px solid transparent; transition: color .16s ease, border-color .16s ease; }
      .download-link:hover, .download-link:focus-visible { color: #FFC72D !important; border-bottom-color: #FFC72D; }
      .search-area { margin-top: .15rem; }
      div[data-testid="stTextInput"] { margin-top: .4rem; }
      div[data-testid="stTextInput"] [data-baseweb="input"] { background: #1D1D1D !important; border: 1px solid #3B3B3B !important; border-radius: 11px !important; box-shadow: none !important; min-height: 3.25rem; transition: border-color .16s ease, box-shadow .16s ease; }
      div[data-testid="stTextInput"] [data-baseweb="input"]:focus-within { border-color: #FFC72D !important; box-shadow: 0 0 0 2px rgba(255,199,45,.13) !important; }
      div[data-testid="stTextInput"] input { background: transparent !important; color: #F4F4F4 !important; min-height: 3.1rem; font-size: .98rem; padding-left: 1rem; }
      div[data-testid="stTextInput"] input::placeholder { color: #858585 !important; opacity: 1; }
      .guide-card { background: #1D1D1D; border: 1px solid #353535; border-radius: 11px; padding: 1rem 1.1rem; margin: .35rem 0 .55rem; min-height: 88px; }
      .guide-card-title { color: #F5F5F5; font-weight: 680; font-size: .98rem; }
      .guide-description { color: #B6B6B6; font-size: .9rem; line-height: 1.5; margin-top: .35rem; }
      .small-note { color: #A8A8A8; font-size: .82rem; }
      div.stButton > button, div.stDownloadButton > button, div.stLinkButton > a { border-radius: 8px; min-height: 2.55rem; font-weight: 600; }
      div.stButton > button[kind="primary"], div.stLinkButton > a[kind="primary"] { background: #FFC72D; border: 1px solid #FFC72D; color: #171717; }
      div.stButton > button[kind="primary"]:hover, div.stLinkButton > a[kind="primary"]:hover { background: #FFC72D; border-color: #FFC72D; color: #171717; }
      div.stButton > button[kind="secondary"] { background: #202020; border: 1px solid #444; color: #F0F0F0; }
      div.stButton > button[kind="secondary"]:hover { border-color: #FFC72D; color: #FFC72D; }
      div[data-testid="stForm"] { background: #202020; border: 1px solid #383838; border-radius: 12px; padding: 1rem 1.2rem; }
      div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { background: #242424; }
      div[data-testid="stNumberInput"] input { background: #242424; }
      hr { border-color: #383838; }
      a { color: #FFC72D; }
      footer { visibility: hidden; }
      @media (max-width: 640px) {
        [data-testid="stMainBlockContainer"] { padding-left: 1rem; padding-right: 1rem; }
        .section-title { font-size: 1.35rem; }
        .download-link-wrap { margin-bottom: 1.9rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_supabase_settings() -> dict[str, str]:
    """Read server-side Supabase credentials without breaking local preview mode."""
    try:
        section = st.secrets.get("supabase", {})
        return {
            "url": str(section.get("url", "")).strip(),
            "anon_key": str(
                section.get("anon_key", section.get("publishable_key", section.get("key", "")))
            ).strip(),
            "service_role_key": str(
                section.get("service_role_key", section.get("secret_key", ""))
            ).strip(),
        }
    except Exception:
        return {"url": "", "anon_key": "", "service_role_key": ""}


def supabase_is_configured() -> bool:
    settings = get_supabase_settings()
    return bool(settings["url"] and settings["anon_key"])


def supabase_server_is_configured() -> bool:
    settings = get_supabase_settings()
    return bool(settings["url"] and settings["service_role_key"])


def create_supabase_client(*, service_role: bool = False, session_prefix: str | None = None):
    """Create a per-session client. Service-role clients are used only by this server process."""
    settings = get_supabase_settings()
    key = settings["service_role_key"] if service_role else settings["anon_key"]
    if not settings["url"] or not key:
        label = "server-side service_role_key" if service_role else "publishable/anon key"
        raise RuntimeError(f"Supabase {label} is missing from .streamlit/secrets.toml.")
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(
            "The Supabase package is not installed. Close the portal and run run_local.bat again."
        ) from exc
    client = create_client(settings["url"], key)
    if session_prefix:
        access = st.session_state.get(f"{session_prefix}_access_token")
        refresh = st.session_state.get(f"{session_prefix}_refresh_token")
        if not access or not refresh:
            raise RuntimeError("Your admin session has expired. Please sign in again.")
        client.auth.set_session(access, refresh)
        try:
            active_session = client.auth.get_session()
            if active_session:
                st.session_state[f"{session_prefix}_access_token"] = _value(
                    active_session, "access_token", access
                )
                st.session_state[f"{session_prefix}_refresh_token"] = _value(
                    active_session, "refresh_token", refresh
                )
        except Exception:
            pass
    return client


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def extract_rows(response: Any) -> list[dict[str, Any]]:
    data = _value(response, "data", []) or []
    if isinstance(data, dict):
        return [data]
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def remember_auth_session(response: Any, prefix: str) -> None:
    session = _value(response, "session")
    if not session:
        raise RuntimeError("Supabase did not return a login session. Please try again.")
    st.session_state[f"{prefix}_access_token"] = _value(session, "access_token")
    st.session_state[f"{prefix}_refresh_token"] = _value(session, "refresh_token")
    user = _value(response, "user") or _value(session, "user")
    st.session_state[f"{prefix}_user_id"] = _value(user, "id")
    st.session_state[f"{prefix}_email"] = _value(user, "email")


def clear_auth_session(prefix: str) -> None:
    for name in ("access_token", "refresh_token", "user_id", "email"):
        st.session_state.pop(f"{prefix}_{name}", None)


def load_guides() -> list[dict[str, Any]]:
    try:
        raw = json.loads(GUIDES_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict) and item.get("published", True)]
    except (OSError, json.JSONDecodeError):
        return []


def normalise(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _normalise_asset_stem(value: str) -> str:
    stem = normalise(Path(value).stem)
    if stem.startswith("guide "):
        stem = stem[6:]
    return stem


def safe_asset_path(relative_path: str | None) -> Path | None:
    if not relative_path:
        return None
    candidate = (ASSETS / relative_path).resolve()
    try:
        candidate.relative_to(ASSETS.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() and candidate.suffix.lower() == ".svg" else None


def find_guide_asset(guide: dict[str, Any]) -> Path | None:
    direct = safe_asset_path(str(guide.get("asset", "")))
    if direct:
        return direct
    aliases = [
        str(guide.get("title", "")),
        str(guide.get("slug", "")).replace("-", " "),
        *[str(value) for value in guide.get("filename_aliases", [])],
    ]
    wanted = {_normalise_asset_stem(value) for value in aliases if value.strip()}
    wanted.discard("")
    if not wanted or not ASSETS.exists():
        return None
    for candidate in sorted(ASSETS.rglob("*.svg")):
        if candidate.name.casefold() == "main_homepage_markit.svg":
            continue
        if _normalise_asset_stem(candidate.name) in wanted:
            return candidate
    return None


def display_svg(path: Path, *, alt: str, max_width: str = "100%") -> None:
    if not path.is_file():
        st.warning(f"Artwork not found: {path.name}")
        return
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    safe_alt = html.escape(alt, quote=True)
    st.markdown(
        '<div style="width:100%;text-align:center;overflow:hidden;">'
        f'<img src="data:image/svg+xml;base64,{encoded}" alt="{safe_alt}" '
        f'style="display:block;width:100%;max-width:{max_width};height:auto;margin:0 auto;">'
        "</div>",
        unsafe_allow_html=True,
    )


def guide_search_score(query: str, guide: dict[str, Any]) -> int:
    q = normalise(query)
    if not q:
        return 0
    fields = [str(guide.get("title", "")), str(guide.get("description", ""))]
    fields += [str(item) for item in guide.get("keywords", [])]
    haystack = normalise(" ".join(fields))
    score = 10 if q in haystack else 0
    for token in (token for token in q.split() if token not in STOP_WORDS):
        if token in haystack:
            score += 3
    if q in normalise(str(guide.get("title", ""))):
        score += 8
    return score


def valid_email(email: str) -> bool:
    email = email.strip().casefold()
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email))


def email_is_allowed(email: str) -> bool:
    """Use the database allow-list when connected; local list is preview-only."""
    email = email.strip().casefold()
    if not valid_email(email):
        return False
    if not supabase_is_configured():
        return email.rsplit("@", 1)[1] in LOCAL_ALLOWED_DOMAINS
    try:
        client = create_supabase_client()
        result = client.rpc("is_approved_company_email", {"p_email": email}).execute()
        return bool(_value(result, "data", False))
    except Exception as exc:
        raise RuntimeError(f"The company-domain check could not reach Supabase: {exc}") from exc


def register_employee(full_name: str, email: str, software_replaced: str) -> dict[str, Any]:
    """Save an employee using the server key; an existing email is never overwritten."""
    if not supabase_server_is_configured():
        raise RuntimeError("The Supabase server-side service role key has not been added yet.")
    client = create_supabase_client(service_role=True)
    email = email.strip().casefold()
    existing = extract_rows(
        client.table("employees")
        .select("id,full_name,email,company_domain,software_replaced,created_at")
        .eq("email", email)
        .limit(1)
        .execute()
    )
    if existing:
        return existing[0]

    domain = email.rsplit("@", 1)[1]
    payload = {
        "full_name": full_name.strip(),
        "email": email,
        "company_domain": domain,
        "software_replaced": software_replaced,
    }
    try:
        client.table("employees").insert(payload).execute()
        created = extract_rows(
            client.table("employees")
            .select("id,full_name,email,company_domain,software_replaced,created_at")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        if created:
            return created[0]
    except Exception:
        # A simultaneous repeat submission may have inserted the unique email first.
        existing = extract_rows(
            client.table("employees")
            .select("id,full_name,email,company_domain,software_replaced,created_at")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        if existing:
            return existing[0]
        raise
    raise RuntimeError("Supabase did not return the employee record after saving it.")


def get_active_installer(client: Any) -> dict[str, Any] | None:
    rows = extract_rows(
        client.table("installer_releases")
        .select("id,version,download_url,delivery_provider,is_active,created_at")
        .eq("is_active", True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return rows[0] if rows else None


def create_download_link(employee: dict[str, Any]) -> str:
    if not supabase_server_is_configured():
        raise RuntimeError("The Supabase server-side service role key has not been added yet.")
    client = create_supabase_client(service_role=True)
    release = get_active_installer(client)
    if not release or not release.get("download_url"):
        raise RuntimeError("The installer link has not been configured by the portal administrator yet.")
    client.table("downloads").insert(
        {
            "employee_id": employee["id"],
            "email_snapshot": employee["email"],
            "installer_version": release["version"],
            "delivery_provider": release.get("delivery_provider") or "dropbox",
        }
    ).execute()
    return str(release["download_url"])


def show_guide(guide: dict[str, Any]) -> None:
    title = str(guide.get("title", "Untitled guide"))
    if st.button("← Back to all guides", type="secondary"):
        st.session_state.pop("selected_guide", None)
        st.rerun()
    st.markdown(f"<div class='section-title'>{html.escape(title)}</div>", unsafe_allow_html=True)
    description = str(guide.get("description", ""))
    if description:
        st.markdown(f"<p class='small-note'>{html.escape(description)}</p>", unsafe_allow_html=True)
    asset = find_guide_asset(guide)
    if asset:
        display_svg(asset, alt=title)
    else:
        st.warning(f"Guide artwork not found for '{title}'. Check the SVG filename under assets/.")


def show_local_download_form() -> None:
    st.markdown(
        "<div class='section-heading'><div class='section-kicker'>MARKIT PDF</div>"
        "<div class='section-title'>Download access</div>"
        "<div class='section-hint'>Enter your details to check your company email.</div></div>",
        unsafe_allow_html=True,
    )
    with st.form("local_download_registration"):
        full_name = st.text_input("Full name", placeholder="Your name")
        email = st.text_input("Company email", placeholder="you@statom.co.uk")
        replacement_label = st.selectbox("Which software would Markit replace?", list(SOFTWARE_OPTIONS))
        submitted = st.form_submit_button("Continue", type="primary", use_container_width=True)
    if submitted:
        if not full_name.strip():
            st.error("Please enter your name.")
        elif not email_is_allowed(email):
            st.error("Please use an approved company email address.")
        else:
            st.success("The company-domain check works in local preview mode.")
            st.info("The portal is not connected to Supabase yet, so this preview does not save details or release the installer.")
    st.caption("The company-domain check checks the address suffix only; it does not verify ownership of the mailbox.")


def show_employee_download() -> None:
    employee = st.session_state.get("portal_employee")
    if not employee:
        return
    st.success(f"Company email accepted: {employee.get('email', '')}")
    st.caption("Your registration is saved. Repeated visits with the same email do not overwrite your original details.")
    if st.button("Get Markit PDF installer link", type="primary", use_container_width=True):
        try:
            url = create_download_link(employee)
            st.session_state["portal_installer_url"] = url
            st.success("Your installer link is ready.")
        except Exception as exc:
            st.error(f"Unable to issue the installer link: {exc}")
    url = st.session_state.get("portal_installer_url")
    if url:
        st.link_button("Open Markit PDF installer in Dropbox", url, type="primary", use_container_width=True)
        st.caption("The portal records when the Dropbox link is issued. Dropbox may allow the shared link to be forwarded.")
    if st.button("Use a different email address", type="secondary"):
        st.session_state.pop("portal_employee", None)
        st.session_state.pop("portal_installer_url", None)
        st.rerun()


def show_connected_download_form() -> None:
    st.markdown(
        "<div class='section-heading'><div class='section-kicker'>MARKIT PDF</div>"
        "<div class='section-title'>Download access</div>"
        "<div class='section-hint'>Enter your details to check your company email.</div></div>",
        unsafe_allow_html=True,
    )
    if st.session_state.get("portal_employee"):
        show_employee_download()
        return

    with st.form("download_registration_connected"):
        full_name = st.text_input("Full name", placeholder="Your name")
        email = st.text_input("Company email", placeholder="you@statom.co.uk")
        replacement_label = st.selectbox("Which software would Markit replace?", list(SOFTWARE_OPTIONS))
        acknowledged = st.checkbox("I understand these details will be stored for internal Markit rollout reporting.")
        submitted = st.form_submit_button("Continue", type="primary", use_container_width=True)
    if submitted:
        clean_email = email.strip().casefold()
        if len(full_name.strip()) < 2:
            st.error("Please enter your full name.")
        elif not valid_email(clean_email):
            st.error("Please enter a valid work email address.")
        elif not acknowledged:
            st.error("Please confirm the data-use notice to continue.")
        else:
            try:
                if not email_is_allowed(clean_email):
                    st.error("That email domain is not currently approved.")
                else:
                    employee = register_employee(
                        full_name.strip(),
                        clean_email,
                        SOFTWARE_OPTIONS[replacement_label],
                    )
                    st.session_state["portal_employee"] = employee
                    st.session_state.pop("portal_installer_url", None)
                    st.success("Your company email is approved and your details have been saved.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Could not complete your registration: {exc}")
    st.caption("The domain check checks the email suffix only; it does not verify mailbox ownership. Your details are used for internal Markit rollout and software-adoption reporting.")


def show_download_registration() -> None:
    if st.button("Close download", key="close_download_panel", type="secondary"):
        st.query_params.clear()
        st.rerun()
    if supabase_is_configured():
        show_connected_download_form()
    else:
        show_local_download_form()


def format_currency(value: float) -> str:
    return f"£{value:,.2f}" if value % 1 else f"£{value:,.0f}"


def admin_user_client():
    """Return an authenticated client only after RLS confirms admin membership."""
    client = create_supabase_client(session_prefix="admin")
    user_id = st.session_state.get("admin_user_id")
    if not user_id:
        clear_auth_session("admin")
        raise RuntimeError("Please sign in again.")
    rows = extract_rows(
        client.table("admin_users")
        .select("user_id,email,display_name")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not rows:
        clear_auth_session("admin")
        raise RuntimeError("This account is not authorised as a Markit Portal administrator.")
    return client


def show_admin_login() -> None:
    st.markdown(
        "<div class='section-kicker'>MARKIT PORTAL</div><div class='section-title'>Administrator sign in</div>",
        unsafe_allow_html=True,
    )
    if not supabase_is_configured():
        st.warning("Connect Supabase to enable administrator sign-in.")
        return
    with st.form("admin_login_form"):
        email = st.text_input("Administrator email", placeholder="helpdesk@statom.co.uk")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        try:
            client = create_supabase_client()
            response = client.auth.sign_in_with_password(
                {"email": email.strip().casefold(), "password": password}
            )
            remember_auth_session(response, "admin")
            admin_user_client()
            st.success("Signed in.")
            st.rerun()
        except Exception as exc:
            clear_auth_session("admin")
            st.error(f"Administrator sign-in failed: {exc}")


def show_admin_dashboard() -> None:
    st.markdown(
        "<div class='section-kicker'>MARKIT PORTAL</div><div class='section-title'>Admin dashboard</div>",
        unsafe_allow_html=True,
    )
    if not supabase_is_configured():
        st.warning("Connect Supabase to enable the administrator dashboard.")
        return
    if not st.session_state.get("admin_access_token"):
        show_admin_login()
        return

    try:
        client = admin_user_client()
        employees = extract_rows(
            client.table("employees")
            .select("id,full_name,email,company_domain,software_replaced,created_at")
            .order("created_at", desc=True)
            .execute()
        )
        downloads = extract_rows(
            client.table("downloads")
            .select("id,employee_id,email_snapshot,installer_version,delivery_provider,created_at")
            .order("created_at", desc=True)
            .execute()
        )
        domains = extract_rows(
            client.table("allowed_domains")
            .select("domain,company_name,is_active")
            .order("domain")
            .execute()
        )
        prices_rows = extract_rows(
            client.table("software_prices")
            .select("software_key,annual_cost,currency")
            .execute()
        )
        active_release = get_active_installer(client)
    except Exception as exc:
        st.error(f"Could not load admin data: {exc}")
        if st.button("Sign out", key="admin_data_error_signout"):
            clear_auth_session("admin")
            st.rerun()
        return

    prices = {row["software_key"]: float(row["annual_cost"]) for row in prices_rows}
    bluebeam_price = prices.get("bluebeam", 330.00)
    adobe_price = prices.get("adobe", 238.75)
    bluebeam_count = sum(1 for row in employees if row.get("software_replaced") == "bluebeam")
    adobe_count = sum(1 for row in employees if row.get("software_replaced") == "adobe")
    other_count = sum(1 for row in employees if row.get("software_replaced") not in {"bluebeam", "adobe"})
    estimated_savings = bluebeam_count * bluebeam_price + adobe_count * adobe_price

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Registered employees", len(employees))
    m2.metric("Bluebeam replaced", bluebeam_count)
    m3.metric("Adobe replaced", adobe_count)
    m4.metric("Estimated annual savings", format_currency(estimated_savings))
    st.caption(
        "Estimated potential annual licence savings, using the costs below. This does not deduct Markit's cost or confirm that old licences have been cancelled. Each employee email is counted once."
    )

    left, right = st.columns([1.35, 1])
    with left:
        st.subheader("Employee registrations")
        if employees:
            employee_view = [
                {
                    "Name": row.get("full_name"),
                    "Email": row.get("email"),
                    "Company": row.get("company_domain"),
                    "Software replaced": str(row.get("software_replaced", "")).replace("_", " ").title(),
                    "Registered": row.get("created_at"),
                }
                for row in employees
            ]
            st.dataframe(employee_view, use_container_width=True, hide_index=True)
        else:
            st.info("No employee registrations yet.")
    with right:
        st.subheader("Software adoption")
        st.metric("Bluebeam", bluebeam_count, help=f"Estimated annual value: {format_currency(bluebeam_count * bluebeam_price)}")
        st.metric("Adobe", adobe_count, help=f"Estimated annual value: {format_currency(adobe_count * adobe_price)}")
        st.metric("Other / new user", other_count)

    st.subheader("Download history")
    if downloads:
        employee_by_id = {row["id"]: row for row in employees}
        history = [
            {
                "Employee": employee_by_id.get(row.get("employee_id"), {}).get("full_name", "Unknown"),
                "Email": row.get("email_snapshot"),
                "Installer version": row.get("installer_version"),
                "Delivery": row.get("delivery_provider"),
                "Link issued": row.get("created_at"),
            }
            for row in downloads
        ]
        st.dataframe(history, use_container_width=True, hide_index=True)
        st.caption("This records when the portal issued the Dropbox link, not whether the browser completed the download.")
    else:
        st.info("No installer links have been issued yet.")

    st.divider()
    st.subheader("Approved company domains")
    if domains:
        st.dataframe(
            [{"Domain": row["domain"], "Company": row.get("company_name", ""), "Active": row.get("is_active", True)} for row in domains],
            use_container_width=True,
            hide_index=True,
        )
    with st.form("add_allowed_domain_form"):
        new_domain = st.text_input("Add company domain", placeholder="example.co.uk").strip().casefold()
        new_company = st.text_input("Company name", placeholder="Example Company").strip()
        add_domain = st.form_submit_button("Add approved domain", type="primary")
    if add_domain:
        if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", new_domain) or ".." in new_domain or new_domain.startswith(".") or new_domain.endswith("."):
            st.error("Enter a valid domain without @, for example example.co.uk.")
        elif not new_company:
            st.error("Enter the company name for this domain.")
        else:
            try:
                client.table("allowed_domains").insert(
                    {"domain": new_domain, "company_name": new_company, "is_active": True}
                ).execute()
                st.success(f"Added {new_domain}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not add domain. It may already exist. Details: {exc}")

    active_domains = [row for row in domains]
    if active_domains:
        domain_labels = {
            f"{row['domain']} — {'Active' if row.get('is_active') else 'Inactive'}": row
            for row in active_domains
        }
        with st.form("edit_domain_status_form"):
            selected_label = st.selectbox("Choose a domain to enable or disable", list(domain_labels))
            selected_domain = domain_labels[selected_label]
            new_active_status = st.checkbox("Domain is approved for downloads", value=bool(selected_domain.get("is_active", True)))
            update_domain = st.form_submit_button("Save domain status")
        if update_domain:
            try:
                client.table("allowed_domains").update({"is_active": new_active_status}).eq(
                    "domain", selected_domain["domain"]
                ).execute()
                st.success(f"Updated {selected_domain['domain']}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not update domain: {exc}")

    st.divider()
    st.subheader("Annual software costs")
    with st.form("software_prices_form"):
        p1, p2 = st.columns(2)
        with p1:
            bluebeam_new_price = st.number_input("Bluebeam (£ / year)", min_value=0.0, value=bluebeam_price, step=5.0, format="%.2f")
        with p2:
            adobe_new_price = st.number_input("Adobe (£ / year)", min_value=0.0, value=adobe_price, step=5.0, format="%.2f")
        save_prices = st.form_submit_button("Save annual costs", type="primary")
    if save_prices:
        try:
            client.table("software_prices").update({"annual_cost": bluebeam_new_price}).eq("software_key", "bluebeam").execute()
            client.table("software_prices").update({"annual_cost": adobe_new_price}).eq("software_key", "adobe").execute()
            st.success("Annual software costs updated.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not update software costs: {exc}")

    st.divider()
    st.subheader("Dropbox installer link")
    st.caption("Set the version label and the Dropbox shared link that approved employees should receive.")
    with st.form("installer_release_form"):
        installer_version = st.text_input(
            "Installer version",
            value=str(active_release.get("version", "")) if active_release else "",
            placeholder="Enter the current version",
        ).strip()
        installer_url = st.text_input(
            "Dropbox shared link",
            value=str(active_release.get("download_url", "")) if active_release else "",
            placeholder="Paste the Dropbox folder or installer link",
        ).strip()
        save_installer = st.form_submit_button("Save active installer link", type="primary")
    if save_installer:
        if not installer_version:
            st.error("Enter the installer version (or a simple label such as Current).")
        elif not installer_url.startswith("https://www.dropbox.com/"):
            st.error("Enter a valid Dropbox HTTPS shared link.")
        else:
            try:
                payload = {
                    "version": installer_version,
                    "download_url": installer_url,
                    "delivery_provider": "dropbox",
                    "is_active": True,
                }
                if active_release:
                    client.table("installer_releases").update(payload).eq("id", active_release["id"]).execute()
                else:
                    client.table("installer_releases").insert(payload).execute()
                st.success("The active Dropbox installer link has been saved.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not save the installer link: {exc}")

    st.divider()
    if st.button("Sign out of admin", type="secondary"):
        try:
            create_supabase_client(session_prefix="admin").auth.sign_out()
        except Exception:
            pass
        clear_auth_session("admin")
        st.rerun()


def main() -> None:
    if st.query_params.get("admin") == "1":
        if st.button("← Back to public website", type="secondary"):
            st.query_params.clear()
            st.rerun()
        show_admin_dashboard()
        return

    selected_slug = st.session_state.get("selected_guide")
    guides = load_guides()
    if selected_slug:
        selected = next((guide for guide in guides if guide.get("slug") == selected_slug), None)
        if selected:
            show_guide(selected)
            return
        st.session_state.pop("selected_guide", None)

    homepage = ASSETS / "main_homepage_markit.svg"
    display_svg(homepage, alt="Markit PDF — Statom construction PDF software")
    st.markdown(
        "<div class='download-link-wrap'><a class='download-link' href='?show_download=1#download-registration'>Download Markit PDF</a></div>",
        unsafe_allow_html=True,
    )
    if st.query_params.get("show_download") == "1":
        show_download_registration()

    st.markdown(
        "<div class='section-heading search-area'><div class='section-kicker'>MARKIT SUPPORT</div>"
        "<div class='section-title'>Find a guide</div>"
        "<div class='section-hint'>Search by tool, task, or keyword. You can use alternative terms too.</div></div>",
        unsafe_allow_html=True,
    )
    query = st.text_input("Search guides", placeholder="e.g. Excel export, measurements, Tool Chest...", label_visibility="collapsed")
    if query.strip():
        ranked = [(guide_search_score(query, guide), guide) for guide in guides]
        matches = [guide for score, guide in sorted(ranked, key=lambda item: item[0], reverse=True) if score > 0]
        st.markdown("<div class='section-heading'><div class='section-title'>Search results</div></div>", unsafe_allow_html=True)
        if not matches:
            st.info("No matching guides yet. Try another keyword or browse all guides below.")
        for guide in matches:
            title, description = str(guide.get("title", "Untitled guide")), str(guide.get("description", ""))
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"<div class='guide-card'><div class='guide-card-title'>{html.escape(title)}</div><div class='guide-description'>{html.escape(description)}</div></div>",
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button("Open guide →", key=f"search_{guide.get('slug')}", type="secondary", use_container_width=True):
                    st.session_state["selected_guide"] = guide.get("slug")
                    st.rerun()

    st.markdown(
        "<div class='section-heading'><div class='section-title'>Browse all guides</div><div class='section-hint'>Or choose a guide from the complete library below.</div></div>",
        unsafe_allow_html=True,
    )
    if not guides:
        st.info("The guide catalogue is ready. Add guide SVGs under assets/ and they will be matched automatically.")
    else:
        columns = st.columns(1 if len(guides) == 1 else 2)
        for index, guide in enumerate(guides):
            with columns[index % len(columns)]:
                st.markdown(
                    f"<div class='guide-card'><div class='guide-card-title'>{html.escape(str(guide.get('title', 'Untitled guide')))}</div><div class='guide-description'>{html.escape(str(guide.get('description', '')))}</div></div>",
                    unsafe_allow_html=True,
                )
                if st.button("Open guide →", key=f"all_{guide.get('slug')}", type="secondary", use_container_width=True):
                    st.session_state["selected_guide"] = guide.get("slug")
                    st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<p class='small-note' style='text-align:center'>Markit PDF · Statom Group · <a href='?admin=1'>Admin</a></p>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
