begin;

drop policy if exists "profiles_select_own"
  on public.profiles;

drop policy if exists "profiles_update_own"
  on public.profiles;

drop policy if exists "verification_runs_select_own"
  on public.verification_runs;

create policy "profiles_select_own"
on public.profiles
for select
to authenticated
using (
  (select auth.uid()) = id
);

create policy "profiles_update_own"
on public.profiles
for update
to authenticated
using (
  (select auth.uid()) = id
)
with check (
  (select auth.uid()) = id
);

create policy "verification_runs_select_own"
on public.verification_runs
for select
to authenticated
using (
  (select auth.uid()) = user_id
);

commit;