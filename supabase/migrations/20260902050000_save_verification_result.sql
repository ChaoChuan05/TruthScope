create or replace function public.save_verification_result(
  p_user_id uuid,
  p_result jsonb
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_run_id uuid;
  v_external_verification_id text;
  v_status text;
  v_input_type text;
  v_disagreement_summary text;
begin
  -- ===================================================
  -- 1. 基础验证
  -- ===================================================

  if p_user_id is null then
    raise exception 'p_user_id is required';
  end if;

  if p_result is null
     or jsonb_typeof(p_result) <> 'object' then
    raise exception 'p_result must be a JSON object';
  end if;

  if not exists (
    select 1
    from auth.users
    where id = p_user_id
  ) then
    raise exception 'Supabase user does not exist';
  end if;

  v_external_verification_id :=
    nullif(p_result ->> 'verificationId', '');

  if v_external_verification_id is null then
    raise exception 'verificationId is required';
  end if;


  -- ===================================================
  -- 2. 转换后端状态
  -- JSON complete → Database completed
  -- ===================================================

v_status :=
  case lower(coalesce(p_result ->> 'status', ''))
    when 'complete' then 'completed'
    when 'completed' then 'completed'
    when 'inconclusive' then 'completed'
    when 'degraded' then 'completed'
    when 'processing' then 'processing'
    when 'pending' then 'pending'
    when 'failed' then 'failed'
    else 'failed'
  end;


  -- ===================================================
  -- 3. 验证 inputType
  -- ===================================================

  v_input_type :=
    case lower(coalesce(p_result ->> 'inputType', ''))
      when 'text' then 'text'
      when 'url' then 'url'
      when 'tweet' then 'tweet'
      when 'image' then 'image'
      else 'text'
    end;


  -- ===================================================
  -- 4. 把 disagreement 数组转换为可显示文字
  -- ===================================================

  select string_agg(value, E'\n')
  into v_disagreement_summary
  from jsonb_array_elements_text(
    coalesce(
      p_result #> '{judgeResult,disagreements}',
      '[]'::jsonb
    )
  ) as disagreement(value);


  -- ===================================================
  -- 5. 写入或更新 verification_runs
  -- ===================================================

  insert into public.verification_runs (
    user_id,
    input_type,
    original_input,
    extracted_claim,
    status,

    final_truth_score,
    final_confidence_score,
    final_verdict,
    score_verdict,
    final_reasoning,
    disagreement_summary,
    error_message,

    external_verification_id,
    external_request_id,
    normalized_text,
    support_value,
    evidence_weight,
    evidence_coverage,
    model_agreement,
    model_disagreement,
    formula_version,
    prompt_version,
    provider_status,

    gonka_request_ids,
    warnings,
    limitations,

    score_breakdown,
    judge_result,
    bias_audit,
    errors,
    raw_result,

    created_at,
    completed_at
  )
  values (
    p_user_id,
    v_input_type,
    coalesce(p_result ->> 'originalInput', ''),

    coalesce(
      nullif(
        p_result #>> '{claims,0,normalizedText}',
        ''
      ),
      nullif(
        p_result #>> '{claims,0,originalText}',
        ''
      )
    ),

    v_status,

    nullif(
      p_result #>> '{score,truthScore}',
      ''
    )::numeric,

    nullif(
      p_result #>> '{score,confidenceScore}',
      ''
    )::numeric,

    nullif(p_result ->> 'verdict', ''),

    nullif(
      p_result #>> '{score,verdict}',
      ''
    ),

    nullif(
      p_result #>> '{judgeResult,reasoningSummary}',
      ''
    ),

    v_disagreement_summary,

    nullif(
      p_result #>> '{errors,0,message}',
      ''
    ),

    v_external_verification_id,
    nullif(p_result ->> 'requestId', ''),
    nullif(p_result ->> 'normalizedText', ''),

    nullif(
      p_result #>> '{judgeResult,supportValue}',
      ''
    )::numeric,

    nullif(
      p_result #>> '{score,evidenceWeight}',
      ''
    )::numeric,

    nullif(
      p_result #>> '{score,evidenceCoverage}',
      ''
    )::numeric,

    nullif(
      p_result #>> '{score,modelAgreement}',
      ''
    )::numeric,

    case
      when lower(
        coalesce(
          p_result ->> 'modelDisagreement',
          'false'
        )
      ) = 'true'
      then true
      else false
    end,

    nullif(
      p_result #>> '{score,formulaVersion}',
      ''
    ),

    nullif(p_result ->> 'promptVersion', ''),
    nullif(p_result ->> 'status', ''),

    array(
      select jsonb_array_elements_text(
        coalesce(
          p_result -> 'gonkaRequestIds',
          '[]'::jsonb
        )
      )
    ),

    array(
      select jsonb_array_elements_text(
        coalesce(
          p_result -> 'warnings',
          '[]'::jsonb
        )
      )
    ),

    array(
      select jsonb_array_elements_text(
        coalesce(
          p_result -> 'limitations',
          '[]'::jsonb
        )
      )
    ),

    p_result -> 'score',
    p_result -> 'judgeResult',
    p_result -> 'biasAudit',

    coalesce(
      p_result -> 'errors',
      '[]'::jsonb
    ),

    p_result,

    coalesce(
      nullif(
        p_result ->> 'createdAt',
        ''
      )::timestamptz,
      now()
    ),

    nullif(
      p_result ->> 'completedAt',
      ''
    )::timestamptz
  )

  on conflict (external_verification_id)
    where external_verification_id is not null
  do update set
    user_id = excluded.user_id,
    input_type = excluded.input_type,
    original_input = excluded.original_input,
    extracted_claim = excluded.extracted_claim,
    status = excluded.status,

    final_truth_score =
      excluded.final_truth_score,

    final_confidence_score =
      excluded.final_confidence_score,

    final_verdict = excluded.final_verdict,
    score_verdict = excluded.score_verdict,
    final_reasoning = excluded.final_reasoning,

    disagreement_summary =
      excluded.disagreement_summary,

    error_message = excluded.error_message,

    external_request_id =
      excluded.external_request_id,

    normalized_text = excluded.normalized_text,
    support_value = excluded.support_value,
    evidence_weight = excluded.evidence_weight,
    evidence_coverage = excluded.evidence_coverage,
    model_agreement = excluded.model_agreement,

    model_disagreement =
      excluded.model_disagreement,

    formula_version = excluded.formula_version,
    prompt_version = excluded.prompt_version,
    provider_status = excluded.provider_status,

    gonka_request_ids =
      excluded.gonka_request_ids,

    warnings = excluded.warnings,
    limitations = excluded.limitations,

    score_breakdown = excluded.score_breakdown,
    judge_result = excluded.judge_result,
    bias_audit = excluded.bias_audit,
    errors = excluded.errors,
    raw_result = excluded.raw_result,

    created_at = excluded.created_at,
    completed_at = excluded.completed_at

  returning id into v_run_id;


  -- ===================================================
  -- 6. 如果是重复结果，先清除旧的子记录
  -- ===================================================

  delete from public.verification_claims
  where run_id = v_run_id;

  delete from public.evidence_sources
  where run_id = v_run_id;

  delete from public.model_inferences
  where run_id = v_run_id;

  delete from public.inference_records
  where run_id = v_run_id;


  -- ===================================================
  -- 7. Claims
  -- ===================================================

  insert into public.verification_claims (
    run_id,
    external_claim_id,
    original_text,
    normalized_text,
    claim_type,
    language,
    verifiable,
    qualifiers
  )
  select
    v_run_id,
    claim ->> 'claimId',
    coalesce(claim ->> 'originalText', ''),
    nullif(claim ->> 'normalizedText', ''),
    nullif(claim ->> 'claimType', ''),
    nullif(claim ->> 'language', ''),

    case
      when lower(
        coalesce(claim ->> 'verifiable', 'false')
      ) = 'true'
      then true
      else false
    end,

    array(
      select jsonb_array_elements_text(
        coalesce(
          claim -> 'qualifiers',
          '[]'::jsonb
        )
      )
    )

  from jsonb_array_elements(
    coalesce(
      p_result -> 'claims',
      '[]'::jsonb
    )
  ) as claim_data(claim)

  where nullif(claim ->> 'claimId', '') is not null;


  -- ===================================================
  -- 8. Evidence
  -- ===================================================

  insert into public.evidence_sources (
    run_id,
    external_evidence_id,
    source_url,
    source_title,
    publisher,
    publication_date,
    retrieval_timestamp,
    source_type,
    excerpt,
    claim_ids,
    stance,
    stance_strength,
    quality,
    limitations
  )
  select
    v_run_id,
    evidence ->> 'evidenceId',
    nullif(evidence #>> '{source,url}', ''),
    nullif(evidence #>> '{source,title}', ''),
    nullif(evidence #>> '{source,publisher}', ''),

    nullif(
      evidence #>> '{source,publicationDate}',
      ''
    )::timestamptz,

    nullif(
      evidence #>> '{source,retrievalTimestamp}',
      ''
    )::timestamptz,

    nullif(
      evidence #>> '{source,sourceType}',
      ''
    ),

    nullif(evidence ->> 'excerpt', ''),

    array(
      select jsonb_array_elements_text(
        coalesce(
          evidence -> 'claimIds',
          '[]'::jsonb
        )
      )
    ),

    nullif(evidence ->> 'stance', ''),

    nullif(
      evidence ->> 'stanceStrength',
      ''
    )::numeric,

    coalesce(
      evidence -> 'quality',
      '{}'::jsonb
    ),

    array(
      select jsonb_array_elements_text(
        coalesce(
          evidence -> 'limitations',
          '[]'::jsonb
        )
      )
    )

  from jsonb_array_elements(
    coalesce(
      p_result -> 'evidence',
      '[]'::jsonb
    )
  ) as evidence_data(evidence)

  where nullif(
    evidence ->> 'evidenceId',
    ''
  ) is not null;


  -- ===================================================
  -- 9. Model analyses
  -- ===================================================

  insert into public.model_inferences (
    run_id,
    external_claim_id,
    model_name,
    stance,
    support_strength,
    confidence,
    used_evidence_ids,
    contradicting_evidence_ids,
    evidence_assessments,
    missing_context,
    reasoning_summary,
    warnings,
    gonka_request_id
  )
  select
    v_run_id,
    analysis ->> 'claimId',
    analysis ->> 'modelName',
    nullif(analysis ->> 'stance', ''),

    nullif(
      analysis ->> 'supportStrength',
      ''
    )::numeric,

    nullif(
      analysis ->> 'confidence',
      ''
    )::numeric,

    array(
      select jsonb_array_elements_text(
        coalesce(
          analysis -> 'usedEvidenceIds',
          '[]'::jsonb
        )
      )
    ),

    array(
      select jsonb_array_elements_text(
        coalesce(
          analysis -> 'contradictingEvidenceIds',
          '[]'::jsonb
        )
      )
    ),

    coalesce(
      analysis -> 'evidenceAssessments',
      '[]'::jsonb
    ),

    array(
      select jsonb_array_elements_text(
        coalesce(
          analysis -> 'missingContext',
          '[]'::jsonb
        )
      )
    ),

    nullif(
      analysis ->> 'reasoningSummary',
      ''
    ),

    array(
      select jsonb_array_elements_text(
        coalesce(
          analysis -> 'warnings',
          '[]'::jsonb
        )
      )
    ),

    nullif(
      analysis ->> 'gonkaRequestId',
      ''
    )

  from jsonb_array_elements(
    coalesce(
      p_result -> 'agentAnalyses',
      '[]'::jsonb
    )
  ) as analysis_data(analysis)

  where nullif(
    analysis ->> 'claimId',
    ''
  ) is not null

  and nullif(
    analysis ->> 'modelName',
    ''
  ) is not null;


  -- ===================================================
  -- 10. Inference records
  -- ===================================================

  insert into public.inference_records (
    run_id,
    task_name,
    requested_model,
    served_model,
    external_request_id,
    provider_response_id,
    latency_ms,
    input_tokens,
    output_tokens,
    fallback
  )
  select
    v_run_id,
    nullif(record ->> 'taskName', ''),
    nullif(record ->> 'requestedModel', ''),
    nullif(record ->> 'servedModel', ''),
    record ->> 'requestId',
    nullif(record ->> 'providerResponseId', ''),

    nullif(
      record ->> 'latencyMs',
      ''
    )::bigint,

    nullif(
      record #>> '{usage,inputTokens}',
      ''
    )::bigint,

    nullif(
      record #>> '{usage,outputTokens}',
      ''
    )::bigint,

    nullif(record ->> 'fallback', '')

  from jsonb_array_elements(
    coalesce(
      p_result -> 'inferenceRecords',
      '[]'::jsonb
    )
  ) as record_data(record)

  where nullif(
    record ->> 'requestId',
    ''
  ) is not null;


  return v_run_id;
end;
$$;


-- =====================================================
-- 11. 只允许安全的后端 service_role 调用
-- =====================================================

revoke execute on function
  public.save_verification_result(uuid, jsonb)
  from public, anon, authenticated;

grant execute on function
  public.save_verification_result(uuid, jsonb)
  to service_role;