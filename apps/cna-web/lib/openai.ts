import { AzureOpenAI } from "openai";
import { DefaultAzureCredential, getBearerTokenProvider } from "@azure/identity";
import type { FindingSeverity } from "@prisma/client";

export interface RawFinding {
  title: string;
  severity: FindingSeverity;
  category: string;
  description: string;
  recommendation: string;
}

function getClient(): AzureOpenAI {
  const endpoint = process.env.AZURE_OPENAI_ENDPOINT;
  if (!endpoint) throw new Error("AZURE_OPENAI_ENDPOINT is not set");

  const credential = new DefaultAzureCredential();
  const azureADTokenProvider = getBearerTokenProvider(
    credential,
    "https://cognitiveservices.azure.com/.default",
  );

  return new AzureOpenAI({
    endpoint,
    azureADTokenProvider,
    apiVersion: process.env.AZURE_OPENAI_API_VERSION ?? "2024-12-01-preview",
    deployment: process.env.AZURE_OPENAI_DEPLOYMENT ?? "gpt-4o",
  });
}

export type AnalysisFocus =
  | "general"
  | "zero_trust"
  | "compliance_nist"
  | "compliance_cis"
  | "well_architected"
  | "remediation_priority";

const FOCUS_PROMPTS: Record<AnalysisFocus, string> = {
  general:
    "Identify all network security findings across all categories.",
  zero_trust:
    "Focus on Zero Trust architecture gaps: micro-segmentation, identity-based access, lateral movement risks, implicit trust zones.",
  compliance_nist:
    "Evaluate against NIST SP 800-53 network controls (SC-7 Boundary Protection, AC-4 Information Flow, SI-3 Malicious Code Protection). Map each finding to the relevant NIST control.",
  compliance_cis:
    "Evaluate against CIS Azure Foundations Benchmark and CIS Controls v8. Map each finding to the relevant CIS control number.",
  well_architected:
    "Evaluate against the Azure Well-Architected Framework Security pillar. Focus on defense in depth, least privilege, and network segmentation best practices from WAF guidance.",
  remediation_priority:
    "Identify findings that represent the highest-impact quick wins. Prioritize based on exploitability, blast radius, and remediation effort. Flag anything that can be fixed in under 1 day.",
};

/**
 * Analyze network assessment documents and return structured findings.
 * Documents must have extracted text (parsedText) to be included.
 * focus controls the analysis lens applied by the AI.
 */
export async function analyzeDocuments(
  documents: { fileName: string; text: string }[],
  focus: AnalysisFocus = "general",
): Promise<RawFinding[]> {
  const client = getClient();

  const docSummary = documents
    .map((d, i) => `--- Document ${i + 1}: ${d.fileName} ---\n${d.text}`)
    .join("\n\n");

  const focusInstruction = FOCUS_PROMPTS[focus];

  const systemPrompt = `You are a senior cloud network security analyst performing a Cloud Network Assessment (CNA).
${focusInstruction}
Each finding must be actionable and specific to the evidence in the documents.
Avoid duplicating findings that were already identified from live discovery.
Return ONLY a JSON object in this exact format:
{
  "findings": [
    {
      "title": "string — concise finding title",
      "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFORMATIONAL",
      "category": "string — e.g. Network Segmentation, Access Control, Encryption, Compliance, Configuration",
      "description": "string — detailed explanation of the issue and its risk",
      "recommendation": "string — specific remediation steps"
    }
  ]
}`;

  const userPrompt = `Analyze these network assessment documents and identify security findings:\n\n${docSummary}`;

  const deployment = process.env.AZURE_OPENAI_DEPLOYMENT ?? "gpt-4o";
  const response = await client.chat.completions.create({
    model: deployment,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userPrompt },
    ],
    response_format: { type: "json_object" },
    temperature: 0.2,
  });

  const raw = response.choices[0]?.message?.content ?? "{}";
  const parsed = JSON.parse(raw) as { findings?: RawFinding[] };
  return parsed.findings ?? [];
}
