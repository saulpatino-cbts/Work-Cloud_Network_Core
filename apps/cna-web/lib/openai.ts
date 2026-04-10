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

/**
 * Analyze network assessment documents and return structured findings.
 * Documents must have extracted text (parsedText) to be included.
 */
export async function analyzeDocuments(
  documents: { fileName: string; text: string }[],
): Promise<RawFinding[]> {
  const client = getClient();

  const docSummary = documents
    .map((d, i) => `--- Document ${i + 1}: ${d.fileName} ---\n${d.text}`)
    .join("\n\n");

  const systemPrompt = `You are a senior cloud network security analyst performing a Cloud Network Assessment (CNA).
Analyze the provided network documentation and identify security findings.
Each finding must be actionable and specific to the evidence in the documents.
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

  const userPrompt = `Analyze these network assessment documents and identify all security findings:\n\n${docSummary}`;

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
