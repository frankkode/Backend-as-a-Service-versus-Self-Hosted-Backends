-- verify_0004_round2.sql
--
-- Round 1 established that 0004_fixes.sql is incomplete: the live "record creator or org owner can
-- update" policy on records calls current_user_role(), a function defined in no migration, and the
-- policy itself still appears in 0002_rls.sql in its pre-fix recursive form. The published migration
-- history therefore does not rebuild the benchmarked database.
--
-- This round captures what is missing, verbatim rather than by inference, and sweeps for any further
-- drift. Round 1 only inspected records, profiles and organisations; file_uploads is included here.
--
-- One statement, because the SQL Editor returns only the last result set. Paste the whole result back.

select 'A. function' as part,
       p.proname || '  security_definer=' || p.prosecdef::text || '  volatility=' ||
         case p.provolatile when 'i' then 'immutable' when 's' then 'stable' else 'volatile' end as item,
       regexp_replace(pg_get_functiondef(p.oid), '\s+', ' ', 'g') as value
from   pg_proc p
join   pg_namespace n on n.oid = p.pronamespace
where  n.nspname = 'public'
  and  p.prokind = 'f'

union all

-- every policy in the schema, so a fourth drifted one cannot hide the way this one did
select 'B. policy',
       tablename || ' / ' || policyname || ' [' || cmd || ']',
       'USING: ' || coalesce(qual, '(none)') ||
       '   WITH CHECK: ' || coalesce(with_check, '(none)')
from   pg_policies
where  schemaname = 'public'

union all

-- column defaults across the whole schema: 0004 changed one, others may have changed unrecorded
select 'C. default',
       table_name || '.' || column_name,
       column_default
from   information_schema.columns
where  table_schema = 'public'
  and  column_default is not null

union all

-- triggers, in case the auth trigger in 0003 was also amended live
select 'D. trigger',
       c.relname || ' / ' || t.tgname,
       regexp_replace(pg_get_triggerdef(t.oid), '\s+', ' ', 'g')
from   pg_trigger t
join   pg_class c on c.oid = t.tgrelid
join   pg_namespace n on n.oid = c.relnamespace
where  n.nspname = 'public'
  and  not t.tgisinternal

order by 1, 2;
