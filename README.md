# Markit PDF Portal — local prototype

A separate Streamlit project for the public Markit PDF website. It does not modify or import the Markit PDF desktop application.

## What's included

- Your Figma homepage SVG displayed at the top of the page.
- A real Streamlit download-registration form.
- Local validation for the four approved company email domains.
- Keyword-based guide search (for example, `Excel to export` finds `Microsoft Office Export`).
- A reusable guide page that displays a guide SVG at its natural aspect ratio and allows normal page scrolling.
- A sample guide catalogue entry to demonstrate search. Its artwork is not included yet.
- A starter Supabase SQL schema for the next phase.

## Run locally on Windows

Open PowerShell in this `markit_portal` folder and run:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Streamlit will print a local address, normally `http://localhost:8501`. Open it in your browser.

If PowerShell blocks virtual-environment activation, use this instead after creating the environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Add a guide

1. Export the guide from Figma as SVG.
2. Copy it into `assets/guides/`.
3. Add an entry to `data/guides.json`, for example:

```json
{
  "slug": "microsoft-office-export",
  "title": "Microsoft Office Export",
  "description": "Export Markit data to Microsoft Excel.",
  "asset": "microsoft_office_export.svg",
  "keywords": ["excel", "spreadsheet", "xlsx", "export", "tables", "office"],
  "published": true
}
```

Search looks across title, description and every keyword. It ignores common filler words such as `to` and ranks complete phrase matches above individual word matches. The `slug` must be unique and URL-friendly. The SVG's height can vary; it is displayed responsively with its aspect ratio preserved.

## Local prototype limitations

This first version is deliberately local-only:

- It does not connect to Supabase yet. The optional Supabase Python SDK is listed separately in `requirements-supabase.txt` and is not required for the local prototype.
- It does not persist names or email addresses.
- It checks the email domain only; it does not prove that the visitor owns that email address.
- It does not release an installer download.
- It does not include the admin login/dashboard yet.

The local form displays a clear notice after validation. Do not use this local-only form to collect real employee information. Production registration must verify email ownership (for example using Supabase Auth OTP/magic-link verification) before creating an employee record or granting a download.

## Supabase preparation (next phase)

1. Create a new Supabase project for the portal (separate from any other company project).
2. In the Supabase SQL Editor, run `supabase/schema.sql`.
3. In Storage, create:
   - `public-guides` — public bucket for public SVG guide files.
   - `private-downloads` — private bucket for the installer. Never make this bucket public.
4. Add the initial admin account through Supabase Auth, then insert that account's user UUID into `public.admin_users` using the SQL editor. Do not use a shared hardcoded password.
5. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in the project URL and publishable/anon key. Keep `secrets.toml` out of Git. Any service-role/secret key must remain server-side only and must never be sent to browser code.

The app currently runs without Supabase secrets. Supabase integration will be added only after the local layout and guide catalogue are confirmed.

## Production security requirements before launch

- Verify employee email ownership before registration/download.
- Enforce the allowed-domain check server-side against `allowed_domains` (not only in the form).
- Use unique lower-case employee email records; do not overwrite a prior registration on repeat download. Record repeat downloads separately in `downloads`.
- Keep the installer in private storage and issue short-lived signed download URLs only after verification.
- Protect administrator pages and all employee/download data with Supabase Auth and Row Level Security.
- Store secrets in the hosting provider's secret manager, not in source control.
- Confirm the organisation is authorised to distribute the installer and any bundled third-party components.

You can also double-click `run_local.bat` in File Explorer. The first run creates a project-local virtual environment and installs Streamlit; later runs reuse it. The Supabase SDK is intentionally kept separate until the database integration phase.
