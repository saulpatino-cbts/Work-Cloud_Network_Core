import { DefaultAzureCredential, getBearerTokenProvider } from "@azure/identity";
import { AzureOpenAI } from "openai";

import { prisma } from "@/lib/prisma";

export const AI_ENGINE_SETTING_KEY = "ai.activeEngine";

export type AiEngineId = "azure-openai" | "foundry-claude";

export type AiChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

export type AiCompletionOptions = {
  messages: AiChatMessage[];
  maxCompletionTokens: number;
  responseFormat?: "json_object";
};

export type AiEngineStatus = {
  id: AiEngineId;
  label: string;
  description: string;
  configured: boolean;
  active: boolean;
  details: Array<{ label: string; value: string }>;
  missing: string[];
};

export type McpServerStatus = {
  id: string;
  label: string;
  endpoint: string;
  transport: string;
  configured: boolean;
};

const VALID_ENGINES = new Set<AiEngineId>(["azure-openai", "foundry-claude"]);

function clean(value: string | null | undefined): string {
  const trimmed = value?.trim() ?? "";
  return trimmed.toLowerCase() === "none" ? "" : trimmed;
}

function maskSecret(value: string): string {
  if (!value) return "Not configured";
  if (value.length <= 8) return "Configured";
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

function hostOnly(value: string): string {
  if (!value) return "Not configured";
  try {
    return new URL(value).host;
  } catch {
    return value;
  }
}

export function normalizeAiEngine(value: string | null | undefined): AiEngineId | null {
  const normalized = clean(value) as AiEngineId;
  return VALID_ENGINES.has(normalized) ? normalized : null;
}

export function getConfiguredDefaultAiEngine(): AiEngineId {
  return normalizeAiEngine(process.env.CNA_AI_ENGINE_DEFAULT) ?? "foundry-claude";
}

export function getMcpServerStatuses(): McpServerStatus[] {
  const azureEndpoint = clean(process.env.CNA_AZURE_MCP_ENDPOINT ?? process.env.AZURE_MCP_SERVER_URL);
  const awsEndpoint = clean(process.env.CNA_AWS_MCP_ENDPOINT ?? process.env.AWS_MCP_SERVER_URL);
  const drawioEndpoint = clean(process.env.CNA_DRAWIO_MCP_URL);

  return [
    {
      id: "azure-mcp",
      label: "Azure MCP",
      endpoint: azureEndpoint || "Not configured",
      transport: clean(process.env.CNA_AZURE_MCP_TRANSPORT) || "streamable-http",
      configured: Boolean(azureEndpoint),
    },
    {
      id: "aws-mcp",
      label: "AWS MCP",
      endpoint: awsEndpoint || "Not configured",
      transport: clean(process.env.CNA_AWS_MCP_TRANSPORT) || "streamable-http",
      configured: Boolean(awsEndpoint),
    },
    {
      id: "drawio-mcp",
      label: "draw.io MCP",
      endpoint: drawioEndpoint || "Not configured",
      transport: "http",
      configured: Boolean(drawioEndpoint),
    },
  ];
}

export function getAiEngineStatuses(activeEngine: AiEngineId): AiEngineStatus[] {
  const azureEndpoint = clean(process.env.AZURE_OPENAI_ENDPOINT);
  const azureDeployment = clean(process.env.AZURE_OPENAI_DEPLOYMENT) || "gpt-5.2-chat";
  const azureApiVersion = clean(process.env.AZURE_OPENAI_API_VERSION) || "2024-12-01-preview";

  const claudeEndpoint = clean(process.env.FOUNDRY_CLAUDE_ENDPOINT);
  const claudeModel = clean(process.env.FOUNDRY_CLAUDE_MODEL) || "claude-sonnet-4-6";
  const claudeApiKey = clean(process.env.FOUNDRY_CLAUDE_API_KEY);

  return [
    {
      id: "azure-openai",
      label: "Azure OpenAI",
      description: "Optional out-of-band provider. Promote to first-class only after Terraform provisions Azure OpenAI networking, RBAC, deployment, and env vars.",
      configured: Boolean(azureEndpoint && azureDeployment),
      active: activeEngine === "azure-openai",
      details: [
        { label: "Endpoint", value: hostOnly(azureEndpoint) },
        { label: "Deployment", value: azureDeployment },
        { label: "API version", value: azureApiVersion },
        { label: "Authentication", value: "Managed identity" },
      ],
      missing: [
        ...(!azureEndpoint ? ["AZURE_OPENAI_ENDPOINT"] : []),
        ...(!azureDeployment ? ["AZURE_OPENAI_DEPLOYMENT"] : []),
      ],
    },
    {
      id: "foundry-claude",
      label: "Foundry Claude Sonnet 4.6",
      description: "Terraform-managed private Foundry deployment using managed identity by default, with API key fallback only when explicitly configured.",
      configured: Boolean(claudeEndpoint && claudeModel),
      active: activeEngine === "foundry-claude",
      details: [
        { label: "Endpoint", value: hostOnly(claudeEndpoint) },
        { label: "Model", value: claudeModel },
        {
          label: "Authentication",
          value: claudeApiKey ? `API key fallback (${maskSecret(claudeApiKey)})` : "Managed identity",
        },
      ],
      missing: [
        ...(!claudeEndpoint ? ["FOUNDRY_CLAUDE_ENDPOINT"] : []),
        ...(!claudeModel ? ["FOUNDRY_CLAUDE_MODEL"] : []),
      ],
    },
  ];
}

export async function getActiveAiEngine(): Promise<AiEngineId> {
  const setting = await prisma.appSetting.findUnique({
    where: { key: AI_ENGINE_SETTING_KEY },
    select: { value: true },
  });

  const stored = normalizeAiEngine(setting?.value);
  if (stored) return stored;

  return getConfiguredDefaultAiEngine();
}

export async function setActiveAiEngine(engine: AiEngineId, updatedBy?: string): Promise<void> {
  if (!VALID_ENGINES.has(engine)) {
    throw new Error(`Unsupported AI engine: ${engine}`);
  }

  const status = getAiEngineStatuses(engine).find((item) => item.id === engine);
  if (!status?.configured) {
    throw new Error(`${status?.label ?? engine} is not fully configured.`);
  }

  await prisma.appSetting.upsert({
    where: { key: AI_ENGINE_SETTING_KEY },
    create: {
      key: AI_ENGINE_SETTING_KEY,
      value: engine,
      updatedBy,
    },
    update: {
      value: engine,
      updatedBy,
    },
  });
}

export async function getAiEngineDashboardState(): Promise<{
  activeEngine: AiEngineId;
  defaultEngine: AiEngineId;
  engines: AiEngineStatus[];
  mcpServers: McpServerStatus[];
}> {
  const activeEngine = await getActiveAiEngine();
  return {
    activeEngine,
    defaultEngine: getConfiguredDefaultAiEngine(),
    engines: getAiEngineStatuses(activeEngine),
    mcpServers: getMcpServerStatuses(),
  };
}

function getAzureClient(): AzureOpenAI {
  const endpoint = clean(process.env.AZURE_OPENAI_ENDPOINT);
  if (!endpoint) throw new Error("AZURE_OPENAI_ENDPOINT is not set");

  const credential = new DefaultAzureCredential();
  const azureADTokenProvider = getBearerTokenProvider(
    credential,
    "https://cognitiveservices.azure.com/.default",
  );

  return new AzureOpenAI({
    endpoint,
    azureADTokenProvider,
    apiVersion: clean(process.env.AZURE_OPENAI_API_VERSION) || "2024-12-01-preview",
    deployment: clean(process.env.AZURE_OPENAI_DEPLOYMENT) || "gpt-5.2-chat",
  });
}

async function getFoundryAuthHeaders(apiKey: string): Promise<Record<string, string>> {
  if (apiKey) {
    return {
      "api-key": apiKey,
      "x-api-key": apiKey,
    };
  }

  const credential = new DefaultAzureCredential();
  const tokenProvider = getBearerTokenProvider(
    credential,
    "https://cognitiveservices.azure.com/.default",
  );
  const token = await tokenProvider();

  return {
    Authorization: `Bearer ${token}`,
  };
}

function toClaudeMessages(messages: AiChatMessage[]): {
  system?: string;
  messages: Array<{ role: "user" | "assistant"; content: string }>;
} {
  const system = messages
    .filter((message) => message.role === "system")
    .map((message) => message.content)
    .join("\n\n");

  const claudeMessages = messages
    .filter((message) => message.role !== "system")
    .map((message) => ({
      role: message.role as "user" | "assistant",
      content: message.content,
    }));

  return {
    system: system || undefined,
    messages: claudeMessages.length ? claudeMessages : [{ role: "user", content: "" }],
  };
}

async function completeWithAzure(options: AiCompletionOptions): Promise<string> {
  const client = getAzureClient();
  const deployment = clean(process.env.AZURE_OPENAI_DEPLOYMENT) || "gpt-5.2-chat";

  const response = await client.chat.completions.create({
    model: deployment,
    messages: options.messages,
    response_format: options.responseFormat ? { type: options.responseFormat } : undefined,
    max_completion_tokens: options.maxCompletionTokens,
  });

  return response.choices[0]?.message?.content ?? "";
}

async function completeWithClaude(options: AiCompletionOptions): Promise<string> {
  const endpoint = clean(process.env.FOUNDRY_CLAUDE_ENDPOINT);
  const model = clean(process.env.FOUNDRY_CLAUDE_MODEL) || "claude-sonnet-4-6";
  const apiKey = clean(process.env.FOUNDRY_CLAUDE_API_KEY);

  if (!endpoint) {
    throw new Error("Foundry Claude endpoint must be configured before use.");
  }

  const claudePayload = toClaudeMessages(options.messages);
  const authHeaders = await getFoundryAuthHeaders(apiKey);
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "anthropic-version": "2023-06-01",
      ...authHeaders,
    },
    body: JSON.stringify({
      model,
      max_tokens: options.maxCompletionTokens,
      system: claudePayload.system,
      messages: claudePayload.messages,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Foundry Claude request failed (${response.status}): ${body.slice(0, 500)}`);
  }

  const data = await response.json() as {
    content?: Array<{ type?: string; text?: string }>;
    output_text?: string;
    choices?: Array<{ message?: { content?: string } }>;
  };

  if (typeof data.output_text === "string") return data.output_text;
  if (typeof data.choices?.[0]?.message?.content === "string") {
    return data.choices[0].message.content;
  }

  return (data.content ?? [])
    .map((part) => part.text ?? "")
    .filter(Boolean)
    .join("\n");
}

export async function generateAiCompletion(options: AiCompletionOptions): Promise<string> {
  const activeEngine = await getActiveAiEngine();
  const statuses = getAiEngineStatuses(activeEngine);
  const activeStatus = statuses.find((item) => item.id === activeEngine);

  if (activeStatus?.configured) {
    return activeEngine === "foundry-claude"
      ? completeWithClaude(options)
      : completeWithAzure(options);
  }

  const fallback = statuses.find((item) => item.configured);
  if (fallback?.id === "azure-openai") return completeWithAzure(options);
  if (fallback?.id === "foundry-claude") return completeWithClaude(options);

  throw new Error("No AI engine is configured. Configure Foundry Claude on the AI Engine page before running analysis.");
}
