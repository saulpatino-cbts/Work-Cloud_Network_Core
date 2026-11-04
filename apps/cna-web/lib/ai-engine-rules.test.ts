import { describe, expect, it } from "vitest";

import {
  type AiEngineId,
  AiEngineConfigurationError,
  AiEngineUnavailableError,
  allowedEngines,
  byoToggleEnabled,
  normalizeAiEngine,
  normalizeAiMode,
  normalizeApplianceCloud,
  parseByoAiProviders,
  resolveEngine,
  validateByoAiProviders,
} from "./ai-engine-rules";

// Shared resolver vector table — mirrored by tests/unit/test_chat_agent.py
// RESOLVER_VECTORS. Keep the two in lockstep.
// [mode, cloud, allowed BYO providers (null for SaaS), stored, envDefault,
//  configured, expected | null(=unavailable)]
const VECTORS: Array<
  [
    "saas" | "byo-api",
    "azure" | "aws",
    Array<"anthropic" | "openai"> | null,
    string | null,
    string | null,
    AiEngineId[],
    AiEngineId | null,
  ]
> = [
  // saas: one engine per cloud; stored/env preferences are irrelevant
  ["saas", "azure", null, null, null, ["azure-openai"], "azure-openai"],
  ["saas", "azure", null, "openai", "openai", ["azure-openai"], "azure-openai"],
  ["saas", "azure", null, "foundry-claude", null, ["azure-openai"], "azure-openai"],
  ["saas", "azure", null, "bogus", null, [], "azure-openai"],
  ["saas", "aws", null, null, null, ["bedrock"], "bedrock"],
  ["saas", "aws", null, "azure-openai", null, ["bedrock"], "bedrock"],
  // byo-api: no key -> unavailable
  ["byo-api", "azure", ["anthropic", "openai"], null, null, [], null],
  ["byo-api", "azure", ["anthropic", "openai"], "anthropic", null, [], null],
  ["byo-api", "azure", ["anthropic", "openai"], null, null, ["azure-openai"], null],
  ["byo-api", "azure", ["anthropic"], null, null, ["openai"], null],
  // byo-api: exactly one key -> it wins, stored setting ignored
  ["byo-api", "azure", ["anthropic", "openai"], null, null, ["anthropic"], "anthropic"],
  ["byo-api", "azure", ["anthropic", "openai"], "openai", null, ["anthropic"], "anthropic"],
  ["byo-api", "aws", ["openai"], "azure-openai", "openai", ["openai"], "openai"],
  // byo-api: both keys -> stored, then env default, then anthropic
  ["byo-api", "azure", ["anthropic", "openai"], "openai", null, ["anthropic", "openai"], "openai"],
  ["byo-api", "azure", ["anthropic", "openai"], "anthropic", "openai", ["anthropic", "openai"], "anthropic"],
  ["byo-api", "azure", ["anthropic", "openai"], null, "openai", ["anthropic", "openai"], "openai"],
  ["byo-api", "azure", ["anthropic", "openai"], "azure-openai", "openai", ["anthropic", "openai"], "openai"],
  ["byo-api", "azure", ["anthropic", "openai"], "bogus", null, ["anthropic", "openai"], "anthropic"],
  ["byo-api", "azure", ["anthropic", "openai"], null, null, ["anthropic", "openai"], "anthropic"],
];

describe("resolveEngine", () => {
  it.each(VECTORS)(
    "%s/%s providers=%j stored=%s env=%s configured=%j -> %s",
    (mode, cloud, byoProviders, stored, envDefault, configured, expected) => {
      const input = {
        mode,
        cloud,
        byoProviders: byoProviders ?? [],
        stored,
        envDefault,
        configured: new Set(configured),
      };
      if (expected === null) {
        expect(() => resolveEngine(input)).toThrow(AiEngineUnavailableError);
      } else {
        expect(resolveEngine(input)).toBe(expected);
      }
    },
  );
});

describe("normalisation", () => {
  it("defaults mode/cloud when unset or unknown", () => {
    expect(normalizeAiMode(undefined)).toBe("saas");
    expect(normalizeAiMode("BYO-API")).toBe("saas");
    expect(normalizeAiMode(" byo-api ")).toBe("byo-api");
    expect(normalizeApplianceCloud(undefined)).toBe("azure");
    expect(normalizeApplianceCloud("aws")).toBe("aws");
    expect(normalizeApplianceCloud("gcp")).toBe("azure");
  });

  it("rejects unknown engine ids and treats 'none' as unset", () => {
    expect(normalizeAiEngine("anthropic")).toBe("anthropic");
    expect(normalizeAiEngine("bedrock")).toBe("bedrock");
    expect(normalizeAiEngine("foundry-claude")).toBeNull();
    expect(normalizeAiEngine("none")).toBeNull();
    expect(normalizeAiEngine(null)).toBeNull();
  });
});

describe("allowedEngines / toggle", () => {
  it("uses the explicit BYO allowlist and ignores it for SaaS", () => {
    expect(allowedEngines("saas", "azure")).toEqual(["azure-openai"]);
    expect(allowedEngines("saas", "aws")).toEqual(["bedrock"]);
    expect(allowedEngines("byo-api", "azure", ["openai"])).toEqual(["openai"]);
    expect(allowedEngines("byo-api", "azure")).toEqual([]);
  });

  it("enables the toggle only when both byo keys are configured", () => {
    expect(byoToggleEnabled(new Set())).toBe(false);
    expect(byoToggleEnabled(new Set<AiEngineId>(["anthropic"]))).toBe(false);
    expect(byoToggleEnabled(new Set<AiEngineId>(["anthropic", "openai"]))).toBe(true);
    expect(byoToggleEnabled(new Set<AiEngineId>(["azure-openai", "openai"]))).toBe(false);
  });
});

describe("CNA_BYO_AI_PROVIDERS parsing", () => {
  it.each([null, "", " ", "anthropic,openai", "{}", "[]", '["azure-openai"]',
    '["anthropic","anthropic"]', '["openai","<OPENAI_API_KEY>"]', '[" openai"]'])(
    "fails closed for invalid config %s",
    (value) => {
      expect(() => parseByoAiProviders(value)).toThrow(AiEngineConfigurationError);
    },
  );

  it("accepts only explicit unique provider IDs", () => {
    expect(parseByoAiProviders('["openai","anthropic"]')).toEqual(["openai", "anthropic"]);
    expect(() => validateByoAiProviders([])).toThrow(AiEngineConfigurationError);
  });

  it("rejects a configured BYO default outside the allowlist", () => {
    expect(() =>
      resolveEngine({
        mode: "byo-api",
        cloud: "azure",
        byoProviders: ["anthropic"],
        stored: null,
        envDefault: "openai",
        configured: new Set(["anthropic", "openai"]),
      }),
    ).toThrow(AiEngineConfigurationError);
  });
});
