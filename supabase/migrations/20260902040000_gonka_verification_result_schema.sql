begin;

-- =====================================================
-- 1. 扩展 verification_runs
-- =====================================================

alter table public.verification_runs
  add column if not exists external_verification_id text,
  add column if not exists external_request_id text,
  add column if not exists normalized_text text,
  add column if not exists final_confidence_score numeric(5,2)
    check (
      final_confidence_score is null
      or final_confidence_score between 0 and 100
    ),
  add column if not exists score_verdict text,
  add column if not exists support_value numeric(6,4)
    check (
      support_value is null
      or support_value between -1 and 1
    ),
  add column if not exists evidence_weight numeric(8,4),
  add column if not exists evidence_coverage numeric(6,4),
  add column if not exists model_agreement numeric(6,4),
  add column if not exists model_disagreement boolean
    not null default false,
  add column if not exists formula_version text,
  add column if not exists prompt_version text,
  add column if not exists provider_status text,
  add column if not exists gonka_request_ids text[]
    not null default '{}'::text[],
  add column if not exists warnings text[]
    not null default '{}'::text[],
  add column if not exists limitations text[]
    not null default '{}'::text[],
  add column if not exists score_breakdown jsonb,
  add column if not exists judge_result jsonb,
  add column if not exists bias_audit jsonb,
  add column if not exists errors jsonb
    not null default '[]'::jsonb,
  add column if not exists raw_result jsonb;

create unique index if not exists
  verification_runs_external_verification_uidx
  on public.verification_runs (external_verification_id)
  where external_verification_id is not null;

create index if not exists
  verification_runs_external_request_idx
  on public.verification_runs (external_request_id);


-- =====================================================
-- 2. Claims
-- =====================================================

create table if not exists public.verification_claims (
  id uuid primary key default gen_random_uuid(),

  run_id uuid not null
    references public.verification_runs(id)
    on delete cascade,

  external_claim_id text not null,
  original_text text not null,
  normalized_text text,
  claim_type text,
  language text,
  verifiable boolean not null default true,

  qualifiers text[]
    not null default '{}'::text[],

  created_at timestamptz
    not null default now(),

  unique (run_id, external_claim_id)
);

create index if not exists verification_claims_run_idx
  on public.verification_claims (run_id);


-- =====================================================
-- 3. Evidence sources
-- =====================================================

create table if not exists public.evidence_sources (
  id uuid primary key default gen_random_uuid(),

  run_id uuid not null
    references public.verification_runs(id)
    on delete cascade,

  external_evidence_id text not null,

  source_url text,
  source_title text,
  publisher text,
  publication_date timestamptz,
  retrieval_timestamp timestamptz,
  source_type text,

  excerpt text,

  claim_ids text[]
    not null default '{}'::text[],

  stance text,
  stance_strength numeric(6,4),

  quality jsonb
    not null default '{}'::jsonb,

  limitations text[]
    not null default '{}'::text[],

  created_at timestamptz
    not null default now(),

  unique (run_id, external_evidence_id)
);

create index if not exists evidence_sources_run_idx
  on public.evidence_sources (run_id);


-- =====================================================
-- 4. Model / agent analyses
-- =====================================================

create table if not exists public.model_inferences (
  id uuid primary key default gen_random_uuid(),

  run_id uuid not null
    references public.verification_runs(id)
    on delete cascade,

  external_claim_id text not null,
  model_name text not null,
  stance text,

  support_strength numeric(6,4),
  confidence numeric(6,4),

  used_evidence_ids text[]
    not null default '{}'::text[],

  contradicting_evidence_ids text[]
    not null default '{}'::text[],

  evidence_assessments jsonb
    not null default '[]'::jsonb,

  missing_context text[]
    not null default '{}'::text[],

  reasoning_summary text,

  warnings text[]
    not null default '{}'::text[],

  gonka_request_id text,

  created_at timestamptz
    not null default now(),

  unique (run_id, external_claim_id, model_name)
);

create index if not exists model_inferences_run_idx
  on public.model_inferences (run_id);

create index if not exists model_inferences_gonka_request_idx
  on public.model_inferences (gonka_request_id);


-- =====================================================
-- 5. Gonka execution records
-- =====================================================

create table if not exists public.inference_records (
  id uuid primary key default gen_random_uuid(),

  run_id uuid not null
    references public.verification_runs(id)
    on delete cascade,

  task_name text,
  requested_model text,
  served_model text,
  external_request_id text not null,
  provider_response_id text,

  latency_ms bigint,
  input_tokens bigint,
  output_tokens bigint,

  fallback text,

  created_at timestamptz
    not null default now(),

  unique (run_id, external_request_id)
);

create index if not exists inference_records_run_idx
  on public.inference_records (run_id);


-- =====================================================
-- 6. 启用 RLS
-- =====================================================

alter table public.verification_claims
  enable row level security;

alter table public.evidence_sources
  enable row level security;

alter table public.model_inferences
  enable row level security;

alter table public.inference_records
  enable row level security;


-- =====================================================
-- 7. 用户只能读取自己的 Verification 数据
-- =====================================================

drop policy if exists verification_claims_select_own
  on public.verification_claims;

create policy verification_claims_select_own
  on public.verification_claims
  for select
  to authenticated
  using (
    exists (
      select 1
      from public.verification_runs vr
      where vr.id = verification_claims.run_id
        and vr.user_id = (select auth.uid())
    )
  );


drop policy if exists evidence_sources_select_own
  on public.evidence_sources;

create policy evidence_sources_select_own
  on public.evidence_sources
  for select
  to authenticated
  using (
    exists (
      select 1
      from public.verification_runs vr
      where vr.id = evidence_sources.run_id
        and vr.user_id = (select auth.uid())
    )
  );


drop policy if exists model_inferences_select_own
  on public.model_inferences;

create policy model_inferences_select_own
  on public.model_inferences
  for select
  to authenticated
  using (
    exists (
      select 1
      from public.verification_runs vr
      where vr.id = model_inferences.run_id
        and vr.user_id = (select auth.uid())
    )
  );


drop policy if exists inference_records_select_own
  on public.inference_records;

create policy inference_records_select_own
  on public.inference_records
  for select
  to authenticated
  using (
    exists (
      select 1
      from public.verification_runs vr
      where vr.id = inference_records.run_id
        and vr.user_id = (select auth.uid())
    )
  );

commit;