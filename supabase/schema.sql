-- Markit Portal: initial Supabase schema
-- Run once in Supabase Dashboard > SQL Editor > New query.
-- This script creates application tables, RLS policies, and safe server-side RPCs.
-- It does NOT create Auth users, configure email delivery, or upload installer files.

begin;

create table if not exists public.allowed_domains (
    domain text primary key check (domain = lower(trim(domain)) and position('@' in domain) = 0),
    company_name text not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

insert into public.allowed_domains (domain, company_name)
values
    ('statom.co.uk', 'Statom Group'),
    ('frankifoundations.co.uk', 'Franki Foundations'),
    ('st-mep.co.uk', 'ST-MEP'),
    ('slipform.co.uk', 'Slipform')
on conflict (domain) do nothing;

create table if not exists public.employees (
    id uuid primary key default gen_random_uuid(),
    full_name text not null check (length(trim(full_name)) between 2 and 160),
    email text not null unique check (email = lower(trim(email))),
    company_domain text not null references public.allowed_domains(domain),
    software_replaced text not null check (software_replaced in ('bluebeam', 'adobe', 'other', 'none')),
    created_at timestamptz not null default now()
);

create table if not exists public.downloads (
    id uuid primary key default gen_random_uuid(),
    employee_id uuid not null references public.employees(id) on delete restrict,
    email_snapshot text not null,
    installer_version text not null,
    delivery_provider text not null default 'dropbox' check (delivery_provider in ('dropbox', 'supabase')),
    created_at timestamptz not null default now()
);

create index if not exists downloads_created_at_idx on public.downloads (created_at desc);
create index if not exists downloads_email_idx on public.downloads (email_snapshot);

create table if not exists public.guides (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    slug text not null unique,
    description text not null default '',
    file_path text not null,
    keywords text[] not null default '{}',
    category text not null default 'General',
    is_published boolean not null default false,
    sort_order integer not null default 100,
    created_at timestamptz not null default now()
);

create table if not exists public.admin_users (
    user_id uuid primary key references auth.users(id) on delete cascade,
    email text not null unique check (email = lower(trim(email))),
    display_name text not null default '',
    created_at timestamptz not null default now()
);

create table if not exists public.software_prices (
    software_key text primary key check (software_key in ('bluebeam', 'adobe')),
    annual_cost numeric(10,2) not null check (annual_cost >= 0),
    currency text not null default 'GBP' check (currency = 'GBP'),
    updated_at timestamptz not null default now()
);

insert into public.software_prices (software_key, annual_cost)
values ('bluebeam', 330.00), ('adobe', 238.75)
on conflict (software_key) do nothing;

create table if not exists public.installer_releases (
    id uuid primary key default gen_random_uuid(),
    version text not null,
    download_url text not null,
    delivery_provider text not null default 'dropbox' check (delivery_provider in ('dropbox', 'supabase')),
    is_active boolean not null default false,
    created_at timestamptz not null default now()
);

create unique index if not exists installer_releases_one_active_idx
    on public.installer_releases (is_active)
    where is_active = true;

-- Explicitly enable RLS even when the project's automatic-RLS option is enabled.
alter table public.allowed_domains enable row level security;
alter table public.employees enable row level security;
alter table public.downloads enable row level security;
alter table public.guides enable row level security;
alter table public.admin_users enable row level security;
alter table public.software_prices enable row level security;
alter table public.installer_releases enable row level security;

-- A SECURITY DEFINER helper avoids recursive RLS checks on admin_users.
create or replace function public.is_portal_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.admin_users au
        where au.user_id = auth.uid()
    );
$$;

revoke all on function public.is_portal_admin() from public;
grant execute on function public.is_portal_admin() to anon, authenticated;

-- Publicly callable domain check reveals only whether a domain is approved,
-- not the domain list or any employee data.
create or replace function public.is_approved_company_email(p_email text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.allowed_domains d
        where d.domain = lower(split_part(trim(coalesce(p_email, '')), '@', 2))
          and d.is_active = true
          and position('@' in trim(coalesce(p_email, ''))) > 1
          and length(trim(coalesce(p_email, ''))) -
              length(replace(trim(coalesce(p_email, '')), '@', '')) = 1
    );
$$;

revoke all on function public.is_approved_company_email(text) from public;
grant execute on function public.is_approved_company_email(text) to anon, authenticated;

-- Called only after Supabase Auth has verified the employee's email.
-- On duplicate email, the original employee row is deliberately left unchanged.
create or replace function public.register_portal_employee(
    p_full_name text,
    p_software_replaced text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_email text;
    v_domain text;
    v_employee_id uuid;
begin
    if auth.uid() is null then
        raise exception 'Email verification is required.' using errcode = '28000';
    end if;

    v_email := lower(trim(coalesce(auth.jwt() ->> 'email', '')));
    v_domain := lower(split_part(v_email, '@', 2));

    if v_email = '' or position('@' in v_email) < 2 then
        raise exception 'A valid verified email address is required.' using errcode = '22023';
    end if;

    if not public.is_approved_company_email(v_email) then
        raise exception 'This email domain is not authorised to download Markit PDF.' using errcode = '42501';
    end if;

    if length(trim(coalesce(p_full_name, ''))) not between 2 and 160 then
        raise exception 'Please enter your full name.' using errcode = '22023';
    end if;

    if p_software_replaced is null or p_software_replaced not in ('bluebeam', 'adobe', 'other', 'none') then
        raise exception 'Please select a valid software option.' using errcode = '22023';
    end if;

    insert into public.employees (full_name, email, company_domain, software_replaced)
    values (trim(p_full_name), v_email, v_domain, p_software_replaced)
    on conflict (email) do nothing
    returning id into v_employee_id;

    if v_employee_id is null then
        select e.id into v_employee_id
        from public.employees e
        where e.email = v_email;
    end if;

    return v_employee_id;
end;
$$;

revoke all on function public.register_portal_employee(text, text) from public;
grant execute on function public.register_portal_employee(text, text) to authenticated;

-- Creates a download audit record and returns the current installer link.
-- The Dropbox link itself can still be forwarded; see setup notes before launch.
create or replace function public.issue_markit_download()
returns table (installer_version text, download_url text, delivery_provider text)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_email text;
    v_employee_id uuid;
    v_version text;
    v_url text;
    v_provider text;
begin
    if auth.uid() is null then
        raise exception 'Please verify your company email first.' using errcode = '28000';
    end if;

    v_email := lower(trim(coalesce(auth.jwt() ->> 'email', '')));

    if not public.is_approved_company_email(v_email) then
        raise exception 'This email domain is not authorised to download Markit PDF.' using errcode = '42501';
    end if;

    select e.id into v_employee_id
    from public.employees e
    where e.email = v_email;

    if v_employee_id is null then
        raise exception 'Please complete employee registration before downloading.' using errcode = '42501';
    end if;

    select r.version, r.download_url, r.delivery_provider
      into v_version, v_url, v_provider
    from public.installer_releases r
    where r.is_active = true
    order by r.created_at desc
    limit 1;

    if v_url is null then
        raise exception 'The Markit PDF installer is not available yet.' using errcode = 'P0002';
    end if;

    insert into public.downloads (employee_id, email_snapshot, installer_version, delivery_provider)
    values (v_employee_id, v_email, v_version, v_provider);

    return query select v_version, v_url, v_provider;
end;
$$;

revoke all on function public.issue_markit_download() from public;
grant execute on function public.issue_markit_download() to authenticated;

-- Employee read access: each verified user can view only their own registration/download history.
create policy employees_read_own_or_admin
on public.employees for select to authenticated
using (email = lower(coalesce(auth.jwt() ->> 'email', '')) or public.is_portal_admin());

create policy downloads_read_own_or_admin
on public.downloads for select to authenticated
using (email_snapshot = lower(coalesce(auth.jwt() ->> 'email', '')) or public.is_portal_admin());

-- Published guides are public; admins can manage all guide entries.
create policy guides_public_read_published
on public.guides for select to anon, authenticated
using (is_published = true or public.is_portal_admin());
create policy guides_admin_manage
on public.guides for all to authenticated
using (public.is_portal_admin())
with check (public.is_portal_admin());

-- Admin accounts can read their own membership row; administrators can manage the list.
create policy admin_users_read_self_or_admin
on public.admin_users for select to authenticated
using (user_id = auth.uid() or public.is_portal_admin());
create policy admin_users_admin_manage
on public.admin_users for all to authenticated
using (public.is_portal_admin())
with check (public.is_portal_admin());

create policy allowed_domains_admin_manage
on public.allowed_domains for all to authenticated
using (public.is_portal_admin())
with check (public.is_portal_admin());

create policy software_prices_public_read
on public.software_prices for select to anon, authenticated
using (true);
create policy software_prices_admin_manage
on public.software_prices for all to authenticated
using (public.is_portal_admin())
with check (public.is_portal_admin());

create policy installer_releases_admin_manage
on public.installer_releases for all to authenticated
using (public.is_portal_admin())
with check (public.is_portal_admin());

-- Minimal table grants. Writes to employee/download tables occur through the RPCs above.
grant usage on schema public to anon, authenticated;
grant select on public.guides to anon, authenticated;
grant select on public.software_prices to anon, authenticated;
grant select on public.employees, public.downloads, public.admin_users to authenticated;
grant select, insert, update, delete on public.allowed_domains, public.guides,
    public.admin_users, public.software_prices, public.installer_releases to authenticated;

commit;

-- After creating your first administrator in Supabase Auth, add them with:
-- Replace the UUID and email with the real Auth user values.
-- insert into public.admin_users (user_id, email, display_name)
-- values ('YOUR-AUTH-USER-UUID', 'you@statom.co.uk', 'Portal Administrator');

-- After you have your installer file's Dropbox shared link, register a release with:
-- insert into public.installer_releases (version, download_url, delivery_provider, is_active)
-- values ('1.0.0', 'YOUR-DROPBOX-FILE-SHARE-LINK', 'dropbox', true);
