import { normalizeApplianceCloud } from "./ai-engine-rules";

/**
 * Single source of truth for "can this deployment use cloud file storage?".
 *
 * The web tier (see lib/blob.ts) only implements Azure Blob Storage. AWS uses
 * S3 which the web tier does not implement yet (CR-CORE-01 / AWS-F-04
 * follow-up, tracked as TODO.md T-709); storage features are disabled on AWS
 * until the S3 path ships. Until then, an AWS appliance degrades gracefully —
 * the three storage-dependent features (document upload, deliverable blobs and
 * the client-portal download) are disabled instead of throwing raw
 * Azure-storage errors like "AZURE_STORAGE_ACCOUNT_NAME is not set".
 *
 * Keyed off the same CNA_APPLIANCE_CLOUD env var and normaliser the AI engine
 * uses (getApplianceCloud in lib/ai-engine.ts), so the two stay consistent.
 */
export function isBlobStorageAvailable(): boolean {
  return normalizeApplianceCloud(process.env.CNA_APPLIANCE_CLOUD) !== "aws";
}

/**
 * Message shown (API body and UI note) when storage is unavailable on this
 * appliance. Kept here so the server guards and the hidden-control notes stay
 * in sync.
 */
export const STORAGE_UNAVAILABLE_MESSAGE =
  "Document storage is not available on this AWS appliance yet.";

/** Short note rendered next to a hidden/disabled storage control in the UI. */
export const STORAGE_UNAVAILABLE_UI_NOTE = "Not available on this appliance";
