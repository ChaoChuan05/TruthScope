begin;

-- Verifier A and B request different models, but Gonka may route both calls to the same served
-- model. Both analyses remain independently traceable through their Gonka request IDs. The old
-- uniqueness rule rejected this valid result and rolled back the complete verification record.
alter table public.model_inferences
  drop constraint if exists model_inferences_run_id_external_claim_id_model_name_key;

-- Request identity distinguishes independent verifier calls without pretending routed model names
-- are unique. Null request IDs remain allowed for partial/provider-degraded records.
create unique index if not exists model_inferences_run_claim_request_uidx
  on public.model_inferences (run_id, external_claim_id, gonka_request_id)
  where gonka_request_id is not null;

commit;
