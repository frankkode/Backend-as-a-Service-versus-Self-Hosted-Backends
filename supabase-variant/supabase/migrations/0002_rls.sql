alter table organisations enable row level security;
alter table profiles enable row level security;
alter table records enable row level security;
alter table file_uploads enable row level security;

create policy "org members can view their org" on organisations
  for select using (id in (select org_id from profiles where profiles.id = auth.uid()));

create policy "users can view profiles in their org" on profiles
  for select using (org_id in (select org_id from profiles where profiles.id = auth.uid()));

create policy "org members can read their org's records" on records
  for select using (org_id in (select org_id from profiles where profiles.id = auth.uid()));

create policy "org members can insert records for their org" on records
  for insert with check (org_id in (select org_id from profiles where profiles.id = auth.uid()));

create policy "record creator or org owner can update" on records
  for update using (
    created_by = auth.uid()
    or org_id in (select org_id from profiles where profiles.id = auth.uid() and role = 'owner')
  );

create policy "org members can manage their own uploads" on file_uploads
  for all using (owner_id = auth.uid());
