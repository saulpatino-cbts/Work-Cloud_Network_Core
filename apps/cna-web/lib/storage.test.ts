import { afterEach, describe, expect, it } from "vitest";

import { isBlobStorageAvailable } from "./storage";

// isBlobStorageAvailable() reads CNA_APPLIANCE_CLOUD through the same
// normaliser the AI engine uses, so drive it the same way: set the env var,
// assert, and restore it after each case.
const ORIGINAL = process.env.CNA_APPLIANCE_CLOUD;

afterEach(() => {
  if (ORIGINAL === undefined) delete process.env.CNA_APPLIANCE_CLOUD;
  else process.env.CNA_APPLIANCE_CLOUD = ORIGINAL;
});

describe("isBlobStorageAvailable", () => {
  it("is false on AWS — the web tier has no S3 implementation yet (CR-CORE-01 / AWS-F-04)", () => {
    process.env.CNA_APPLIANCE_CLOUD = "aws";
    expect(isBlobStorageAvailable()).toBe(false);
  });

  it("is false for 'aws' with surrounding whitespace (the normaliser trims)", () => {
    process.env.CNA_APPLIANCE_CLOUD = "  aws  ";
    expect(isBlobStorageAvailable()).toBe(false);
  });

  it("is true on Azure, where blob storage is implemented", () => {
    process.env.CNA_APPLIANCE_CLOUD = "azure";
    expect(isBlobStorageAvailable()).toBe(true);
  });

  it("defaults to true (Azure) when the cloud is unset or unknown", () => {
    delete process.env.CNA_APPLIANCE_CLOUD;
    expect(isBlobStorageAvailable()).toBe(true);

    process.env.CNA_APPLIANCE_CLOUD = "gcp";
    expect(isBlobStorageAvailable()).toBe(true);
  });
});
