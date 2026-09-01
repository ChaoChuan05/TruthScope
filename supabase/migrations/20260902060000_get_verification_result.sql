create or replace function public.get_verification_result(
    p_verification_id text
)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $function$
    select jsonb_build_object(
        'verificationId',
        verification_run.external_verification_id,
        'ownerUserId',
        verification_run.user_id,
        'document',
        verification_run.raw_result
    )
    from public.verification_runs as verification_run
    where verification_run.external_verification_id = p_verification_id
    limit 1;
$function$;

revoke all
on function public.get_verification_result(text)
from public, anon, authenticated;

grant execute
on function public.get_verification_result(text)
to service_role;