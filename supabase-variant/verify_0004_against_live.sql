-- verify_0004_against_live.sql
--
-- Run this in the Supabase SQL Editor BEFORE deleting or abandoning the project.
--
-- Why: the three fixes in migrations/0004_fixes.sql were applied by hand in the SQL Editor during
-- the build, then written back into a migration file from notes. That file has never been checked
-- against the database it claims to describe. The thesis (Section 4.3) states that every measurement
-- can be reproduced from the published repository; if the migration does not match the schema that
-- was actually benchmarked, that claim is false and, once the project is gone, unfalsifiable.
--
-- This is deliberately ONE statement. The SQL Editor returns only the last result set when several
-- statements are pasted together, so the four checks are unioned into a single table instead.
-- Run it, then paste the whole result back.
--
-- What each row should say:
--   1. policy       every SELECT policy USING current_user_org_id(); the INSERT policy's WITH CHECK
--                   contains BOTH org_id = current_user_org_id() AND created_by = auth.uid()
--   2. function     security_definer=true, body selecting org_id from profiles where id = auth.uid()
--   3. view         security_invoker=true   <- a NULL here means Fix 2 never landed
--   4. column       records.created_by default is auth.uid()

select '1. policy' as check_name,
       tablename || ' / ' || policyname || ' [' || cmd || ']' as item,
       'USING: '      || coalesce(qual, '(none)') ||
       '   WITH CHECK: ' || coalesce(with_check, '(none)')    as value
from   pg_policies
where  schemaname = 'public'
  and  tablename in ('records', 'profiles', 'organisations')

union all

select '2. function',
       p.proname || '  security_definer=' || p.prosecdef::text,
       regexp_replace(pg_get_functiondef(p.oid), '\s+', ' ', 'g')
from   pg_proc p
join   pg_namespace n on n.oid = p.pronamespace
where  n.nspname = 'public'
  and  p.proname = 'current_user_org_id'

union all

select '3. view',
       c.relname,
       coalesce(array_to_string(c.reloptions, ', '),
                '(NULL - security_invoker NOT set, Fix 2 missing)')
from   pg_class c
join   pg_namespace n on n.oid = c.relnamespace
where  n.nspname = 'public'
  and  c.relname = 'report_view'

union all

select '4. column',
       table_name || '.' || column_name,
       'default: ' || coalesce(column_default, '(none)')
from   information_schema.columns
where  table_schema = 'public'
  and  table_name   = 'records'
  and  column_name  = 'created_by'

order by 1, 2;
