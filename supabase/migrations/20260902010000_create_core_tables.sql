begin;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  avatar_url text,
  created_at timestamptz not null default now()
);

create table if not exists public.verification_runs (
  id uuid primary key default gen_random_uuid(),

  user_id uuid
    references auth.users(id)
    on delete cascade,

  input_type text not null
    check (input_type in ('text', 'url', 'tweet', 'image')),

  original_input text not null,
  extracted_claim text,

  status text not null default 'pending'
    check (status in ('pending', 'processing', 'completed', 'failed')),

  final_truth_score numeric(5,2)
    check (
      final_truth_score is null
      or final_truth_score between 0 and 100
    ),

  final_verdict text,
  final_reasoning text,
  disagreement_summary text,
  error_message text,

  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists verification_runs_user_created_idx
  on public.verification_runs (user_id, created_at desc);

alter table public.profiles enable row level security;
alter table public.verification_runs enable row level security;

commit;