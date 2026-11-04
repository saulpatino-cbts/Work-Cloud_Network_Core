import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getStorageConfig, isBlobStorageAvailable, isPortalPublishingAvailable } from "./storage";

beforeEach(() => {
  vi.stubEnv("CNA_APPLIANCE_CLOUD", "aws");
  vi.stubEnv("CNA_STORAGE_BUCKET", "cna-test-artifacts");
  vi.stubEnv("AZURE_STORAGE_ACCOUNT_NAME", "cnateststorage");
  vi.stubEnv("AZURE_STORAGE_CONTAINER_ENGAGEMENTS", undefined);
});
afterEach(() => vi.unstubAllEnvs());

describe("storage configuration and independent portal capability", () => {
  it("enables configured AWS storage, but not the Azure-only API portal publisher", () => {
    expect(getStorageConfig()).toEqual({ cloud: "aws", bucket: "cna-test-artifacts", engagements: "raw-artifacts" });
    expect(isBlobStorageAvailable()).toBe(true);
    expect(isPortalPublishingAvailable()).toBe(false);
  });

  it("uses the established cloud normalizer and keeps Azure as the legacy default", () => {
    for (const cloud of ["  aws  ", "azure", undefined, "gcp"]) {
      vi.stubEnv("CNA_APPLIANCE_CLOUD", cloud);
      expect(isBlobStorageAvailable()).toBe(true);
      expect(getStorageConfig().cloud).toBe(cloud === "  aws  " ? "aws" : "azure");
    }
  });

  it("preserves Azure custom engagement containers and publishing", () => {
    vi.stubEnv("CNA_APPLIANCE_CLOUD", "azure");
    vi.stubEnv("AZURE_STORAGE_CONTAINER_ENGAGEMENTS", "engagements");
    expect(getStorageConfig()).toEqual({ cloud: "azure", account: "cnateststorage", engagements: "engagements" });
    expect(isPortalPublishingAvailable()).toBe(true);
  });

  it.each([
    undefined, "", " ", "s3://cna-test-artifacts", "https://bucket.invalid",
    "arn:aws:s3:::bucket", "Uppercase", "ab", "a".repeat(64), "a..b",
    "a.-b", "a-.b", "192.168.0.1", "xn--bucket", "sthree-bucket",
    "amzn-s3-demo-bucket", "bucket-s3alias", "bucket--ol-s3", "bucket.mrap",
    "bucket--x-s3", "bucket--table-s3", "../other",
  ])("rejects invalid AWS bucket configuration: %s", (bucket) => {
    vi.stubEnv("CNA_STORAGE_BUCKET", bucket);
    expect(isBlobStorageAvailable()).toBe(false);
    expect(getStorageConfig).toThrow("CNA_STORAGE_BUCKET");
  });

  it.each([undefined, "", "Uppercase", "https://account.invalid", "a".repeat(25)])(
    "rejects invalid Azure account: %s", (account) => {
      vi.stubEnv("CNA_APPLIANCE_CLOUD", "azure");
      vi.stubEnv("AZURE_STORAGE_ACCOUNT_NAME", account);
      expect(isBlobStorageAvailable()).toBe(false);
      expect(isPortalPublishingAvailable()).toBe(false);
    },
  );

  it.each(["", "a", "has--double", "../other", "deliverables", "portal-eng-a"])(
    "rejects unsafe Azure engagement containers: %s", (container) => {
      vi.stubEnv("CNA_APPLIANCE_CLOUD", "azure");
      vi.stubEnv("AZURE_STORAGE_CONTAINER_ENGAGEMENTS", container);
      expect(getStorageConfig).toThrow("AZURE_STORAGE_CONTAINER_ENGAGEMENTS");
    },
  );

  it("does not require or borrow Azure configuration on AWS", () => {
    vi.stubEnv("AZURE_STORAGE_ACCOUNT_NAME", undefined);
    vi.stubEnv("AZURE_STORAGE_CONTAINER_ENGAGEMENTS", "../unsafe");
    expect(isBlobStorageAvailable()).toBe(true);
    expect(getStorageConfig().engagements).toBe("raw-artifacts");
  });
});
