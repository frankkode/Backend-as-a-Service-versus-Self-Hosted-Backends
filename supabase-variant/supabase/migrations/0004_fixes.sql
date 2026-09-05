-- 0004_fixes.sql
--
-- Backfills the fixes that were applied live via the Supabase SQL Editor during the build-and-
-- verification phase (thesis Section 5.2; Appendix B rows 40, 41, 43, 44 and 73), so that the
-- committed migration history reproduces the final, tested configuration.
--
-- Every statement below was verified against the live database on 2026-09-05 by dumping
-- pg_policies, pg_proc, pg_class.reloptions and information_schema.columns and diffing them against
-- this file (see verify_0004_against_live.sql and verify_0004_round2.sql). The definitions here are
-- transcribed from that dump, not reconstructed from memory: an earlier draft of this file was
-- written from notes and turned out to be missing three of the six changes.
--
--   1. RLS infinite recursion: policies that subquery public.profiles from within a policy on
--      profiles (or that fan out through it) recurse. Two SECURITY DEFINER helpers evaluate the
--      caller's organisation and role outside RLS.
--   2. report_view security context: the view must evaluate RLS as the querying user
--      (security_invoker), not as the view owner.
--   3. Authorship spoofing: created_by is server-derived (DEFAULT auth.uid()) and the insert
--      policy's WITH CHECK is strengthened so a client-supplied created_by cannot claim another
--      user's identity.
--   4. Role propagation on signup: handle_new_user must honour the role supplied in the signup
--      metadata, otherwise every seeded account becomes a member and the owner-only update path in
--      the policy below can never be exercised.

-- ---------------------------------------------------------------------------------------------
-- Fix 1a: recursion-safe organisation lookup
-- ---------------------------------------------------------------------------------------------
create or replace function public.current_user_org_id() returns uuid
language sql security definer stable
set search_path = public
as $$
  select org_id from public.profiles where id = auth.uid()
$$;

-- ---------------------------------------------------------------------------------------------
-- Fix 1b: recursion-safe role lookup.
-- Required by the records UPDATE policy below. This was applied live but omitted from the first
-- draft of this migration, which meant a fresh `supabase db reset` failed: the policy referenced a
-- function that did not exist.
-- ---------------------------------------------------------------------------------------------
create or replace function public.current_user_role() returns text
language sql security definer stable
set search_path = public
as $$
  select role from public.profiles where id = auth.uid()
$$;

-- ---------------------------------------------------------------------------------------------
-- Fix 1c: the four policies rewritten to use the helpers instead of recursive subqueries
-- ---------------------------------------------------------------------------------------------
drop policy if exists "users can view profiles in their org" on profiles;
create policy "users can view profiles in their org" on profiles
  for select using (org_id = public.current_user_org_id());

drop policy if exists "org members can view their org" on organisations;
create policy "org members can view their org" on organisations
  for select using (id = public.current_user_org_id());

drop policy if exists "org members can read their org's records" on records;
create policy "org members can read their org's records" on records
  for select using (org_id = public.current_user_org_id());

-- This one was also rewritten live. 0002_rls.sql still carries its pre-fix form, in which the
-- owner branch subqueries profiles directly and therefore recurses.
drop policy if exists "record creator or org owner can update" on records;
create policy "record creator or org owner can update" on records
  for update using (
    created_by = auth.uid()
    or (org_id = public.current_user_org_id() and public.current_user_role() = 'owner')
  );

-- ---------------------------------------------------------------------------------------------
-- Fix 2: report_view evaluates RLS as the querying user
-- ---------------------------------------------------------------------------------------------
alter view public.report_view set (security_invoker = on);

-- ---------------------------------------------------------------------------------------------
-- Fix 3: server-derived authorship, spoof-proof insert policy
-- ---------------------------------------------------------------------------------------------
alter table records alter column created_by set default auth.uid();

drop policy if exists "org members can insert records for their org" on records;
create policy "org members can insert records for their org" on records
  for insert with check (
    org_id = public.current_user_org_id()
    and created_by = auth.uid()
  );

-- ---------------------------------------------------------------------------------------------
-- Fix 4: honour the role supplied at signup.
-- 0003_auth_trigger.sql hardcodes 'member'. Rebuilding from that version produces a database in
-- which no account is ever an owner, so the owner branch of the update policy above is unreachable
-- and the role-separation checks in the criteria catalog cannot be reproduced.
-- ---------------------------------------------------------------------------------------------
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer
as $$
begin
  insert into public.profiles (id, org_id, email, role)
  values (
    new.id,
    (new.raw_user_meta_data->>'org_id')::uuid,
    new.email,
    coalesce(new.raw_user_meta_data->>'role', 'member')
  );
  return new;
end;
$$;
