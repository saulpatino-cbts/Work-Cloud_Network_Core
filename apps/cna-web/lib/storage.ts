import { normalizeApplianceCloud } from "./ai-engine-rules";

type StorageConfig =
  | { cloud: "aws"; bucket: string; engagements: string }
  | { cloud: "azure"; account: string; engagements: string };

const AZURE_CONTAINER = /^(?!.*--)[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/;

/** Configuration only: does not load credentials or contact either cloud. */
export function getStorageConfig(): StorageConfig {
  if (normalizeApplianceCloud(process.env.CNA_APPLIANCE_CLOUD) === "aws") {
    const bucket = process.env.CNA_STORAGE_BUCKET ?? "";
    // General-purpose bucket names only, never URLs, ARNs or access-point aliases.
    if (
      !/^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$/.test(bucket) ||
      bucket.includes("..") || bucket.includes(".-") || bucket.includes("-.") ||
      /^\d+\.\d+\.\d+\.\d+$/.test(bucket) ||
      /^(xn--|sthree-|amzn-s3-demo-)/.test(bucket) ||
      /(-s3alias|--ol-s3|\.mrap|--x-s3|--table-s3)$/.test(bucket)
    ) {
      throw new Error("CNA_STORAGE_BUCKET must be a valid S3 bucket name");
    }
    return { cloud: "aws", bucket, engagements: "raw-artifacts" };
  }
  const account = process.env.AZURE_STORAGE_ACCOUNT_NAME ?? "";
  const engagements = process.env.AZURE_STORAGE_CONTAINER_ENGAGEMENTS ?? "raw-artifacts";
  if (!/^[a-z0-9]{3,24}$/.test(account)) {
    throw new Error("AZURE_STORAGE_ACCOUNT_NAME must be a valid storage account name");
  }
  if (!AZURE_CONTAINER.test(engagements) || engagements === "deliverables" || engagements.startsWith("portal-")) {
    throw new Error("AZURE_STORAGE_CONTAINER_ENGAGEMENTS must be a dedicated container name");
  }
  return { cloud: "azure", account, engagements };
}

/** Enable web storage controls only when the selected backend is configured. */
export function isBlobStorageAvailable(): boolean {
  try {
    getStorageConfig();
    return true;
  } catch {
    return false;
  }
}

/** The Python API's external portal publisher still uses AzureBlobDeployer. */
export function isPortalPublishingAvailable(): boolean {
  return normalizeApplianceCloud(process.env.CNA_APPLIANCE_CLOUD) !== "aws" &&
    isBlobStorageAvailable();
}

export const STORAGE_UNAVAILABLE_MESSAGE =
  "Document storage is not configured for this appliance.";
export const PORTAL_UNAVAILABLE_MESSAGE =
  "External client portal publishing is not available on this appliance.";
export const STORAGE_UNAVAILABLE_UI_NOTE = "Not available on this appliance";
