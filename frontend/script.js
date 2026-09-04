"use strict";

const appConfig = window.TRUTHSCOPE_CONFIG || {};
const apiBaseUrl = String(
  appConfig.API_BASE_URL || "http://127.0.0.1:8000/api/v1",
).replace(/\/$/, "");
const oauthRedirectSetting = String(appConfig.OAUTH_REDIRECT_URL || "").trim();
const supabaseUrl = String(appConfig.SUPABASE_URL || "").replace(/\/$/, "");
const supabasePublishableKey = String(appConfig.SUPABASE_PUBLISHABLE_KEY || "");

const input = document.getElementById("claimInput");
const charCount = document.getElementById("charcount");
const results = document.getElementById("results");
const checkButton = document.getElementById("checkBtn");
const checkLabel = document.getElementById("checkLabel");
const needle = document.getElementById("needle");
const arcForeground = document.getElementById("arcFg");
const scoreNumber = document.getElementById("scoreNum");
const checkTime = document.getElementById("checkTime");
const verificationLoading = document.getElementById("verificationLoading");
const loadingStatus = document.getElementById("loadingStatus");
const pipelineTitle = document.getElementById("pipelineTitle");
const pipelineElapsed = document.getElementById("pipelineElapsed");
const pipelineToggle = document.getElementById("pipelineToggle");
const pipelineDetails = document.getElementById("pipelineDetails");
const pipelineSteps = document.getElementById("pipelineSteps");
const pipelineProgress = document.getElementById("pipelineProgress");
const verificationMessage = document.getElementById("verificationMessage");
const openLoginButton = document.getElementById("openLoginBtn");
const promptLoginButton = document.getElementById("promptLoginBtn");
const loginModal = document.getElementById("loginModal");
const closeLoginButton = document.getElementById("closeLoginBtn");
const googleLoginButton = document.getElementById("googleLoginBtn");
const logoutButton = document.getElementById("logoutBtn");
const userPanel = document.getElementById("userPanel");
const userAvatar = document.getElementById("userAvatar");
const userDisplayName = document.getElementById("userDisplayName");
const authMessage = document.getElementById("authMessage");
const signedOutPrompt = document.getElementById("signedOutPrompt");
const themeToggle = document.getElementById("themeToggle");
const historyList = document.getElementById("historyList");
const historyRefresh = document.getElementById("historyRefresh");
const historyCount = document.getElementById("historyCount");

const HISTORY_PAGE_SIZE = 500;

const examples = {
  population: "Malaysia reported a population of 34.1 million in 2024.",
  fuel: "The Malaysian government will remove every fuel subsidy next month.",
  quote: "A Member of Parliament said healthcare would be fully privatised.",
};

const verdictLabels = {
  strongly_supported: "STRONGLY SUPPORTED BY EVIDENCE",
  mostly_supported: "MOSTLY SUPPORTED BY EVIDENCE",
  mixed_or_inconclusive: "MIXED OR INCONCLUSIVE",
  mostly_contradicted: "MOSTLY CONTRADICTED BY EVIDENCE",
  strongly_contradicted: "STRONGLY CONTRADICTED BY EVIDENCE",
};

const pipelineStageDefinitions = [
  {
    label: "Claim extraction",
    detail: "Identify atomic, verifiable claims",
    startsAt: 0,
    taskNames: ["claimExtraction"],
    errorStages: ["claimExtraction"],
  },
  {
    label: "Evidence planning",
    detail: "Build neutral search queries",
    startsAt: 8,
    taskNames: ["evidencePlanning"],
    errorStages: ["evidencePlanningAndRetrieval"],
  },
  {
    label: "Source retrieval",
    detail: "Collect and normalize public evidence",
    startsAt: 18,
    taskNames: [],
    errorStages: ["evidencePlanningAndRetrieval"],
  },
  {
    label: "Context analysis",
    detail: "Check dates, quotations, and missing context",
    startsAt: 35,
    taskNames: ["contextAnalysis"],
    errorStages: ["contextAnalyzer"],
  },
  {
    label: "Verifier A",
    detail: "Independent evidence assessment",
    startsAt: 50,
    taskNames: ["verifierModelA"],
    errorStages: ["verifierModelA"],
  },
  {
    label: "Verifier B",
    detail: "Second independent assessment",
    startsAt: 70,
    taskNames: ["verifierModelB"],
    errorStages: ["verifierModelB"],
  },
  {
    label: "Consensus judge",
    detail: "Compare agreements and disagreements",
    startsAt: 95,
    taskNames: ["consensusJudge", "consensusRetry"],
    errorStages: ["consensusJudge", "consensusRetry"],
  },
  {
    label: "Bias audit",
    detail: "Check decision language for neutrality indicators",
    startsAt: 115,
    taskNames: ["biasAudit", "biasAuditRetry"],
    errorStages: ["biasAudit", "biasAuditRetry"],
  },
];

let supabaseClient = null;
let currentSession = null;
let previousModalFocus = null;
let pipelineTimer = null;
let pipelineStartedAt = null;
let lastEstimatedStageIndex = -1;
let scoreAnimationFrame = null;
let historyUserId = null;
let historyLoadGeneration = 0;

function createElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function replaceChildren(element, children = []) {
  element.replaceChildren(...children);
}

function humanize(value) {
  if (!value) return "Unavailable";
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatModelPercent(value) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? String(Math.round(numericValue * 100)) : "—";
}

function formatDate(value) {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en-MY", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kuala_Lumpur",
  }).format(date);
}

function safeHttpUrl(value) {
  try {
    const url = new URL(String(value));
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function oauthRedirectUrl() {
  const currentPage = `${window.location.origin}${window.location.pathname}`;
  const redirectUrl = safeHttpUrl(oauthRedirectSetting || currentPage);
  if (!redirectUrl) {
    throw new Error("Open TruthScope through its local HTTP server before using Google login.");
  }
  return redirectUrl;
}

function shortRequestId(value) {
  if (!value) return "Request ID unavailable";
  const requestId = String(value);
  return requestId.length > 28
    ? `${requestId.slice(0, 14)}…${requestId.slice(-8)}`
    : requestId;
}

function confidenceLevel(value) {
  const confidence = Number(value);
  if (!Number.isFinite(confidence)) return "UNAVAILABLE";
  if (confidence >= 0.75) return "HIGH";
  if (confidence >= 0.45) return "MEDIUM";
  return "LOW";
}

function findingClass(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized.includes("contradict")) return "danger";
  if (normalized.includes("support")) return "support";
  return "caution";
}

function animateScore(target) {
  if (scoreAnimationFrame !== null) cancelAnimationFrame(scoreAnimationFrame);
  const numericTarget = Number(target);
  if (!Number.isFinite(numericTarget)) {
    scoreNumber.textContent = "—";
    needle.style.transform = "rotate(-90deg)";
    arcForeground.style.strokeDashoffset = "267";
    return;
  }

  const boundedTarget = Math.max(0, Math.min(100, numericTarget));
  const angle = -90 + (boundedTarget / 100) * 180;
  needle.style.transform = `rotate(${angle}deg)`;
  arcForeground.style.strokeDashoffset = String(267 - (267 * boundedTarget) / 100);

  const startedAt = performance.now();
  const step = (timestamp) => {
    const progress = Math.min(1, (timestamp - startedAt) / 900);
    scoreNumber.textContent = String(Math.round(boundedTarget * (1 - Math.pow(1 - progress, 3))));
    if (progress < 1) scoreAnimationFrame = requestAnimationFrame(step);
  };
  scoreAnimationFrame = requestAnimationFrame(step);
}

function setVerificationMessage(message, tone = "error") {
  verificationMessage.textContent = message || "";
  verificationMessage.className = `verification-message ${tone}`;
  verificationMessage.hidden = !message;
}

function formatElapsed(milliseconds) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

function pipelineStepElement(stage, status, statusText, metadata = "") {
  const row = createElement("div", `pipeline-step ${status}`);
  row.setAttribute("role", "listitem");
  if (status === "active") row.setAttribute("aria-current", "step");
  const marker = createElement("span", "pipeline-marker", status === "confirmed" ? "✓" : "");
  marker.setAttribute("aria-hidden", "true");
  const content = createElement("div", "pipeline-step-content");
  content.append(
    createElement("div", "pipeline-step-name", stage.label),
    createElement("div", "pipeline-step-detail", stage.detail),
  );
  const state = createElement("div", "pipeline-step-state", statusText);
  if (metadata) state.append(createElement("span", "pipeline-step-meta", metadata));
  row.append(marker, content, state);
  return row;
}

function renderEstimatedPipeline(elapsedSeconds) {
  let activeIndex = 0;
  pipelineStageDefinitions.forEach((stage, index) => {
    if (elapsedSeconds >= stage.startsAt) activeIndex = index;
  });
  pipelineProgress.style.width = `${Math.min(92, 8 + elapsedSeconds * 0.7)}%`;
  if (activeIndex === lastEstimatedStageIndex) return;

  lastEstimatedStageIndex = activeIndex;
  const rows = pipelineStageDefinitions.map((stage, index) => {
    if (index < activeIndex) {
      return pipelineStepElement(stage, "estimated", "Earlier stage · estimated");
    }
    if (index === activeIndex) {
      return pipelineStepElement(stage, "active", "Likely active");
    }
    return pipelineStepElement(stage, "queued", "Queued");
  });
  replaceChildren(pipelineSteps, rows);
  loadingStatus.textContent = `Estimated stage: ${pipelineStageDefinitions[activeIndex].label}`;
}

function updatePipelineClock() {
  if (pipelineStartedAt === null) return;
  const elapsedMilliseconds = performance.now() - pipelineStartedAt;
  pipelineElapsed.textContent = `Worked for ${formatElapsed(elapsedMilliseconds)}`;
  renderEstimatedPipeline(elapsedMilliseconds / 1000);
}

function stopPipelineClock() {
  if (pipelineTimer !== null) window.clearInterval(pipelineTimer);
  pipelineTimer = null;
}

function startPipeline() {
  stopPipelineClock();
  pipelineStartedAt = performance.now();
  lastEstimatedStageIndex = -1;
  pipelineTitle.textContent = "Agent pipeline working";
  pipelineDetails.hidden = false;
  pipelineToggle.textContent = "Hide details";
  pipelineToggle.setAttribute("aria-expanded", "true");
  verificationLoading.className = "verification-loading running";
  verificationLoading.hidden = false;
  updatePipelineClock();
  pipelineTimer = window.setInterval(updatePipelineClock, 1000);
}

function inferenceForStage(records, stage) {
  return records.find((record) => stage.taskNames.includes(record.taskName));
}

function finishPipeline(data) {
  stopPipelineClock();
  lastEstimatedStageIndex = -1;
  const elapsedMilliseconds =
    pipelineStartedAt === null ? 0 : performance.now() - pipelineStartedAt;
  pipelineElapsed.textContent = `Worked for ${formatElapsed(elapsedMilliseconds)}`;
  if (data.status === "failed") {
    pipelineTitle.textContent = "Agent pipeline failed";
  } else if (data.status === "degraded") {
    pipelineTitle.textContent = "Agent pipeline finished with limitations";
  } else {
    pipelineTitle.textContent = "Agent pipeline completed";
  }
  verificationLoading.className = `verification-loading ${data.status || "complete"}`;
  loadingStatus.textContent = `Backend status: ${humanize(data.status)}`;
  pipelineProgress.style.width = "100%";

  const records = Array.isArray(data.inferenceRecords) ? data.inferenceRecords : [];
  const errors = Array.isArray(data.errors) ? data.errors : [];
  const rows = pipelineStageDefinitions.map((stage) => {
    const record = inferenceForStage(records, stage);
    const error = errors.find((item) => stage.errorStages.includes(item.stage));
    if (record) {
      const latency = Number.isFinite(Number(record.latencyMs))
        ? `${(Number(record.latencyMs) / 1000).toFixed(1)}s`
        : "";
      const metadata = [record.servedModel, latency, shortRequestId(record.requestId)]
        .filter(Boolean)
        .join(" · ");
      return pipelineStepElement(stage, "confirmed", "Confirmed", metadata);
    }
    const retrievalFinished =
      stage.label === "Source retrieval" &&
      Array.isArray(data.evidence) &&
      records.some((item) => item.taskName === "evidencePlanning");
    if (retrievalFinished && !error) {
      return pipelineStepElement(
        stage,
        "confirmed",
        "Confirmed",
        `${data.evidence.length} evidence record${data.evidence.length === 1 ? "" : "s"}`,
      );
    }
    if (error) return pipelineStepElement(stage, "failed", "Unavailable", error.message);
    return pipelineStepElement(stage, "skipped", "Skipped");
  });
  replaceChildren(pipelineSteps, rows);
}

function failPipeline(message) {
  stopPipelineClock();
  lastEstimatedStageIndex = -1;
  const elapsedMilliseconds =
    pipelineStartedAt === null ? 0 : performance.now() - pipelineStartedAt;
  pipelineElapsed.textContent = `Worked for ${formatElapsed(elapsedMilliseconds)}`;
  pipelineTitle.textContent = "Agent pipeline request failed";
  loadingStatus.textContent = message || "Verification request failed.";
  verificationLoading.className = "verification-loading failed";
  pipelineProgress.style.width = "100%";
}

function extractErrorMessage(responseBody, fallback) {
  if (responseBody?.error?.message) return responseBody.error.message;
  if (Array.isArray(responseBody?.detail)) {
    return responseBody.detail.map((item) => item.msg || "Invalid input").join(" ");
  }
  if (typeof responseBody?.detail === "string") return responseBody.detail;
  return fallback;
}

function configuredForAuth() {
  return Boolean(
    safeHttpUrl(supabaseUrl) &&
    !supabaseUrl.includes("YOUR_PROJECT_REF") &&
    supabasePublishableKey &&
    !supabasePublishableKey.includes("YOUR_PUBLIC") &&
    window.supabase &&
    typeof window.supabase.createClient === "function"
  );
}

function openLogin(message = "") {
  previousModalFocus = document.activeElement;
  authMessage.textContent = message;
  loginModal.hidden = false;
  document.body.classList.add("auth-modal-open");
  requestAnimationFrame(() => googleLoginButton.focus());
}

function closeLogin() {
  loginModal.hidden = true;
  document.body.classList.remove("auth-modal-open");
  if (previousModalFocus instanceof HTMLElement) previousModalFocus.focus();
}

function clearPrivateUi() {
  stopPipelineClock();
  pipelineStartedAt = null;
  verificationLoading.hidden = true;
  results.hidden = true;
  results.classList.remove("show");
  replaceChildren(document.getElementById("modelGrid"));
  replaceChildren(document.getElementById("analysisTrace"));
  replaceChildren(document.getElementById("evidenceList"));
  replaceChildren(document.getElementById("disagreementList"));
  replaceChildren(historyList);
  historyCount.textContent = "0 records";
  setVerificationMessage("");
}

async function loadUserProfile(user) {
  const fallbackName =
    user.user_metadata?.full_name || user.user_metadata?.name || user.email?.split("@")[0] || "User";
  let displayName = fallbackName;
  let avatarUrl = user.user_metadata?.avatar_url || user.user_metadata?.picture || "";

  const { data, error } = await supabaseClient
    .from("profiles")
    .select("display_name,avatar_url")
    .eq("id", user.id)
    .maybeSingle();
  if (!error && data) {
    displayName = data.display_name || displayName;
    avatarUrl = data.avatar_url || avatarUrl;
  }

  userDisplayName.textContent = displayName;
  const safeAvatarUrl = safeHttpUrl(avatarUrl);
  userAvatar.hidden = !safeAvatarUrl;
  userAvatar.alt = safeAvatarUrl ? `${displayName} avatar` : "";
  if (safeAvatarUrl) userAvatar.src = safeAvatarUrl;
  else userAvatar.removeAttribute("src");
}

function updateAuthUi(session) {
  currentSession = session || null;
  const signedIn = Boolean(currentSession?.user?.id);
  document.querySelectorAll(".auth-only").forEach((element) => {
    element.hidden = !signedIn;
  });
  signedOutPrompt.hidden = signedIn;
  openLoginButton.hidden = signedIn;
  userPanel.hidden = !signedIn;

  if (!signedIn) {
    historyUserId = null;
    clearPrivateUi();
    return;
  }

  void loadUserProfile(currentSession.user);
  if (historyUserId !== currentSession.user.id) {
    historyUserId = currentSession.user.id;
    void loadHistory();
  }
  closeLogin();
}

async function getSession() {
  if (!supabaseClient) throw new Error("Supabase login is not configured.");
  const { data, error } = await supabaseClient.auth.getSession();
  if (error || !data.session) throw new Error("Please sign in before verifying a claim.");
  currentSession = data.session;
  return data.session;
}

async function apiRequest(path, options = {}, retryAfterRefresh = true) {
  const session = await getSession();
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${session.access_token}`,
      ...(options.headers || {}),
    },
  });

  if (response.status === 401 && retryAfterRefresh) {
    const { data, error } = await supabaseClient.auth.refreshSession();
    if (!error && data.session) return apiRequest(path, options, false);
  }

  let responseBody = null;
  try {
    responseBody = await response.json();
  } catch {
    responseBody = null;
  }
  if (!response.ok) {
    if (response.status === 401) {
      await supabaseClient.auth.signOut({ scope: "local" });
      throw new Error("Session expired. Sign in again.");
    }
    throw new Error(
      extractErrorMessage(responseBody, `Verification request failed with HTTP ${response.status}.`),
    );
  }
  return responseBody;
}

function renderClaims(claims) {
  const container = document.getElementById("claimText");
  const claimItems = Array.isArray(claims) ? claims : [];
  if (!claimItems.length) {
    replaceChildren(container, [createElement("p", "claim-item", "No atomic claim extracted.")]);
    return;
  }
  replaceChildren(
    container,
    claimItems.map((claim, index) =>
      createElement(
        "p",
        "claim-item",
        `${claimItems.length > 1 ? `${index + 1}. ` : ""}${claim.normalizedText || claim.originalText}`,
      ),
    ),
  );
}

function renderModelCard({ label, provider, confidence, finding, requestId, summary }) {
  const tone = findingClass(finding);
  const card = createElement("article", `model-card ${tone}`);
  card.append(
    createElement("div", "model-name", label),
    createElement("div", "model-provider", `${provider || "Model unavailable"} · via Gonka Router`),
  );
  const score = createElement("div", "model-score");
  score.append(document.createTextNode(formatModelPercent(confidence)), createElement("span", "", "%"));
  card.append(
    score,
    createElement("div", "model-conf", `CONFIDENCE — ${confidenceLevel(confidence)}`),
    createElement("div", `model-tag ${tone}`, humanize(finding)),
    createElement("p", "model-summary", summary || "Analysis summary unavailable."),
  );
  const request = createElement("div", "model-reqid", shortRequestId(requestId));
  if (requestId) request.title = String(requestId);
  card.append(request);
  return card;
}

function renderModels(data) {
  const analyses = Array.isArray(data.agentAnalyses) ? data.agentAnalyses : [];
  const cards = analyses.map((analysis, index) =>
    renderModelCard({
      label: `Verifier ${String.fromCharCode(65 + index)}`,
      provider: analysis.modelName,
      confidence: analysis.confidence,
      finding: analysis.stance,
      requestId: analysis.gonkaRequestId,
      summary: analysis.reasoningSummary,
    }),
  );
  if (data.judgeResult) {
    const judgeRecord = (data.inferenceRecords || []).find((record) =>
      ["consensusJudge", "consensusRetry"].includes(record.taskName),
    );
    cards.push(
      renderModelCard({
        label: "Consensus Judge",
        provider: judgeRecord?.servedModel || judgeRecord?.requestedModel,
        confidence: data.judgeResult.confidence,
        finding: data.judgeResult.verdict,
        requestId: data.judgeResult.gonkaRequestId || judgeRecord?.requestId,
        summary: data.judgeResult.reasoningSummary,
      }),
    );
  }
  if (!cards.length) cards.push(createElement("div", "empty-state", "No valid model analysis was returned."));
  replaceChildren(document.getElementById("modelGrid"), cards);
}

function inferenceRequestId(data, taskNames) {
  return (data.inferenceRecords || []).find((item) => taskNames.includes(item.taskName))?.requestId;
}

function traceStep(index, label, title, body, requestId) {
  const step = createElement("article", "trace-step");
  step.append(
    createElement("div", "t-idx", `Step ${index} — ${label}`),
    createElement("div", "t-title", title),
    createElement("div", "t-body", body || "Summary unavailable."),
  );
  const request = createElement("div", "t-req", `Request ID: ${shortRequestId(requestId)}`);
  if (requestId) request.title = String(requestId);
  step.append(request);
  return step;
}

function renderAnalysisTrace(data) {
  const claims = Array.isArray(data.claims) ? data.claims : [];
  const steps = [
    traceStep(
      1,
      "Claim extraction",
      `${claims.length} atomic claim${claims.length === 1 ? "" : "s"} identified`,
      claims.map((claim) => claim.normalizedText || claim.originalText).join(" ") ||
        "Claim extraction did not complete.",
      inferenceRequestId(data, ["claimExtraction"]),
    ),
  ];
  (data.agentAnalyses || []).forEach((analysis, index) => {
    steps.push(
      traceStep(
        steps.length + 1,
        `Verifier ${String.fromCharCode(65 + index)}`,
        `${humanize(analysis.stance)} · ${analysis.modelName}`,
        analysis.reasoningSummary,
        analysis.gonkaRequestId,
      ),
    );
  });
  if (data.judgeResult) {
    steps.push(
      traceStep(
        steps.length + 1,
        "Consensus",
        verdictLabels[data.judgeResult.verdict] || humanize(data.judgeResult.verdict),
        data.judgeResult.reasoningSummary,
        data.judgeResult.gonkaRequestId || inferenceRequestId(data, ["consensusRetry", "consensusJudge"]),
      ),
    );
  }
  if (data.biasAudit) {
    steps.push(
      traceStep(
        steps.length + 1,
        "Bias audit",
        `Audit ${humanize(data.biasAudit.status)}`,
        data.biasAudit.reasoningSummary,
        data.biasAudit.gonkaRequestId || inferenceRequestId(data, ["biasAuditRetry", "biasAudit"]),
      ),
    );
  }
  replaceChildren(document.getElementById("analysisTrace"), steps);
}

function renderEvidence(data) {
  const evidence = Array.isArray(data.evidence) ? data.evidence : [];
  if (!evidence.length) {
    replaceChildren(document.getElementById("evidenceList"), [createElement("div", "empty-state", "No evidence was retrieved.")]);
    return;
  }
  const items = evidence.map((record, index) => {
    const item = createElement("article", "evidence-item");
    const body = createElement("div", "evidence-body");
    const sourceUrl = safeHttpUrl(record.source?.url);
    const title = sourceUrl
      ? createElement("a", "e-title", record.source?.title || sourceUrl)
      : createElement("div", "e-title", record.source?.title || "Untitled source");
    if (sourceUrl) {
      title.href = sourceUrl;
      title.target = "_blank";
      title.rel = "noopener noreferrer";
    }
    const meta = [
      record.source?.publisher,
      record.source?.publicationDate
        ? `Published ${formatDate(record.source.publicationDate)}`
        : "Publication date unavailable",
      humanize(record.stance),
    ].filter(Boolean);
    body.append(title, createElement("div", "e-date", meta.join(" · ")));
    if (record.excerpt) {
      const details = createElement("details", "evidence-details");
      details.append(createElement("summary", "", "View relevant excerpt"), createElement("p", "", record.excerpt));
      body.append(details);
    }
    item.append(createElement("div", "evidence-num", String(index + 1).padStart(2, "0")), body);
    return item;
  });
  replaceChildren(document.getElementById("evidenceList"), items);
}

function renderDisagreement(data) {
  const disagreements = data.judgeResult?.disagreements || [];
  const agreements = data.judgeResult?.agreements || [];
  const findings = disagreements.length ? disagreements : agreements;
  document.getElementById("disagreementTitle").textContent = disagreements.length
    ? "Where models diverge"
    : "Where models agree";
  const rows = findings.map((finding, index) => {
    const row = createElement("div", "disagree-row");
    row.append(
      createElement("div", "m", `${disagreements.length ? "POINT" : "AGREE"} ${index + 1}`),
      createElement("div", "", finding),
    );
    return row;
  });
  if (!rows.length) rows.push(createElement("div", "empty-state", "Model comparison unavailable."));
  replaceChildren(document.getElementById("disagreementList"), rows);
  document.getElementById("judgeSummary").textContent =
    data.judgeResult?.reasoningSummary || "Consensus judge did not return a valid summary.";
}

function renderNotices(data) {
  const notices = document.getElementById("resultNotices");
  const entries = [];
  if (data.status && data.status !== "complete") entries.push(`Workflow status: ${humanize(data.status)}.`);
  if (data.biasAudit?.status) entries.push(`Bias audit: ${humanize(data.biasAudit.status)}.`);
  (data.warnings || []).forEach((warning) => entries.push(`Warning: ${warning}`));
  (data.limitations || []).forEach((limitation) => entries.push(`Limitation: ${limitation}`));
  (data.errors || []).forEach((error) => entries.push(`${error.stage}: ${error.message}`));
  if (!entries.length) {
    notices.hidden = true;
    replaceChildren(notices);
    return;
  }
  const list = createElement("ul", "");
  entries.forEach((entry) => list.append(createElement("li", "", entry)));
  replaceChildren(notices, [list]);
  notices.hidden = false;
}

function renderResult(data) {
  const score = data.score || null;
  const verdict = score?.verdict || data.verdict || "mixed_or_inconclusive";
  animateScore(score?.truthScore);
  const verdictPill = document.getElementById("verdictPill");
  verdictPill.textContent = verdictLabels[verdict] || humanize(verdict);
  verdictPill.className = `verdict-pill ${findingClass(verdict)}`;
  checkTime.textContent = formatDate(data.completedAt);
  const requestIds = Array.isArray(data.gonkaRequestIds) ? data.gonkaRequestIds : [];
  document.getElementById("requestCount").textContent =
    `${requestIds.length} Gonka request ID${requestIds.length === 1 ? "" : "s"}`;
  document.getElementById("confidenceScore").textContent = Number.isFinite(Number(score?.confidenceScore))
    ? `Confidence ${Math.round(Number(score.confidenceScore))}%`
    : "Confidence unavailable";
  renderClaims(data.claims);
  renderModels(data);
  renderAnalysisTrace(data);
  renderEvidence(data);
  renderDisagreement(data);
  renderNotices(data);
  results.hidden = false;
  requestAnimationFrame(() => results.classList.add("show"));
}

function renderHistoryRows(rows) {
  historyCount.textContent = `${rows.length} record${rows.length === 1 ? "" : "s"}`;
  if (!rows.length) {
    replaceChildren(historyList, [createElement("div", "empty-state", "No saved verifications yet. Run your first check above.")]);
    return;
  }
  const items = rows.map((row) => {
    const button = createElement("button", "history-item");
    button.type = "button";
    const score = Number(row.final_truth_score);
    const scoreText = row.final_truth_score !== null && Number.isFinite(score)
      ? `${Math.round(score)}%`
      : "No score";
    button.append(
      createElement(
        "span",
        "history-claim",
        row.extracted_claim || row.original_input || "Untitled verification",
      ),
      createElement(
        "span",
        "history-meta",
        `${humanize(row.final_verdict || row.provider_status || row.status)} · ${scoreText} · ${formatDate(row.completed_at || row.created_at)}`,
      ),
    );
    button.addEventListener("click", async () => {
      button.disabled = true;
      setVerificationMessage("");
      try {
        if (row.external_verification_id) {
          const result = await apiRequest(
            `/verifications/${encodeURIComponent(row.external_verification_id)}`,
          );
          renderResult(result);
        } else {
          const { data, error } = await supabaseClient
            .from("verification_runs")
            .select("raw_result")
            .eq("id", row.id)
            .maybeSingle();
          if (error || !data?.raw_result) {
            throw new Error("Full report is unavailable for this legacy history record.");
          }
          renderResult(data.raw_result);
        }
        results.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (error) {
        setVerificationMessage(error.message || "Could not load verification history.");
      } finally {
        button.disabled = false;
      }
    });
    return button;
  });
  replaceChildren(historyList, items);
}

async function loadHistory() {
  if (!supabaseClient || !currentSession?.user) return;
  const loadGeneration = ++historyLoadGeneration;
  historyRefresh.disabled = true;
  replaceChildren(historyList, [createElement("div", "empty-state", "Loading history...")]);
  historyCount.textContent = "Loading…";
  const expectedUserId = currentSession.user.id;

  const rows = [];
  let offset = 0;
  let historyError = null;
  while (currentSession?.user?.id === expectedUserId) {
    const { data, error } = await supabaseClient
      .from("verification_runs")
      .select("id,external_verification_id,original_input,extracted_claim,final_truth_score,final_verdict,provider_status,status,created_at,completed_at")
      .order("created_at", { ascending: false })
      .range(offset, offset + HISTORY_PAGE_SIZE - 1);
    if (error) {
      historyError = error;
      break;
    }
    const page = data || [];
    rows.push(...page);
    if (page.length < HISTORY_PAGE_SIZE) break;
    offset += HISTORY_PAGE_SIZE;
  }

  if (loadGeneration !== historyLoadGeneration) return;
  historyRefresh.disabled = false;
  if (currentSession?.user?.id !== expectedUserId) return;
  if (historyError) {
    historyCount.textContent = "Unavailable";
    replaceChildren(historyList, [createElement("div", "empty-state error-text", "History could not be loaded.")]);
    return;
  }
  renderHistoryRows(rows);
}

async function runCheck() {
  const claim = input.value.trim();
  if (!currentSession) {
    openLogin("Sign in before running verification.");
    return;
  }
  if (!claim) {
    setVerificationMessage("Enter a claim or public URL first.");
    input.focus();
    return;
  }

  checkButton.disabled = true;
  checkButton.setAttribute("aria-busy", "true");
  checkLabel.textContent = "Analyzing…";
  results.hidden = true;
  results.classList.remove("show");
  setVerificationMessage("");
  startPipeline();

  try {
    const data = await apiRequest("/verifications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input: claim }),
    });
    finishPipeline(data);
    renderResult(data);
    if (data.status === "degraded") {
      setVerificationMessage("Verification completed with partial provider results. Review warnings below.", "warning");
    } else if (data.status === "failed") {
      setVerificationMessage("Verification failed. Review errors below.");
    } else {
      setVerificationMessage("Verification completed.", "success");
    }
    await loadHistory();
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    const message = error.message || "Verification request failed.";
    failPipeline(message);
    setVerificationMessage(message);
    if (!currentSession) openLogin("Session expired. Sign in again.");
  } finally {
    checkLabel.textContent = "Run Verification";
    checkButton.disabled = false;
    checkButton.removeAttribute("aria-busy");
  }
}

function applyTheme(theme) {
  const normalizedTheme = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = normalizedTheme;
  try {
    localStorage.setItem("truthscope-theme", normalizedTheme);
  } catch {
    // Theme remains active when browser storage is blocked.
  }
  const nextTheme = normalizedTheme === "dark" ? "light" : "dark";
  themeToggle.querySelector(".theme-icon").textContent = normalizedTheme === "dark" ? "☀" : "☾";
  themeToggle.querySelector(".theme-label").textContent = humanize(nextTheme);
  themeToggle.setAttribute("aria-label", `Use ${nextTheme} theme`);
}

function initializeTheme() {
  let savedTheme = null;
  try {
    savedTheme = localStorage.getItem("truthscope-theme");
  } catch {
    // Browser preference remains available when storage is blocked.
  }
  const preferredTheme = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  applyTheme(savedTheme || preferredTheme);
}

async function initializeAuth() {
  if (!configuredForAuth()) {
    updateAuthUi(null);
    openLoginButton.title = "Frontend Supabase configuration required";
    return;
  }
  try {
    supabaseClient = window.supabase.createClient(supabaseUrl, supabasePublishableKey, {
      auth: { autoRefreshToken: true, persistSession: true, detectSessionInUrl: true },
    });
  } catch {
    updateAuthUi(null);
    openLoginButton.title = "Frontend Supabase configuration is invalid";
    return;
  }
  window.truthScopeSupabase = supabaseClient;
  supabaseClient.auth.onAuthStateChange((_event, session) => {
    window.setTimeout(() => updateAuthUi(session), 0);
  });
  const { data, error } = await supabaseClient.auth.getSession();
  if (error) authMessage.textContent = error.message;
  updateAuthUi(data.session);
}

input.addEventListener("input", () => {
  charCount.textContent = `${input.value.length} / ${input.maxLength}`;
});
input.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") void runCheck();
});
document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    input.value = examples[chip.dataset.ex] || "";
    input.dispatchEvent(new Event("input"));
    input.focus();
  });
});
checkButton.addEventListener("click", () => void runCheck());
historyRefresh.addEventListener("click", () => void loadHistory());
promptLoginButton.addEventListener("click", () => openLogin());
openLoginButton.addEventListener("click", () => {
  openLogin(configuredForAuth() ? "" : "Copy config.example.js to config.js and add public Supabase settings.");
});
closeLoginButton.addEventListener("click", closeLogin);
loginModal.addEventListener("click", (event) => {
  if (event.target === loginModal) closeLogin();
});
loginModal.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeLogin();
    return;
  }
  if (event.key !== "Tab") return;
  const focusable = [...loginModal.querySelectorAll("button")].filter((element) => !element.disabled);
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
});

googleLoginButton.addEventListener("click", async () => {
  if (!supabaseClient) {
    authMessage.textContent = "Public Supabase configuration is missing.";
    return;
  }
  googleLoginButton.disabled = true;
  authMessage.textContent = "Redirecting to Google…";
  try {
    const { error } = await supabaseClient.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: oauthRedirectUrl() },
    });
    if (error) throw error;
  } catch (error) {
    authMessage.textContent = error.message || "Google login failed.";
    googleLoginButton.disabled = false;
  }
});

logoutButton.addEventListener("click", async () => {
  logoutButton.disabled = true;
  const { error } = await supabaseClient.auth.signOut({ scope: "local" });
  logoutButton.disabled = false;
  if (error) setVerificationMessage(error.message || "Sign out failed.");
});
themeToggle.addEventListener("click", () => {
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
});
pipelineToggle.addEventListener("click", () => {
  const isExpanded = pipelineToggle.getAttribute("aria-expanded") === "true";
  pipelineDetails.hidden = isExpanded;
  pipelineToggle.setAttribute("aria-expanded", String(!isExpanded));
  pipelineToggle.textContent = isExpanded ? "Show details" : "Hide details";
});

initializeTheme();
void initializeAuth();
