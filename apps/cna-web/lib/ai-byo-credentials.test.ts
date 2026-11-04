import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./prisma", () => ({
  prisma: {
    appSetting: {
      deleteMany: vi.fn(),
      findMany: vi.fn(),
      findUnique: vi.fn(),
      upsert: vi.fn(),
    },
    $transaction: vi.fn(),
  },
}));

import { prisma } from "./prisma";

import {
  clearByoApiKey,
  getByoCredentialPresence,
  getDecryptedByoApiKey,
  probeByoApiKey,
  setByoApiKey,
} from "./ai-byo-credentials";

const appSetting = vi.mocked(prisma.appSetting);

describe("BYO credential allowlist enforcement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.CNA_AI_MODE = "byo-api";
    process.env.CNA_BYO_AI_PROVIDERS = '["anthropic"]';
  });

  it("only retrieves settings for enabled providers", async () => {
    appSetting.findMany.mockResolvedValue([]);

    await getByoCredentialPresence();

    expect(appSetting.findMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { key: { in: ["ai.byo.anthropic.apiKey", "ai.byo.anthropic.keyHint", "ai.byo.anthropic.model"] } },
      }),
    );
  });

  it("blocks disallowed key retrieval and probing before DB or SDK access", async () => {
    await expect(getDecryptedByoApiKey("openai")).rejects.toThrow(
      "openai is not enabled by CNA_BYO_AI_PROVIDERS",
    );
    await expect(probeByoApiKey("openai", "not-a-real-key")).rejects.toThrow(
      "openai is not enabled by CNA_BYO_AI_PROVIDERS",
    );
    await expect(setByoApiKey("openai", "not-a-real-key")).rejects.toThrow(
      "openai is not enabled by CNA_BYO_AI_PROVIDERS",
    );
    expect(appSetting.findUnique).not.toHaveBeenCalled();
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });

  it.each([
    undefined,
    "",
    " ",
    "not-json",
    "{}",
    "[]",
    '["anthropic","anthropic"]',
    '["azure-openai"]',
    '["<ANTHROPIC_API_KEY>"]',
  ])("rejects invalid provider config before save/probe/decrypt: %s", async (config) => {
    if (config === undefined) delete process.env.CNA_BYO_AI_PROVIDERS;
    else process.env.CNA_BYO_AI_PROVIDERS = config;

    await expect(setByoApiKey("anthropic", "not-a-real-key")).rejects.toThrow(
      "CNA_BYO_AI_PROVIDERS",
    );
    await expect(probeByoApiKey("anthropic", "not-a-real-key")).rejects.toThrow(
      "CNA_BYO_AI_PROVIDERS",
    );
    await expect(getDecryptedByoApiKey("anthropic")).rejects.toThrow(
      "CNA_BYO_AI_PROVIDERS",
    );
    expect(appSetting.findUnique).not.toHaveBeenCalled();
    expect(prisma.$transaction).not.toHaveBeenCalled();
  });

  it("keeps disallowed stored keys deletable for cleanup", async () => {
    appSetting.deleteMany.mockResolvedValue({ count: 2 });

    await clearByoApiKey("openai");

    expect(appSetting.deleteMany).toHaveBeenCalledWith({
      where: { key: { in: ["ai.byo.openai.apiKey", "ai.byo.openai.keyHint"] } },
    });
  });

  it("ignores the allowlist completely in SaaS mode", async () => {
    process.env.CNA_AI_MODE = "saas";
    process.env.CNA_BYO_AI_PROVIDERS = "not-json";

    await expect(getByoCredentialPresence()).rejects.toThrow("unavailable in saas mode");
    expect(appSetting.findMany).not.toHaveBeenCalled();
  });
});
