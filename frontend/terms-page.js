"use strict";

const termsBundle = window.TRUTHSCOPE_TERMS || {};
const termsLanguages = new Set(["en", "ms", "zh-CN"]);
const termsLanguageSelect = document.getElementById("termsPageLanguage");
const termsDocument = document.getElementById("termsPageDocument");

function createTermsElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function selectedTermsLanguage() {
  const urlLanguage = new URLSearchParams(window.location.search).get("lang");
  if (termsLanguages.has(urlLanguage)) return urlLanguage;
  try {
    const savedLanguage = localStorage.getItem("truthscope-language");
    if (termsLanguages.has(savedLanguage)) return savedLanguage;
  } catch {
    // English remains default when storage is blocked.
  }
  return "en";
}

function renderTermsPage(language) {
  const normalizedLanguage = termsLanguages.has(language) ? language : "en";
  const documentContent = termsBundle.documents?.[normalizedLanguage] || termsBundle.documents?.en;
  if (!documentContent) return;

  document.documentElement.lang = normalizedLanguage;
  document.title = `${documentContent.title} — TruthScope`;
  termsLanguageSelect.value = normalizedLanguage;
  termsLanguageSelect.setAttribute("aria-label", documentContent.languageLabel);

  const fragment = document.createDocumentFragment();
  fragment.append(
    createTermsElement("h1", "terms-page-title", documentContent.title),
    createTermsElement("p", "terms-effective mono", documentContent.effectiveDate),
    createTermsElement("p", "terms-introduction", documentContent.introduction),
  );
  documentContent.sections.forEach((section) => {
    const sectionElement = createTermsElement("section", "terms-section");
    sectionElement.append(createTermsElement("h2", "", section.title));
    section.paragraphs.forEach((paragraph) => {
      sectionElement.append(createTermsElement("p", "", paragraph));
    });
    fragment.append(sectionElement);
  });
  const repositoryLink = createTermsElement("a", "terms-repository", documentContent.repositoryLabel);
  repositoryLink.href = "https://github.com/ChaoChuan05/TruthScope";
  repositoryLink.target = "_blank";
  repositoryLink.rel = "noopener noreferrer";
  fragment.append(repositoryLink);
  termsDocument.replaceChildren(fragment);

  const url = new URL(window.location.href);
  url.searchParams.set("lang", normalizedLanguage);
  window.history.replaceState({}, "", url);
}

termsLanguageSelect.addEventListener("change", () => {
  renderTermsPage(termsLanguageSelect.value);
});

try {
  const savedTheme = localStorage.getItem("truthscope-theme");
  document.documentElement.dataset.theme = savedTheme === "light" ? "light" : "dark";
} catch {
  document.documentElement.dataset.theme = "dark";
}

renderTermsPage(selectedTermsLanguage());
