/**
 * Pure AI-engine selection rules — no Prisma, no SDKs, no env reads — so the
 * web tier and cna/ai_engine/chat_agent.py can be held to one shared vector
 * table (see ai-engine-rules.test.ts / tests/unit/test_chat_agent.py).
 *
 * The appliance's deploy-time AI mode (CNA_AI_MODE) decides which engine
 * family is allowed:
 *   saas     — the cloud-native engine for this appliance's cloud:
 *              azure-openai on Azure, bedrock on AWS.
 *   byo-api  — only Anthropic/OpenAI IDs explicitly allowed by
 *              CNA_BYO_AI_PROVIDERS, keyed by an admin-entered API key.
 */

export type AiEngineId = "azure-openai" | "bedrock" | "anthropic" | "openai";
export type AiMode = "saas" | "byo-api";
export type ApplianceCloud = "azure" | "aws";
export type ByoProvider = "anthropic" | "openai";

export const VALID_ENGINES: ReadonlySet<AiEngineId> = new Set<AiEngineId>([
  "azure-openai",
  "bedrock",
  "anthropic",
  "openai",
]);

export const SAAS_ENGINE_BY_CLOUD: Readonly<Record<ApplianceCloud, AiEngineId>> = {
  azure: "azure-openai",
  aws: "bedrock",
};

// Complete provider ID set. The configured JSON array order supplies the
// deterministic tie-break when multiple enabled keys are configured.
export const BYO_ENGINES: readonly ByoProvider[] = ["anthropic", "openai"];
export const BYO_AI_PROVIDERS_ENV = "CNA_BYO_AI_PROVIDERS";

const BYO_AI_PROVIDERS_ERROR =
  `${BYO_AI_PROVIDERS_ENV} must be a non-empty JSON array of unique provider IDs: anthropic, openai.`;

export function clean(value: string | null | undefined): string {
  const trimmed = value?.trim() ?? "";
  return trimmed.toLowerCase() === "none" ? "" : trimmed;
}

export function normalizeAiMode(value: string | null | undefined): AiMode {
  return clean(value) === "byo-api" ? "byo-api" : "saas";
}

export function normalizeApplianceCloud(value: string | null | undefined): ApplianceCloud {
  return clean(value) === "aws" ? "aws" : "azure";
}

export function normalizeAiEngine(value: string | null | undefined): AiEngineId | null {
  const normalized = clean(value) as AiEngineId;
  return VALID_ENGINES.has(normalized) ? normalized : null;
}

export function isByoProvider(value: string): value is ByoProvider {
  return (BYO_ENGINES as readonly string[]).includes(value);
}

export class AiEngineConfigurationError extends Error {}

/** Parse the strict deploy-time BYO provider allowlist without echoing its value. */
export function parseByoAiProviders(value: string | null | undefined): ByoProvider[] {
  if (!value?.trim()) throw new AiEngineConfigurationError(BYO_AI_PROVIDERS_ERROR);

  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new AiEngineConfigurationError(BYO_AI_PROVIDERS_ERROR);
  }
  if (!Array.isArray(parsed) || parsed.length === 0) {
    throw new AiEngineConfigurationError(BYO_AI_PROVIDERS_ERROR);
  }

  const providers: ByoProvider[] = [];
  for (const item of parsed) {
    if (typeof item !== "string" || !isByoProvider(item) || providers.includes(item)) {
      throw new AiEngineConfigurationError(BYO_AI_PROVIDERS_ERROR);
    }
    providers.push(item);
  }
  return providers;
}

export function validateByoAiProviders(providers: readonly string[]): ByoProvider[] {
  if (providers.length === 0 || providers.some((provider) => !isByoProvider(provider)) ||
      new Set(providers).size !== providers.length) {
    throw new AiEngineConfigurationError(BYO_AI_PROVIDERS_ERROR);
  }
  return [...providers] as ByoProvider[];
}

export function assertByoProviderAllowed(
  provider: ByoProvider,
  providers: readonly ByoProvider[],
): void {
  if (!providers.includes(provider)) {
    throw new AiEngineConfigurationError(
      `${provider} is not enabled by ${BYO_AI_PROVIDERS_ENV}.`,
    );
  }
}

export function configuredByoAiProviders(): ByoProvider[] {
  return parseByoAiProviders(process.env[BYO_AI_PROVIDERS_ENV]);
}

export function allowedEngines(
  mode: AiMode,
  cloud: ApplianceCloud,
  byoProviders: readonly ByoProvider[] = [],
): readonly AiEngineId[] {
  return mode === "byo-api" ? byoProviders : [SAAS_ENGINE_BY_CLOUD[cloud]];
}

export class AiEngineUnavailableError extends Error {}

export type ResolveEngineInput = {
  mode: AiMode;
  cloud: ApplianceCloud;
  byoProviders: readonly ByoProvider[];
  stored: string | null | undefined;
  envDefault: string | null | undefined;
  configured: ReadonlySet<AiEngineId>;
};

/**
 * Resolve the active engine — mirrors resolve_engine() in chat_agent.py.
 *
 * saas:    the single engine allowed for this cloud; stored/env preferences
 *          are irrelevant. Configuration is the caller's check.
 * byo-api: among explicitly allowed and configured BYO engines — one ⇒ it wins
 *          outright (stored setting ignored); many ⇒ stored, then env default,
 *          then the first allowlisted provider;
 *          none ⇒ AiEngineUnavailableError.
 * A stored value from another mode is skipped, never fatal.
 */
export function resolveEngine(input: ResolveEngineInput): AiEngineId {
  const allowed =
    input.mode === "byo-api"
      ? allowedEngines(input.mode, input.cloud, validateByoAiProviders(input.byoProviders))
      : allowedEngines(input.mode, input.cloud);
  if (input.mode === "saas") return allowed[0];

  const configuredDefault = clean(input.envDefault);
  if (configuredDefault && !allowed.includes(configuredDefault as AiEngineId)) {
    throw new AiEngineConfigurationError(
      `CNA_AI_ENGINE_DEFAULT must name a provider enabled by ${BYO_AI_PROVIDERS_ENV}.`,
    );
  }

  const candidates = allowed.filter((engine) => input.configured.has(engine));
  if (candidates.length === 0) {
    throw new AiEngineUnavailableError(
      "No enabled bring-your-own AI API key is configured. Add a key for a provider enabled by CNA_BYO_AI_PROVIDERS on the admin AI Engine page.",
    );
  }
  if (candidates.length === 1) return candidates[0];

  const stored = normalizeAiEngine(input.stored);
  if (stored && candidates.includes(stored)) return stored;
  const envDefault = normalizeAiEngine(input.envDefault);
  if (envDefault && candidates.includes(envDefault)) return envDefault;
  return candidates[0];
}

/** The BYO toggle is only meaningful when there is a real choice to make. */
export function byoToggleEnabled(configured: ReadonlySet<AiEngineId>): boolean {
  return BYO_ENGINES.every((engine) => configured.has(engine));
}
