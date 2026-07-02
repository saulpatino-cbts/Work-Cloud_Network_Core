// ──────────────────────────────────────────────────────────────────────────────
// Prompt construction for the sectioned Comprehensive Assessment.
// One system+user pair per section; the synthesis pass writes the Executive
// Summary from per-section summaries after all domain sections complete.
// ──────────────────────────────────────────────────────────────────────────────

import type { SectionSpec } from "@/lib/report-sections";

export interface ReportMeta {
  clientOrg: string;
  engagementName: string;
  title: string;
  date: string; // YYYY-MM-DD
}

export const SUMMARY_TRAILER_RE = /<!--\s*SUMMARY:\s*([\s\S]*?)-->/;

/**
 * Grounding rules shared by every section call. The depth bar is the NSA
 * Network Infrastructure Security Guide: every observation gets a why-it-
 * matters rationale and concrete, executable remediation.
 */
const SHARED_SYSTEM = (meta: ReportMeta) => `You are a CBTS principal network architect writing one section of a formal Cloud Network Assessment report for ${meta.clientOrg} (engagement: ${meta.engagementName}, dated ${meta.date}).

DEPTH BAR: NSA "Network Infrastructure Security Guide" caliber — a numbered technical publication. For every issue: what was observed, why it matters (attack path / failure mode / business impact), and specific remediation with exact Azure portal paths, CLI commands, or policy patterns. Insight-dense prose, no filler, no generic advice that ignores the data.

GROUNDING RULES (non-negotiable):
- Use ONLY facts present in the ENGAGEMENT DATA below. Never invent resources, findings, metrics, or vendor claims.
- Cite finding titles verbatim when discussing them, e.g. (finding: "Subnet without NSG").
- Mark every numeric estimate or static-price approximation with [VERIFY].
- Mark judgment calls that need consultant sign-off with [REVIEW REQUIRED].
- If the data for an aspect of your charter is missing or incomplete, say so explicitly ("not assessed — no data") instead of inferring.

FORMAT:
- Professional Markdown. Root heading is "## {section number}. {section title}" exactly as given; subsections use "###" numbered {n}.1, {n}.2, …
- Use tables for enumerable facts, prose for analysis. ASCII/Unicode diagrams where topology is discussed.
- No preamble, no closing summary sentence about the report itself.
- End with an HTML comment "<!--SUMMARY: ...-->" containing a ≤80-word summary of this section's key conclusions (used to build the executive summary — write it for an executive).`;

export function buildSectionMessages(
  spec: SectionSpec,
  sliceText: string,
  meta: ReportMeta,
  msLearnContext?: string,
): { system: string; user: string } {
  const charter = spec.charter.map((c) => `- ${c}`).join("\n");
  return {
    system: SHARED_SYSTEM(meta),
    user: `Write Section ${spec.number}: "${spec.title}".

SECTION CHARTER — this section must cover:
${charter}

=== ENGAGEMENT DATA (the only source of truth for this section) ===
${sliceText}
${msLearnContext ? `\n${msLearnContext}\n(Reference these Microsoft Learn links inline where relevant — they are verified.)` : ""}

Begin with the heading "## ${spec.number}. ${spec.title}".`,
  };
}

// ── Synthesis pass (Executive Summary) ────────────────────────────────────────

export function buildSynthesisMessages(
  meta: ReportMeta,
  sectionSummaries: Array<{ number: number; title: string; summary: string }>,
  findingStats: { total: number; bySeverity: Array<{ severity: string; count: number }> },
): { system: string; user: string } {
  return {
    system: `You are a CBTS principal network architect writing the Executive Summary of a formal Cloud Network Assessment for ${meta.clientOrg} (${meta.engagementName}, ${meta.date}).

RULES:
- Ground every statement in the section summaries and finding statistics provided — nothing else.
- Open with a 2-3 sentence plain-English risk posture statement (no jargon).
- Then: key themes across the assessment (3-6 bullets, each referencing the section number where detail lives, e.g. "(§5)").
- Then: a severity breakdown table.
- Then: "Top Priorities" — the 3-5 highest-impact actions, business-outcome framed.
- Executive tone; no CLI commands; ≤700 words.
- Output professional Markdown starting with the heading "## 1. Executive Summary". No preamble.`,
    user: `Finding statistics: ${findingStats.total} findings total — ${findingStats.bySeverity.map((s) => `${s.count} ${s.severity}`).join(", ")}.

Section summaries:
${sectionSummaries.map((s) => `§${s.number} ${s.title}: ${s.summary}`).join("\n\n")}`,
  };
}
