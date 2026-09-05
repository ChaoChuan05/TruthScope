"use strict";

const appConfig = window.TRUTHSCOPE_CONFIG || {};
const apiBaseUrl = String(
  appConfig.API_BASE_URL || "http://127.0.0.1:8000/api/v1",
).replace(/\/$/, "");
const oauthRedirectSetting = String(appConfig.OAUTH_REDIRECT_URL || "").trim();
const supabaseUrl = String(appConfig.SUPABASE_URL || "").replace(/\/$/, "");
const supabasePublishableKey = String(appConfig.SUPABASE_PUBLISHABLE_KEY || "");
const i18n = window.TRUTHSCOPE_I18N || {};
const termsBundle = window.TRUTHSCOPE_TERMS || {};
const supportedLanguages = new Set(["en", "ms", "zh-CN"]);

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
const githubLoginButton = document.getElementById("githubLoginBtn");
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
const historySearch = document.getElementById("historySearch");
const historyVerdictFilter = document.getElementById("historyVerdictFilter");
const clearInputButton = document.getElementById("clearInputBtn");
const inputTypeBadge = document.getElementById("inputTypeBadge");
const stopWaitingButton = document.getElementById("stopWaitingBtn");
const evidenceCount = document.getElementById("evidenceCount");
const claimBreakdown = document.getElementById("claimBreakdown");
const trendingTopics = document.getElementById("trendingTopics");
const trendingTopicsLabel = document.getElementById("topicSuggestionsLabel");
const trendingTopicsStatus = document.getElementById("trendingTopicsStatus");
const languageSelect = document.getElementById("languageSelect");
const termsLink = document.getElementById("termsLink");
const termsModal = document.getElementById("termsModal");
const termsGateTitle = document.getElementById("termsGateTitle");
const termsEffectiveDate = document.getElementById("termsEffectiveDate");
const termsLanguageSelect = document.getElementById("termsLanguageSelect");
const termsScroll = document.getElementById("termsScroll");
const termsReadStatus = document.getElementById("termsReadStatus");
const termsAcceptance = document.getElementById("termsAcceptance");
const termsAcceptanceLabel = document.getElementById("termsAcceptanceLabel");
const declineTermsButton = document.getElementById("declineTermsBtn");
const acceptTermsButton = document.getElementById("acceptTermsBtn");

const HISTORY_PAGE_SIZE = 500;
const TRENDING_TOPICS_CACHE_PREFIX = "truthscope-current-topics-v1:";
const PENDING_VERIFICATION_CACHE_PREFIX = "truthscope-pending-verification-v1:";
const TERMS_ACCEPTANCE_CACHE_PREFIX = "truthscope-terms-acceptance-v1:";
const TERMS_VERSION = String(termsBundle.version || "2026-09-05-2");
const VERIFICATION_JOB_POLL_INTERVAL_MS = 2500;

const verdictTranslationKeys = {
  strongly_supported: "verdictStronglySupported",
  mostly_supported: "verdictMostlySupported",
  mixed_or_inconclusive: "verdictMixed",
  mostly_contradicted: "verdictMostlyContradicted",
  strongly_contradicted: "verdictStronglyContradicted",
};

const enumTranslationKeys = {
  supports: "supported",
  support: "supported",
  contradicted: "contradicted",
  contradicts: "contradicted",
  neutral: "neutral",
  unclear: "unclear",
  mixed_or_inconclusive: "inconclusive",
  inconclusive: "inconclusive",
  degraded: "degraded",
  complete: "complete",
  failed: "failed",
  passed: "passed",
  flagged: "flagged",
  unavailable: "unavailable",
  primary: "primary",
  secondary: "secondary",
  user_provided: "userProvided",
  unknown: "unknown",
  light: "light",
  dark: "dark",
};

const pipelineStageDefinitions = [
  {
    stageId: "claimExtraction",
    labelKey: "stageClaimExtraction",
    detailKey: "stageClaimExtractionDetail",
    startsAt: 0,
    taskNames: ["claimExtraction"],
    errorStages: ["claimExtraction"],
  },
  {
    stageId: "sourceRetrieval",
    labelKey: "stageSourceRetrieval",
    detailKey: "stageSourceRetrievalDetail",
    startsAt: 8,
    taskNames: [],
    errorStages: ["evidencePlanningAndRetrieval"],
  },
  {
    stageId: "verifierA",
    labelKey: "stageVerifierA",
    detailKey: "stageVerifierADetail",
    startsAt: 25,
    taskNames: ["verifierModelA"],
    errorStages: ["verifierModelA"],
  },
  {
    stageId: "verifierB",
    labelKey: "stageVerifierB",
    detailKey: "stageVerifierBDetail",
    startsAt: 50,
    taskNames: ["verifierModelB"],
    errorStages: ["verifierModelB"],
  },
  {
    stageId: "consensus",
    labelKey: "stageConsensus",
    detailKey: "stageConsensusDetail",
    startsAt: 75,
    taskNames: ["consensusJudge", "consensusRetry"],
    errorStages: ["consensusJudge", "consensusRetry"],
  },
  {
    stageId: "biasAudit",
    labelKey: "stageBiasAudit",
    detailKey: "stageBiasAuditDetail",
    startsAt: 95,
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
let historyRows = [];
let activeHistoryId = null;
let activeVerificationController = null;
let pendingVerificationUserId = null;
let trendingTopicsUserId = null;
let trendingTopicsLoadGeneration = 0;
let selectedLanguage = "en";
let lastRenderedResult = null;
let currentTrendingTopics = [];
let currentTrendingSource = "fallback";
let activeTermsUserId = null;
let termsReadToEnd = false;
const acceptedTermsSessionUsers = new Set();

function t(key, replacements = {}) {
  const languageMessages = i18n.messages?.[selectedLanguage] || i18n.messages?.en || {};
  const fallbackMessages = i18n.messages?.en || {};
  let value = languageMessages[key] ?? fallbackMessages[key] ?? key;
  Object.entries(replacements).forEach(([name, replacement]) => {
    value = String(value).replaceAll(`{${name}}`, String(replacement));
  });
  return String(value);
}

function defaultTrendingTopics() {
  return [
    { label: t("topicPopulationLabel"), claim: t("topicPopulationClaim") },
    { label: t("topicSubsidyLabel"), claim: t("topicSubsidyClaim") },
    { label: t("topicParliamentLabel"), claim: t("topicParliamentClaim") },
  ];
}

function verdictLabel(verdict) {
  const translationKey = verdictTranslationKeys[String(verdict || "")];
  return translationKey ? t(translationKey) : humanize(verdict);
}

function applyLanguage(language, { persist = true } = {}) {
  selectedLanguage = supportedLanguages.has(language) ? language : "en";
  const languageDefinition = i18n.languages?.[selectedLanguage] || {};
  document.documentElement.lang = languageDefinition.htmlLang || selectedLanguage;
  document.title = t("documentTitle");
  languageSelect.value = selectedLanguage;
  termsLanguageSelect.value = selectedLanguage;
  termsLink.href = `terms.html?lang=${encodeURIComponent(selectedLanguage)}`;

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-html]").forEach((element) => {
    element.innerHTML = t(element.dataset.i18nHtml);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  });

  if (persist) {
    try {
      localStorage.setItem("truthscope-language", selectedLanguage);
    } catch {
      // Language remains active when browser storage is blocked.
    }
  }

  applyTheme(document.documentElement.dataset.theme);
  updateInputUi();
  renderTrendingTopics(currentTrendingTopics, currentTrendingSource);
  if (historyRows.length) renderHistoryRows();
  if (lastRenderedResult) renderResult(lastRenderedResult);
  if (!verificationLoading.hidden) {
    if (pipelineTimer !== null) {
      pipelineTitle.textContent = t("pipelineWorking");
      lastEstimatedStageIndex = -1;
      updatePipelineClock();
    } else if (lastRenderedResult) {
      finishPipeline(lastRenderedResult);
    }
  }
  if (activeVerificationController) checkLabel.textContent = t("analyzing");
  if (!currentSession?.user?.id || !hasAcceptedCurrentTerms(currentSession.user.id)) {
    clearUserProfileUi();
  }
  if (!termsModal.hidden) renderTermsGate({ resetReading: true });
}

function initializeLanguage() {
  let savedLanguage = "en";
  try {
    savedLanguage = localStorage.getItem("truthscope-language") || "en";
  } catch {
    // English remains the default when browser storage is blocked.
  }
  applyLanguage(savedLanguage, { persist: false });
}

function createElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function replaceChildren(element, children = []) {
  element.replaceChildren(...children);
}

function normalizeTrendingTopics(value) {
  if (!Array.isArray(value)) return [];
  const normalizedTopics = [];
  const seenClaims = new Set();
  for (const item of value) {
    const label = String(item?.label || "").trim().slice(0, 72);
    const claim = String(item?.claim || "").trim().slice(0, 500);
    const claimKey = claim.toLocaleLowerCase("en-MY");
    if (!label || !claim || seenClaims.has(claimKey)) continue;
    normalizedTopics.push({ label, claim });
    seenClaims.add(claimKey);
    if (normalizedTopics.length === 3) break;
  }
  return normalizedTopics;
}

function renderTrendingTopics(topics, source = "fallback") {
  const normalizedTopics = normalizeTrendingTopics(topics);
  currentTrendingTopics = normalizedTopics;
  currentTrendingSource = source;
  const selectedTopics = normalizedTopics.length ? normalizedTopics : defaultTrendingTopics();
  const buttons = selectedTopics.map((topic) => {
    const button = createElement("button", "chip", topic.label);
    button.type = "button";
    button.title = t("useClaim", { claim: topic.claim });
    button.addEventListener("click", () => {
      input.value = topic.claim;
      input.dispatchEvent(new Event("input"));
      input.focus();
    });
    return button;
  });
  replaceChildren(trendingTopics, buttons);
  const usesBrave = source === "brave_news";
  trendingTopicsLabel.textContent = t(usesBrave ? "currentTopics" : "tryExample");
  trendingTopicsStatus.textContent = usesBrave
    ? t("topicsLoaded")
    : t("examplesAvailable");
}

function trendingTopicsCacheKey(userId) {
  return `${TRENDING_TOPICS_CACHE_PREFIX}${encodeURIComponent(String(userId))}`;
}

function pendingVerificationCacheKey(userId) {
  return `${PENDING_VERIFICATION_CACHE_PREFIX}${encodeURIComponent(String(userId))}`;
}

function readPendingVerification(userId) {
  try {
    const rawValue = localStorage.getItem(pendingVerificationCacheKey(userId));
    if (!rawValue) return null;
    const pending = JSON.parse(rawValue);
    const jobId = String(pending?.jobId || "").trim();
    const startedAt = Number(pending?.startedAt);
    if (!jobId || !Number.isFinite(startedAt)) return null;
    return {
      jobId,
      startedAt,
      outputLanguage: supportedLanguages.has(pending?.outputLanguage)
        ? pending.outputLanguage
        : "en",
    };
  } catch {
    return null;
  }
}

function writePendingVerification(userId, pending) {
  try {
    localStorage.setItem(pendingVerificationCacheKey(userId), JSON.stringify(pending));
  } catch {
    // The request still runs, but refresh recovery is unavailable when storage is blocked.
  }
}

function clearPendingVerification(userId) {
  try {
    localStorage.removeItem(pendingVerificationCacheKey(userId));
  } catch {
    // Ignore blocked storage; the completed job is harmless if discovered again.
  }
}

function readTrendingTopicsCache(userId) {
  try {
    const cachedValue = sessionStorage.getItem(trendingTopicsCacheKey(userId));
    if (!cachedValue) return null;
    const cached = JSON.parse(cachedValue);
    const topics = normalizeTrendingTopics(cached?.topics);
    if (!topics.length) return null;
    return {
      topics,
      source: cached?.source === "brave_news" ? "brave_news" : "fallback",
    };
  } catch {
    return null;
  }
}

function writeTrendingTopicsCache(userId, value) {
  try {
    sessionStorage.setItem(
      trendingTopicsCacheKey(userId),
      JSON.stringify({ topics: value.topics, source: value.source }),
    );
  } catch {
    // In-memory user tracking still prevents duplicate requests until this page reloads.
  }
}

async function loadTrendingTopics(userId) {
  const cached = readTrendingTopicsCache(userId);
  if (cached) {
    renderTrendingTopics(cached.topics, cached.source);
    return;
  }

  const loadGeneration = ++trendingTopicsLoadGeneration;
  let result = { topics: defaultTrendingTopics(), source: "fallback" };
  try {
    const response = await apiRequest("/trending-topics");
    const topics = normalizeTrendingTopics(response?.topics);
    if (topics.length) {
      result = {
        topics,
        source: response?.source === "brave_news" ? "brave_news" : "fallback",
      };
    }
  } catch {
    // Suggestions are non-critical; cache the safe examples and keep verification available.
  }
  writeTrendingTopicsCache(userId, result);
  if (
    loadGeneration === trendingTopicsLoadGeneration &&
    currentSession?.user?.id === userId
  ) {
    renderTrendingTopics(result.topics, result.source);
  }
}

function humanize(value) {
  if (!value) return t("unavailable");
  const translationKey = enumTranslationKeys[String(value).toLowerCase()];
  if (translationKey) return t(translationKey);
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatModelPercent(value) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? String(Math.round(numericValue * 100)) : "—";
}

function formatDate(value) {
  if (!value) return t("dateUnavailable");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return t("dateUnavailable");
  const locale = i18n.languages?.[selectedLanguage]?.locale || "en-MY";
  return new Intl.DateTimeFormat(locale, {
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

function inputType(value) {
  const normalizedValue = String(value || "").trim();
  return normalizedValue && safeHttpUrl(normalizedValue) ? "url" : "text";
}

function updateInputUi() {
  const hasInput = Boolean(input.value.trim());
  const requestRunning = activeVerificationController !== null;
  charCount.textContent = `${input.value.length} / ${input.maxLength}`;
  inputTypeBadge.textContent = t(inputType(input.value) === "url" ? "publicUrl" : "textClaim");
  inputTypeBadge.className = `input-type-badge ${inputType(input.value)}`;
  clearInputButton.disabled = !hasInput || requestRunning;
  checkButton.disabled = !hasInput || requestRunning;
}

function oauthRedirectUrl() {
  const currentPage = `${window.location.origin}${window.location.pathname}`;
  const redirectUrl = safeHttpUrl(oauthRedirectSetting || currentPage);
  if (!redirectUrl) {
    throw new Error(t("localServerRequired"));
  }
  return redirectUrl;
}

function shortRequestId(value) {
  if (!value) return t("requestIdUnavailable");
  const requestId = String(value);
  return requestId.length > 28
    ? `${requestId.slice(0, 14)}…${requestId.slice(-8)}`
    : requestId;
}

function confidenceLevel(value) {
  const confidence = Number(value);
  if (!Number.isFinite(confidence)) return t("unavailable").toUpperCase();
  if (confidence >= 0.75) return t("high");
  if (confidence >= 0.45) return t("medium");
  return t("low");
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
    createElement("div", "pipeline-step-name", t(stage.labelKey)),
    createElement("div", "pipeline-step-detail", t(stage.detailKey)),
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
      return pipelineStepElement(stage, "estimated", t("earlierEstimated"));
    }
    if (index === activeIndex) {
      return pipelineStepElement(stage, "active", t("likelyActive"));
    }
    return pipelineStepElement(stage, "queued", t("queued"));
  });
  replaceChildren(pipelineSteps, rows);
  loadingStatus.textContent = t("estimatedStage", {
    stage: t(pipelineStageDefinitions[activeIndex].labelKey),
  });
}

function updatePipelineClock() {
  if (pipelineStartedAt === null) return;
  const elapsedMilliseconds = Date.now() - pipelineStartedAt;
  pipelineElapsed.textContent = t("workedFor", { time: formatElapsed(elapsedMilliseconds) });
  renderEstimatedPipeline(elapsedMilliseconds / 1000);
}

function stopPipelineClock() {
  if (pipelineTimer !== null) window.clearInterval(pipelineTimer);
  pipelineTimer = null;
}

function startPipeline(startedAt = Date.now()) {
  stopPipelineClock();
  pipelineStartedAt = Number.isFinite(Number(startedAt)) ? Number(startedAt) : Date.now();
  lastEstimatedStageIndex = -1;
  pipelineTitle.textContent = t("pipelineWorking");
  pipelineDetails.hidden = false;
  pipelineToggle.textContent = t("hideDetails");
  pipelineToggle.setAttribute("aria-expanded", "true");
  verificationLoading.className = "verification-loading running";
  verificationLoading.hidden = false;
  stopWaitingButton.hidden = false;
  stopWaitingButton.disabled = false;
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
    pipelineStartedAt === null ? 0 : Date.now() - pipelineStartedAt;
  pipelineElapsed.textContent = t("workedFor", { time: formatElapsed(elapsedMilliseconds) });
  if (data.status === "failed") {
    pipelineTitle.textContent = t("pipelineFailed");
  } else if (data.status === "degraded") {
    pipelineTitle.textContent = t("pipelineLimited");
  } else {
    pipelineTitle.textContent = t("pipelineCompleted");
  }
  verificationLoading.className = `verification-loading ${data.status || "complete"}`;
  loadingStatus.textContent = t("backendStatus", { status: humanize(data.status) });
  pipelineProgress.style.width = "100%";
  stopWaitingButton.hidden = true;

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
      return pipelineStepElement(stage, "confirmed", t("confirmed"), metadata);
    }
    const retrievalFinished =
      stage.stageId === "sourceRetrieval" &&
      Array.isArray(data.evidence) &&
      Array.isArray(data.claims) &&
      data.claims.length > 0;
    if (retrievalFinished && !error) {
      return pipelineStepElement(
        stage,
        "confirmed",
        t("confirmed"),
        t("evidenceRecords", { count: data.evidence.length }),
      );
    }
    if (error) return pipelineStepElement(stage, "failed", t("unavailable"), error.message);
    return pipelineStepElement(stage, "skipped", t("skipped"));
  });
  replaceChildren(pipelineSteps, rows);
}

function failPipeline(message) {
  stopPipelineClock();
  lastEstimatedStageIndex = -1;
  const elapsedMilliseconds =
    pipelineStartedAt === null ? 0 : Date.now() - pipelineStartedAt;
  pipelineElapsed.textContent = t("workedFor", { time: formatElapsed(elapsedMilliseconds) });
  pipelineTitle.textContent = t("pipelineRequestFailed");
  loadingStatus.textContent = message || t("requestFailed");
  verificationLoading.className = "verification-loading failed";
  pipelineProgress.style.width = "100%";
  stopWaitingButton.hidden = true;
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

function termsDocumentForLanguage() {
  return termsBundle.documents?.[selectedLanguage] || termsBundle.documents?.en || null;
}

function termsAcceptanceKey(userId) {
  return `${TERMS_ACCEPTANCE_CACHE_PREFIX}${userId}`;
}

function hasAcceptedCurrentTerms(userId) {
  if (!userId) return false;
  if (acceptedTermsSessionUsers.has(userId)) return true;
  try {
    const storedAcceptance = JSON.parse(localStorage.getItem(termsAcceptanceKey(userId)) || "null");
    return storedAcceptance?.version === TERMS_VERSION;
  } catch {
    return false;
  }
}

function storeTermsAcceptance(userId) {
  acceptedTermsSessionUsers.add(userId);
  try {
    localStorage.setItem(
      termsAcceptanceKey(userId),
      JSON.stringify({
        version: TERMS_VERSION,
        acceptedAt: new Date().toISOString(),
        language: selectedLanguage,
      }),
    );
  } catch {
    // Current session can continue; blocked storage causes another prompt after reload.
  }
}

function updateTermsReadState() {
  const documentContent = termsDocumentForLanguage();
  if (!documentContent) return;
  const reachedEnd =
    termsScroll.scrollHeight - termsScroll.scrollTop <= termsScroll.clientHeight + 6;
  if (reachedEnd) termsReadToEnd = true;
  termsAcceptance.disabled = !termsReadToEnd;
  termsReadStatus.textContent = termsReadToEnd
    ? documentContent.readComplete
    : documentContent.scrollPrompt;
  acceptTermsButton.disabled = !(termsReadToEnd && termsAcceptance.checked);
}

function renderTermsGate({ resetReading = false } = {}) {
  const documentContent = termsDocumentForLanguage();
  if (!documentContent) return;

  termsGateTitle.textContent = documentContent.title;
  termsEffectiveDate.textContent = documentContent.effectiveDate;
  termsLanguageSelect.value = selectedLanguage;
  termsLanguageSelect.setAttribute("aria-label", documentContent.languageLabel);
  termsAcceptanceLabel.textContent = documentContent.acceptance;
  acceptTermsButton.textContent = documentContent.acceptButton;
  declineTermsButton.textContent = documentContent.declineButton;

  const fragment = document.createDocumentFragment();
  fragment.append(createElement("p", "terms-introduction", documentContent.introduction));
  documentContent.sections.forEach((section) => {
    const sectionElement = createElement("section", "terms-section");
    sectionElement.append(createElement("h3", "", section.title));
    section.paragraphs.forEach((paragraph) => {
      sectionElement.append(createElement("p", "", paragraph));
    });
    fragment.append(sectionElement);
  });
  termsScroll.replaceChildren(fragment);

  if (resetReading) {
    termsReadToEnd = false;
    termsAcceptance.checked = false;
    termsScroll.scrollTop = 0;
  }
  requestAnimationFrame(updateTermsReadState);
}

function openTermsGate(userId) {
  const sameOpenGate = activeTermsUserId === userId && !termsModal.hidden;
  activeTermsUserId = userId;
  termsModal.hidden = false;
  document.body.classList.add("auth-modal-open");
  if (!sameOpenGate) renderTermsGate({ resetReading: true });
  requestAnimationFrame(() => termsScroll.focus());
}

function closeTermsGate() {
  termsModal.hidden = true;
  activeTermsUserId = null;
  termsReadToEnd = false;
  termsAcceptance.checked = false;
  termsAcceptance.disabled = true;
  acceptTermsButton.disabled = true;
  if (loginModal.hidden) document.body.classList.remove("auth-modal-open");
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
  if (termsModal.hidden) document.body.classList.remove("auth-modal-open");
  if (previousModalFocus instanceof HTMLElement) previousModalFocus.focus();
}

function clearPrivateUi() {
  if (activeVerificationController) activeVerificationController.abort();
  activeVerificationController = null;
  pendingVerificationUserId = null;
  stopPipelineClock();
  pipelineStartedAt = null;
  verificationLoading.hidden = true;
  results.hidden = true;
  results.classList.remove("show");
  replaceChildren(document.getElementById("modelGrid"));
  replaceChildren(document.getElementById("analysisTrace"));
  replaceChildren(document.getElementById("evidenceList"));
  replaceChildren(document.getElementById("disagreementList"));
  replaceChildren(claimBreakdown);
  replaceChildren(historyList);
  historyRows = [];
  activeHistoryId = null;
  lastRenderedResult = null;
  historyCount.textContent = t("records", { count: 0 });
  setVerificationMessage("");
  updateInputUi();
}

function clearUserProfileUi() {
  userDisplayName.textContent = t("account");
  userAvatar.hidden = true;
  userAvatar.alt = "";
  userAvatar.removeAttribute("src");
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
  const termsAccepted = signedIn && hasAcceptedCurrentTerms(currentSession.user.id);
  document.querySelectorAll(".auth-only").forEach((element) => {
    element.hidden = !termsAccepted;
  });
  signedOutPrompt.hidden = signedIn;
  openLoginButton.hidden = signedIn;
  userPanel.hidden = !signedIn;

  if (!signedIn) {
    closeTermsGate();
    clearUserProfileUi();
    historyUserId = null;
    trendingTopicsUserId = null;
    trendingTopicsLoadGeneration += 1;
    renderTrendingTopics([], "fallback");
    clearPrivateUi();
    return;
  }

  closeLogin();
  if (!termsAccepted) {
    clearUserProfileUi();
    historyUserId = null;
    trendingTopicsUserId = null;
    trendingTopicsLoadGeneration += 1;
    clearPrivateUi();
    openTermsGate(currentSession.user.id);
    return;
  }

  closeTermsGate();
  void loadUserProfile(currentSession.user);
  if (trendingTopicsUserId !== currentSession.user.id) {
    trendingTopicsUserId = currentSession.user.id;
    void loadTrendingTopics(currentSession.user.id);
  }
  if (historyUserId !== currentSession.user.id) {
    historyUserId = currentSession.user.id;
    void loadHistory();
  }
  void resumePendingVerification(currentSession.user.id);
}

async function getSession() {
  if (!supabaseClient) throw new Error(t("authMissing"));
  const { data, error } = await supabaseClient.auth.getSession();
  if (error || !data.session) throw new Error(t("sessionExpired"));
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
      throw new Error(t("sessionExpired"));
    }
    const requestError = new Error(
      extractErrorMessage(responseBody, `Verification request failed with HTTP ${response.status}.`),
    );
    requestError.status = response.status;
    throw requestError;
  }
  return responseBody;
}

function waitForJobPoll(signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Polling aborted", "AbortError"));
      return;
    }
    let timeoutId = null;
    const onAbort = () => {
      if (timeoutId !== null) window.clearTimeout(timeoutId);
      reject(new DOMException("Polling aborted", "AbortError"));
    };
    timeoutId = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, VERIFICATION_JOB_POLL_INTERVAL_MS);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

async function waitForVerificationJob(jobId, controller) {
  while (!controller.signal.aborted) {
    const job = await apiRequest(
      `/verification-jobs/${encodeURIComponent(jobId)}`,
      { signal: controller.signal },
    );
    if (job?.status === "complete" && job.result) return job.result;
    if (job?.status === "failed") {
      const jobError = new Error(job.errorMessage || t("requestFailed"));
      jobError.terminal = true;
      throw jobError;
    }
    await waitForJobPoll(controller.signal);
  }
  throw new DOMException("Polling aborted", "AbortError");
}

async function showVerificationResult(data) {
  finishPipeline(data);
  renderResult(data);
  if (data.status === "degraded") {
    setVerificationMessage(t("verificationDegraded"), "warning");
  } else if (data.status === "failed") {
    setVerificationMessage(t("verificationFailed"));
  } else {
    setVerificationMessage(t("verificationComplete"), "success");
  }
  await loadHistory();
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function resumePendingVerification(userId) {
  if (activeVerificationController || pendingVerificationUserId === userId) return;
  const pending = readPendingVerification(userId);
  if (!pending) return;

  const controller = new AbortController();
  pendingVerificationUserId = userId;
  activeVerificationController = controller;
  updateInputUi();
  checkButton.setAttribute("aria-busy", "true");
  checkLabel.textContent = t("analyzing");
  results.hidden = true;
  results.classList.remove("show");
  setVerificationMessage("");
  startPipeline(pending.startedAt);

  try {
    const data = await waitForVerificationJob(pending.jobId, controller);
    clearPendingVerification(userId);
    if (activeVerificationController === controller) activeVerificationController = null;
    await showVerificationResult(data);
  } catch (error) {
    if (error.name === "AbortError") {
      const message = t("stoppedWaiting");
      failPipeline(message);
      setVerificationMessage(message, "warning");
    } else {
      if (error.terminal || [403, 404].includes(error.status)) {
        clearPendingVerification(userId);
      }
      const message = error.message || t("requestFailed");
      failPipeline(message);
      setVerificationMessage(message);
      await loadHistory();
    }
  } finally {
    if (activeVerificationController === controller) activeVerificationController = null;
    if (pendingVerificationUserId === userId) pendingVerificationUserId = null;
    checkLabel.textContent = t("runVerification");
    checkButton.removeAttribute("aria-busy");
    updateInputUi();
  }
}

function renderClaims(claims) {
  const container = document.getElementById("claimText");
  const claimItems = Array.isArray(claims) ? claims : [];
  if (!claimItems.length) {
    replaceChildren(container, [createElement("p", "claim-item", t("noClaim"))]);
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
    createElement("div", "model-provider", `${provider || t("modelUnavailable")} · ${t("viaGonka")}`),
  );
  const score = createElement("div", "model-score");
  score.append(document.createTextNode(formatModelPercent(confidence)), createElement("span", "", "%"));
  card.append(
    score,
    createElement("div", "model-conf", `${t("confidence").toUpperCase()} — ${confidenceLevel(confidence)}`),
    createElement("div", `model-tag ${tone}`, humanize(finding)),
    createElement("p", "model-summary", summary || t("analysisUnavailable")),
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
      label: t("verifier", { name: String.fromCharCode(65 + index) }),
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
        label: t("consensusJudge"),
        provider: judgeRecord?.servedModel || judgeRecord?.requestedModel,
        confidence: data.judgeResult.confidence,
        finding: data.judgeResult.verdict,
        requestId: data.judgeResult.gonkaRequestId || judgeRecord?.requestId,
        summary: data.judgeResult.reasoningSummary,
      }),
    );
  }
  if (!cards.length) cards.push(createElement("div", "empty-state", t("noModel")));
  replaceChildren(document.getElementById("modelGrid"), cards);
}

function inferenceRequestId(data, taskNames) {
  return (data.inferenceRecords || []).find((item) => taskNames.includes(item.taskName))?.requestId;
}

function traceStep(index, label, title, body, requestId) {
  const step = createElement("article", "trace-step");
  step.append(
    createElement("div", "t-idx", t("step", { index, label })),
    createElement("div", "t-title", title),
    createElement("div", "t-body", body || t("summaryUnavailable")),
  );
  const request = createElement("div", "t-req", t("requestId", {
    id: shortRequestId(requestId),
  }));
  if (requestId) request.title = String(requestId);
  step.append(request);
  return step;
}

function renderAnalysisTrace(data) {
  const claims = Array.isArray(data.claims) ? data.claims : [];
  const steps = [
    traceStep(
      1,
      t("stageClaimExtraction"),
      t("atomicClaims", { count: claims.length }),
      claims.map((claim) => claim.normalizedText || claim.originalText).join(" ") ||
        t("extractionFailed"),
      inferenceRequestId(data, ["claimExtraction"]),
    ),
  ];
  (data.agentAnalyses || []).forEach((analysis, index) => {
    steps.push(
      traceStep(
        steps.length + 1,
        t("verifier", { name: String.fromCharCode(65 + index) }),
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
        t("consensus"),
        verdictLabel(data.judgeResult.verdict),
        data.judgeResult.reasoningSummary,
        data.judgeResult.gonkaRequestId || inferenceRequestId(data, ["consensusRetry", "consensusJudge"]),
      ),
    );
  }
  if (data.biasAudit) {
    steps.push(
      traceStep(
        steps.length + 1,
        t("biasAudit"),
        t("auditStatus", { status: humanize(data.biasAudit.status) }),
        data.biasAudit.reasoningSummary,
        data.biasAudit.gonkaRequestId || inferenceRequestId(data, ["biasAuditRetry", "biasAudit"]),
      ),
    );
  }
  replaceChildren(document.getElementById("analysisTrace"), steps);
}

function assessedEvidenceStance(data, record) {
  const assessments = (data.agentAnalyses || []).flatMap((analysis) =>
    (analysis.evidenceAssessments || []).filter(
      (assessment) => assessment.evidenceId === record.evidenceId,
    ),
  );
  const support = assessments.filter((item) => item.stance === "supports").length;
  const contradict = assessments.filter((item) => item.stance === "contradicts").length;
  if (support > contradict) return "supports";
  if (contradict > support) return "contradicts";
  if (assessments.some((item) => item.stance === "neutral")) return "neutral";
  return record.stance || "unclear";
}

function evidenceQualityPercent(record) {
  const quality = record.quality || {};
  const values = [
    quality.provenance,
    quality.directness,
    quality.dateRelevance,
    quality.contextCompleteness,
    quality.corroboration,
  ].map(Number);
  if (!values.every(Number.isFinite)) return null;
  return Math.round((values.reduce((total, value) => total + value, 0) / 25) * 100);
}

function evidenceItem(data, record, index, stance) {
  const item = createElement("article", `evidence-item ${findingClass(stance)}`);
  const body = createElement("div", "evidence-body");
  const sourceUrl = safeHttpUrl(record.source?.url);
  const title = sourceUrl
    ? createElement("a", "e-title", record.source?.title || sourceUrl)
    : createElement("div", "e-title", record.source?.title || t("untitledSource"));
  if (sourceUrl) {
    title.href = sourceUrl;
    title.target = "_blank";
    title.rel = "noopener noreferrer";
    title.append(createElement("span", "external-icon", "↗"));
    title.append(createElement("span", "sr-only", t("opensTab")));
  }

  const sourceType = humanize(record.source?.sourceType || "unknown");
  const quality = evidenceQualityPercent(record);
  const badges = createElement("div", "evidence-badges");
  badges.append(
    createElement("span", `stance-badge ${findingClass(stance)}`, humanize(stance)),
    createElement("span", "source-type-badge", sourceType),
  );
  if (quality !== null) {
    const qualityBadge = createElement("span", "quality-badge", t("evidenceQuality", { quality }));
    qualityBadge.title = t("evidenceQualityHelp");
    badges.append(qualityBadge);
  }

  const claimIndexes = (record.claimIds || [])
    .map((claimId) => (data.claims || []).findIndex((claim) => claim.claimId === claimId))
    .filter((claimIndex) => claimIndex >= 0)
    .map((claimIndex) => claimIndex + 1);
  const meta = [
    record.source?.publisher,
    record.source?.publicationDate
      ? t("published", { date: formatDate(record.source.publicationDate) })
      : t("publicationUnavailable"),
    claimIndexes.length ? t("claim", { number: claimIndexes.join(", ") }) : null,
  ].filter(Boolean);
  body.append(badges, title, createElement("div", "e-date", meta.join(" · ")));

  if (record.excerpt) {
    const details = createElement("details", "evidence-details");
    details.append(
      createElement("summary", "", t("readExcerpt")),
      createElement("p", "", record.excerpt),
    );
    body.append(details);
  }
  if (record.limitations?.length) {
    const limitations = createElement("details", "evidence-details evidence-limitations");
    const list = createElement("ul", "");
    record.limitations.forEach((limitation) => list.append(createElement("li", "", limitation)));
    limitations.append(createElement("summary", "", t("sourceLimitations")), list);
    body.append(limitations);
  }
  item.append(createElement("div", "evidence-num", String(index + 1).padStart(2, "0")), body);
  return item;
}

function renderEvidence(data) {
  const evidence = Array.isArray(data.evidence) ? data.evidence : [];
  evidenceCount.textContent = t("sources", { count: evidence.length });
  if (!evidence.length) {
    replaceChildren(document.getElementById("evidenceList"), [
      createElement("div", "empty-state", t("noEvidence")),
    ]);
    return;
  }

  const groups = [
    { key: "supports", title: t("supportsClaim"), tone: "support" },
    { key: "contradicts", title: t("contradictsClaim"), tone: "danger" },
    { key: "other", title: t("neutralUnclear"), tone: "caution" },
  ];
  const indexedEvidence = evidence.map((record, index) => ({
    record,
    index,
    stance: assessedEvidenceStance(data, record),
  }));
  const sections = groups.flatMap((group) => {
    const records = indexedEvidence.filter(({ stance }) =>
      group.key === "other" ? !["supports", "contradicts"].includes(stance) : stance === group.key,
    );
    if (!records.length) return [];
    const section = createElement("section", `evidence-group ${group.tone}`);
    const heading = createElement("h4", "evidence-group-title");
    heading.append(
      createElement("span", "", group.title),
      createElement("span", "evidence-group-count", String(records.length)),
    );
    section.append(
      heading,
      ...records.map(({ record, index, stance }) => evidenceItem(data, record, index, stance)),
    );
    return [section];
  });
  replaceChildren(document.getElementById("evidenceList"), sections);
}

function renderClaimBreakdown(data) {
  const claims = Array.isArray(data.claims) ? data.claims : [];
  if (!claims.length) {
    replaceChildren(claimBreakdown, [
      createElement("div", "empty-state", t("noClaimBreakdown")),
    ]);
    return;
  }

  const cards = claims.map((claim, claimIndex) => {
    const card = createElement("article", "claim-card");
    const heading = createElement("div", "claim-card-heading");
    heading.append(
      createElement("span", "claim-number", t("claim", { number: claimIndex + 1 })),
      createElement(
        "span",
        "claim-source-count",
        t("sources", {
          count: (data.evidence || []).filter((record) =>
            record.claimIds?.includes(claim.claimId),
          ).length,
        }),
      ),
    );
    card.append(
      heading,
      createElement("h3", "claim-card-text", claim.normalizedText || claim.originalText),
    );

    const analyses = (data.agentAnalyses || []).filter(
      (analysis) => analysis.claimId === claim.claimId,
    );
    if (!analyses.length) {
      card.append(createElement("div", "empty-state", t("noModel")));
      return card;
    }
    const assessments = createElement("div", "claim-assessments");
    analyses.forEach((analysis, analysisIndex) => {
      const row = createElement("div", "claim-assessment");
      const confidence = formatModelPercent(analysis.confidence);
      row.append(
        createElement("span", "claim-verifier", t("verifier", {
          name: String.fromCharCode(65 + analysisIndex),
        })),
        createElement(
          "span",
          `stance-badge ${findingClass(analysis.stance)}`,
          humanize(analysis.stance),
        ),
        createElement(
          "span",
          "claim-confidence",
          confidence === "—"
            ? t("confidenceUnavailable")
            : t("percentConfidence", { percent: confidence }),
        ),
      );
      const summary = createElement("p", "claim-analysis-summary", analysis.reasoningSummary);
      assessments.append(row, summary);
    });
    card.append(assessments);
    return card;
  });
  replaceChildren(claimBreakdown, cards);
}

function renderDisagreement(data) {
  const disagreements = data.judgeResult?.disagreements || [];
  const agreements = data.judgeResult?.agreements || [];
  const findings = disagreements.length ? disagreements : agreements;
  document.getElementById("disagreementTitle").textContent = disagreements.length
    ? t("modelsDiverge")
    : t("modelsAgree");
  const rows = findings.map((finding, index) => {
    const row = createElement("div", "disagree-row");
    row.append(
      createElement("div", "m", t(disagreements.length ? "point" : "agree", {
        number: index + 1,
      })),
      createElement("div", "", finding),
    );
    return row;
  });
  if (!rows.length) rows.push(createElement("div", "empty-state", t("comparisonUnavailable")));
  replaceChildren(document.getElementById("disagreementList"), rows);
}

function renderNotices(data) {
  const notices = document.getElementById("resultNotices");
  const entries = [];
  if (data.status && data.status !== "complete") {
    entries.push(t("workflowStatus", { status: humanize(data.status) }));
  }
  if (data.biasAudit?.status && data.biasAudit.status !== "passed") {
    entries.push(t("auditNotice", { status: humanize(data.biasAudit.status) }));
  }
  (data.warnings || []).forEach((warning) => entries.push(t("warning", { text: warning })));
  (data.limitations || []).forEach((limitation) => entries.push(t("limitation", { text: limitation })));
  (data.errors || []).forEach((error) =>
    entries.push(`${humanize(error.stage)}: ${error.message}`),
  );
  if (!entries.length) {
    notices.hidden = true;
    replaceChildren(notices);
    return;
  }
  const uniqueEntries = [...new Set(entries)];
  const title = data.status === "degraded"
    ? t("partialResult")
    : data.status === "failed"
      ? t("verificationIncomplete")
      : t("importantContext");
  const list = createElement("ul", "");
  uniqueEntries.forEach((entry) => list.append(createElement("li", "", entry)));
  replaceChildren(notices, [createElement("h3", "", title), list]);
  notices.className = `result-notices ${data.status || "inconclusive"}`;
  notices.hidden = false;
}

function renderResult(data) {
  lastRenderedResult = data;
  const score = data.score || null;
  const verdict = score?.verdict || data.verdict || "mixed_or_inconclusive";
  animateScore(score?.truthScore);
  const verdictPill = document.getElementById("verdictPill");
  const localizedVerdict = verdictLabel(verdict);
  verdictPill.textContent = localizedVerdict;
  verdictPill.className = `verdict-pill ${findingClass(verdict)}`;
  document.getElementById("resultSummary").textContent =
    data.judgeResult?.reasoningSummary ||
    data.agentAnalyses?.[0]?.reasoningSummary ||
    t("reliableSummaryUnavailable");
  checkTime.textContent = formatDate(data.completedAt);
  const requestIds = Array.isArray(data.gonkaRequestIds) ? data.gonkaRequestIds : [];
  document.getElementById("requestCount").textContent = t("requestIds", {
    count: requestIds.length,
  });
  const confidence = Number(score?.confidenceScore);
  const confidenceText = Number.isFinite(confidence)
    ? t("confidenceScore", { score: Math.round(confidence) })
    : t("confidenceUnavailable");
  document.getElementById("confidenceScore").textContent = confidenceText;
  const supportScore = Number(score?.truthScore);
  document.getElementById("scoreAnnouncement").textContent = Number.isFinite(supportScore)
    ? t("supportAnnouncement", {
      verdict: localizedVerdict,
      score: Math.round(supportScore),
      confidence: confidenceText,
    })
    : t("supportUnavailable", {
      verdict: localizedVerdict,
      confidence: confidenceText,
    });
  renderClaims(data.claims);
  renderNotices(data);
  renderEvidence(data);
  renderClaimBreakdown(data);
  renderDisagreement(data);
  renderModels(data);
  renderAnalysisTrace(data);
  results.hidden = false;
  requestAnimationFrame(() => results.classList.add("show"));
}

function historyCategory(row) {
  const status = String(row.provider_status || row.status || "").toLowerCase();
  const verdict = String(row.final_verdict || "").toLowerCase();
  if (status === "degraded" || status === "failed") return "degraded";
  if (verdict.includes("contradicted")) return "contradicted";
  if (verdict.includes("supported")) return "supported";
  return "inconclusive";
}

function filteredHistoryRows() {
  const query = historySearch.value.trim().toLowerCase();
  const category = historyVerdictFilter.value;
  return historyRows.filter((row) => {
    const text = `${row.extracted_claim || ""} ${row.original_input || ""}`.toLowerCase();
    return (!query || text.includes(query)) &&
      (category === "all" || historyCategory(row) === category);
  });
}

function renderHistoryRows() {
  const filteredRows = filteredHistoryRows();
  const visibleRows = filteredRows;
  historyCount.textContent = filteredRows.length === historyRows.length
    ? t("records", { count: historyRows.length })
    : t("filteredRecords", { shown: filteredRows.length, total: historyRows.length });
  if (!filteredRows.length) {
    const message = historyRows.length
      ? t("noHistoryMatch")
      : t("noHistory");
    replaceChildren(historyList, [createElement("div", "empty-state", message)]);
    return;
  }
  const items = visibleRows.map((row) => {
    const rowId = row.external_verification_id || row.id;
    const button = createElement(
      "button",
      `history-item${activeHistoryId === rowId ? " active" : ""}`,
    );
    button.type = "button";
    if (activeHistoryId === rowId) button.setAttribute("aria-current", "true");
    const score = Number(row.final_truth_score);
    const scoreText = row.final_truth_score !== null && Number.isFinite(score)
      ? `${Math.round(score)}%`
      : t("noScore");
    const status = row.final_verdict || row.provider_status || row.status;
    const meta = createElement("span", "history-meta");
    meta.append(
      createElement("span", `history-verdict ${historyCategory(row)}`, humanize(status)),
      createElement("span", "", scoreText),
      createElement("span", "", formatDate(row.completed_at || row.created_at)),
    );
    button.append(
      createElement(
        "span",
        "history-claim",
        row.extracted_claim || row.original_input || t("untitledVerification"),
      ),
      meta,
    );
    button.addEventListener("click", async () => {
      button.disabled = true;
      button.classList.add("loading");
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
            throw new Error(t("fullReportUnavailable"));
          }
          renderResult(data.raw_result);
        }
        activeHistoryId = rowId;
        renderHistoryRows();
        results.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (error) {
        setVerificationMessage(error.message || t("historyLoadFailed"));
      } finally {
        button.disabled = false;
        button.classList.remove("loading");
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
  historySearch.disabled = true;
  historyVerdictFilter.disabled = true;
  replaceChildren(historyList, [createElement("div", "empty-state", t("loadingHistory"))]);
  historyCount.textContent = t("loadingHistory");
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
  historySearch.disabled = false;
  historyVerdictFilter.disabled = false;
  if (currentSession?.user?.id !== expectedUserId) return;
  if (historyError) {
    historyRows = [];
    historyCount.textContent = t("unavailable");
    replaceChildren(historyList, [
      createElement("div", "empty-state error-text", t("historyUnavailable")),
    ]);
    return;
  }
  historyRows = rows;
  renderHistoryRows();
}

async function runCheck() {
  const claim = input.value.trim();
  if (!currentSession) {
    openLogin(t("signInBeforeVerification"));
    return;
  }
  if (!claim) {
    setVerificationMessage(t("enterClaim"));
    input.focus();
    return;
  }

  const controller = new AbortController();
  const userId = currentSession.user.id;
  const outputLanguage = selectedLanguage;
  const startedAt = Date.now();
  activeVerificationController = controller;
  updateInputUi();
  checkButton.setAttribute("aria-busy", "true");
  checkLabel.textContent = t("analyzing");
  results.hidden = true;
  results.classList.remove("show");
  setVerificationMessage("");
  startPipeline(startedAt);

  try {
    const job = await apiRequest("/verification-jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input: claim, outputLanguage }),
      signal: controller.signal,
    });
    if (!job?.jobId) throw new Error(t("requestFailed"));
    writePendingVerification(userId, {
      jobId: job.jobId,
      startedAt,
      outputLanguage,
    });
    const data = await waitForVerificationJob(job.jobId, controller);
    clearPendingVerification(userId);
    if (activeVerificationController === controller) activeVerificationController = null;
    await showVerificationResult(data);
  } catch (error) {
    if (error.name === "AbortError") {
      const message = t("stoppedWaiting");
      failPipeline(message);
      setVerificationMessage(message, "warning");
    } else {
      if (error.terminal || [403, 404].includes(error.status)) {
        clearPendingVerification(userId);
      }
      const message = error.message || t("requestFailed");
      failPipeline(message);
      setVerificationMessage(message);
      if (!currentSession) openLogin(t("sessionExpired"));
    }
  } finally {
    if (activeVerificationController === controller) activeVerificationController = null;
    checkLabel.textContent = t("runVerification");
    checkButton.removeAttribute("aria-busy");
    updateInputUi();
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
  themeToggle.setAttribute("aria-label", t(nextTheme === "light" ? "useLightTheme" : "useDarkTheme"));
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

async function beginOAuth(provider) {
  if (!supabaseClient) {
    authMessage.textContent = t("authMissing");
    return;
  }
  const isGithub = provider === "github";
  googleLoginButton.disabled = true;
  githubLoginButton.disabled = true;
  authMessage.textContent = t(isGithub ? "redirectingGithub" : "redirectingGoogle");
  try {
    const { error } = await supabaseClient.auth.signInWithOAuth({
      provider,
      options: { redirectTo: oauthRedirectUrl() },
    });
    if (error) throw error;
  } catch (error) {
    authMessage.textContent = error.message || t(isGithub ? "githubLoginFailed" : "googleLoginFailed");
    googleLoginButton.disabled = false;
    githubLoginButton.disabled = false;
  }
}

input.addEventListener("input", updateInputUi);
input.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") void runCheck();
});
checkButton.addEventListener("click", () => void runCheck());
clearInputButton.addEventListener("click", () => {
  input.value = "";
  updateInputUi();
  input.focus();
});
stopWaitingButton.addEventListener("click", () => {
  stopWaitingButton.disabled = true;
  activeVerificationController?.abort();
});
historyRefresh.addEventListener("click", () => void loadHistory());
historySearch.addEventListener("input", () => {
  renderHistoryRows();
});
historyVerdictFilter.addEventListener("change", () => {
  renderHistoryRows();
});
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

termsLanguageSelect.addEventListener("change", () => {
  applyLanguage(termsLanguageSelect.value);
});
termsScroll.addEventListener("scroll", updateTermsReadState);
termsAcceptance.addEventListener("change", updateTermsReadState);
termsModal.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    event.preventDefault();
    return;
  }
  if (event.key !== "Tab") return;
  const focusable = [
    ...termsModal.querySelectorAll("button, select, input:not([disabled]), [tabindex='0']"),
  ].filter((element) => !element.disabled && !element.hidden);
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

acceptTermsButton.addEventListener("click", () => {
  if (!activeTermsUserId || !termsReadToEnd || !termsAcceptance.checked) return;
  storeTermsAcceptance(activeTermsUserId);
  updateAuthUi(currentSession);
});

declineTermsButton.addEventListener("click", async () => {
  if (!supabaseClient) return;
  declineTermsButton.disabled = true;
  const { error } = await supabaseClient.auth.signOut({ scope: "local" });
  declineTermsButton.disabled = false;
  if (error) termsReadStatus.textContent = error.message || t("signOutFailed");
});

googleLoginButton.addEventListener("click", () => void beginOAuth("google"));
githubLoginButton.addEventListener("click", () => void beginOAuth("github"));

logoutButton.addEventListener("click", async () => {
  logoutButton.disabled = true;
  const { error } = await supabaseClient.auth.signOut({ scope: "local" });
  logoutButton.disabled = false;
  if (error) setVerificationMessage(error.message || t("signOutFailed"));
});
languageSelect.addEventListener("change", () => applyLanguage(languageSelect.value));
themeToggle.addEventListener("click", () => {
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
});
pipelineToggle.addEventListener("click", () => {
  const isExpanded = pipelineToggle.getAttribute("aria-expanded") === "true";
  pipelineDetails.hidden = isExpanded;
  pipelineToggle.setAttribute("aria-expanded", String(!isExpanded));
  pipelineToggle.textContent = t(isExpanded ? "showDetails" : "hideDetails");
});

initializeLanguage();
initializeTheme();
renderTrendingTopics([], "fallback");
updateInputUi();
void initializeAuth();
