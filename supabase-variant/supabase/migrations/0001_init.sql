create table organisations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  org_id uuid not null references organisations(id) on delete cascade,
  email text not null,
  role text not null check (role in ('owner', 'member')),
  created_at timestamptz not null default now()
);

create table records (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organisations(id) on delete cascade,
  created_by uuid not null references profiles(id),
  status text not null default 'open',
  payload jsonb not null default '{}',
  updated_at timestamptz not null default now()
);

create table file_uploads (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references profiles(id) on delete cascade,
  path text not null,
  uploaded_at timestamptz not null default now()
);

create view report_view as
  select
    org_id,
    date_trunc('month', updated_at) as period,
    count(*) as total_records,
    avg(extract(epoch from (updated_at - (payload->>'created_at')::timestamptz))) as avg_processing_time
  from records
  group by org_id, date_trunc('month', updated_at);
