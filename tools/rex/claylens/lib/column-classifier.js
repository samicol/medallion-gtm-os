// Classify a Clay AI column by its likely use case + risk class.
//
// Heuristic, not authoritative: written into ClayLens output so reviewers can
// override manually.

export const RISK_PENALTY = Object.freeze({
  LOW: 0.0,
  MEDIUM: 0.3,
  HIGH: 0.7,
});

const _COPY_RE = new RegExp(
  "\\b(" +
    "email|e-mail|mail|" +
    "dm|message|msg|" +
    "copy|reply|" +
    "subject[_\\s-]*line|subject|" +
    "intro|opener|icebreaker|ice-breaker|" +
    "linkedin\\s*dm|linkedin\\s*message|" +
    "invite|invitation|" +
    "follow[_\\s-]*up" +
    ")\\b",
  "i",
);

const _CLASSIFY_RE = new RegExp(
  "\\b(" +
    "icp|qualify|qualification|qualified|" +
    "classif|categor|" +
    "normali[sz]|cleanup|clean|clean[_\\s-]*up|" +
    "extract|parse|format|" +
    "industry|segment|" +
    "scor|scoring|rating|rank|" +
    "validate|validation" +
    ")\\b",
  "i",
);

const _RESEARCH_RE = new RegExp(
  "\\b(" +
    "signal|trigger|analysis|" +
    "detect|detection|usage|" +
    "research|intel|intelligence|" +
    "trigger|event|news|" +
    "tech[_\\s-]*stack|stack|" +
    "pain|objection|competitor" +
    ")\\b",
  "i",
);

/**
 * Return { useCase, riskClass } for a column.
 *
 * useCase:   copy | classification | research | claygent | ai
 * riskClass: LOW  | MEDIUM          | HIGH
 *
 * Name-based copy match takes precedence over claygent useCase; some
 * copywriting columns set useCase="claygent" as a config artifact but are pure
 * copy generation (no web research).
 *
 * @param {string} columnName
 * @param {string|null|undefined} actionUseCase
 * @returns {{useCase: string, riskClass: string}}
 */
export function classify(columnName, actionUseCase) {
  const uc = String(actionUseCase || "").trim().replace(/^"+|"+$/g, "").toLowerCase();
  const name = columnName || "";

  // Copy match always wins: voice-fidelity risk is what matters regardless
  // of the underlying useCase config.
  if (_COPY_RE.test(name)) {
    return { useCase: "copy", riskClass: "HIGH" };
  }

  if (uc === "claygent") {
    return { useCase: "claygent", riskClass: "MEDIUM" };
  }

  if (_CLASSIFY_RE.test(name)) {
    return { useCase: "classification", riskClass: "LOW" };
  }
  if (_RESEARCH_RE.test(name)) {
    return { useCase: "research", riskClass: "MEDIUM" };
  }

  return { useCase: "ai", riskClass: "MEDIUM" };
}
