import {
  BlobSASPermissions,
  BlobServiceClient,
  generateBlobSASQueryParameters,
} from "@azure/storage-blob";
import { DefaultAzureCredential } from "@azure/identity";
import {
  DeleteObjectCommand,
  DeleteObjectsCommand,
  GetObjectCommand,
  ListObjectsV2Command,
  PutObjectCommand,
  S3Client,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { getStorageConfig } from "./storage";

const DEFAULT_DOWNLOAD_TTL_HOURS = 1;
const MAX_DOWNLOAD_TTL_SECONDS = 3600;
const S3_DELETE_BATCH_SIZE = 1000;
const MARKDOWN_CONTENT_TYPE = "text/markdown; charset=utf-8";
type StorageConfig = ReturnType<typeof getStorageConfig>;

function azureClient(config: StorageConfig): BlobServiceClient {
  if (config.cloud !== "azure") throw new Error("Expected Azure storage configuration");
  return new BlobServiceClient(
    `https://${config.account}.blob.core.windows.net`,
    new DefaultAzureCredential(),
  );
}

function validateEngagement(engagementId: string): void {
  if (!/^[a-zA-Z0-9_-]{1,128}$/.test(engagementId)) {
    throw new Error("Invalid storage engagement ID");
  }
}

function validatePath(path: string): void {
  // Accept canonical relative keys only. Never normalize a URL, percent escape,
  // backslash or dot segment into an apparently authorized engagement prefix.
  if (
    !path || /[\\%?#:\u0000-\u001f\u007f]/.test(path) ||
    path.split("/").some((part) => !part || part === "." || part === "..")
  ) {
    throw new Error("Invalid storage path");
  }
}

function scopedPath(blobPath: string, engagementId: string, config: StorageConfig) {
  validateEngagement(engagementId);
  validatePath(blobPath);
  const [container, owner, ...file] = blobPath.split("/");
  if (
    (container !== config.engagements && container !== "deliverables") ||
    owner !== engagementId || file.length === 0
  ) {
    throw new Error("Storage path does not belong to the expected engagement");
  }
  return { container, blobName: [owner, ...file].join("/") };
}

async function upload(
  config: StorageConfig,
  container: string,
  engagementId: string,
  fileName: string,
  buffer: Buffer,
  contentType: string,
): Promise<string> {
  validateEngagement(engagementId);
  validatePath(fileName);
  const blobName = `${engagementId}/${fileName}`;
  const key = `${container}/${blobName}`;
  if (Buffer.byteLength(key, "utf8") > 1024) throw new Error("Storage path is too long");
  if (config.cloud === "aws") {
    // No static credentials or custom endpoint: use the SDK workload chain.
    const client = new S3Client({});
    try {
      await client.send(new PutObjectCommand({
        Bucket: config.bucket, Key: key, Body: buffer, ContentType: contentType,
      }));
    } finally {
      client.destroy();
    }
  } else {
    await azureClient(config).getContainerClient(container).getBlockBlobClient(blobName)
      .upload(buffer, buffer.length, { blobHTTPHeaders: { blobContentType: contentType } });
  }
  return key;
}

/** Persist the same relative container/engagement/file path on either cloud. */
export async function uploadEngagementFile(
  engagementId: string,
  fileName: string,
  buffer: Buffer,
  contentType: string,
): Promise<string> {
  const config = getStorageConfig();
  return upload(config, config.engagements, engagementId, fileName, buffer, contentType);
}

export async function uploadDeliverable(
  engagementId: string,
  fileName: string,
  content: string,
): Promise<string> {
  return upload(getStorageConfig(), "deliverables", engagementId, fileName,
    Buffer.from(content, "utf-8"), MARKDOWN_CONTENT_TYPE);
}

function isAzureNotFound(error: unknown): boolean {
  return typeof error === "object" && error !== null &&
    "statusCode" in error && error.statusCode === 404;
}

/** Caller must authorize engagementId first. Missing objects are success. */
export async function deleteBlob(blobPath: string, engagementId: string): Promise<void> {
  const config = getStorageConfig();
  const { container, blobName } = scopedPath(blobPath, engagementId, config);
  if (config.cloud === "aws") {
    const client = new S3Client({});
    try {
      await client.send(new DeleteObjectCommand({ Bucket: config.bucket, Key: blobPath }));
    } finally {
      client.destroy();
    }
    return;
  }
  try {
    await azureClient(config).getContainerClient(container).getBlockBlobClient(blobName).delete();
  } catch (error: unknown) {
    if (!isAzureNotFound(error)) throw error;
  }
}

/**
 * Delete only the authorized engagement's portal: an Azure container, or a
 * slash-delimited S3 prefix inside the configured bucket. Never delete a bucket.
 * Unversioned/current objects only; version retention is an appliance policy.
 */
export async function deleteContainer(containerName: string, engagementId: string): Promise<void> {
  validateEngagement(engagementId);
  if (containerName !== `portal-${engagementId}`) throw new Error("Invalid portal container scope");
  const config = getStorageConfig();
  if (config.cloud === "azure") {
    try {
      await azureClient(config).getContainerClient(containerName).delete();
    } catch (error: unknown) {
      if (!isAzureNotFound(error)) throw error;
    }
    return;
  }
  const client = new S3Client({});
  const prefix = `${containerName}/`;
  let token: string | undefined;
  const seenTokens = new Set<string>();
  try {
    do {
      const page = await client.send(new ListObjectsV2Command({
        Bucket: config.bucket, Prefix: prefix, ContinuationToken: token,
      }));
      const objects = (page.Contents ?? []).map(({ Key }) => {
        if (!Key?.startsWith(prefix)) throw new Error("S3 returned an object outside the portal scope");
        return { Key };
      });
      for (let offset = 0; offset < objects.length; offset += S3_DELETE_BATCH_SIZE) {
        const result = await client.send(new DeleteObjectsCommand({
          Bucket: config.bucket,
          Delete: { Objects: objects.slice(offset, offset + S3_DELETE_BATCH_SIZE), Quiet: true },
        }));
        if (result.Errors?.length) throw new Error("S3 portal cleanup failed for one or more objects");
      }
      token = page.IsTruncated ? page.NextContinuationToken : undefined;
      if (page.IsTruncated && (!token || seenTokens.has(token))) {
        throw new Error("S3 returned invalid portal pagination");
      }
      if (token) seenTokens.add(token);
    } while (token);
  } finally {
    client.destroy();
  }
}

/** Read-only URL, 1 second–1 hour. Caller must authorize engagementId first. */
export async function generateSasUrl(
  blobPath: string,
  engagementId: string,
  ttlHours: number = DEFAULT_DOWNLOAD_TTL_HOURS,
): Promise<string> {
  const expiresIn = Math.floor(ttlHours * 3600);
  if (!Number.isFinite(ttlHours) || ttlHours > DEFAULT_DOWNLOAD_TTL_HOURS ||
    expiresIn < 1 || expiresIn > MAX_DOWNLOAD_TTL_SECONDS) {
    throw new Error("Download URL lifetime must be between 1 second and 1 hour");
  }
  const config = getStorageConfig();
  const { container, blobName } = scopedPath(blobPath, engagementId, config);
  if (config.cloud === "aws") {
    const client = new S3Client({});
    try {
      return await getSignedUrl(client, new GetObjectCommand({
        Bucket: config.bucket, Key: blobPath,
      }), { expiresIn });
    } finally {
      client.destroy();
    }
  }
  const client = azureClient(config);
  const startsOn = new Date();
  const expiresOn = new Date(startsOn.getTime() + expiresIn * 1000);
  const userDelegationKey = await client.getUserDelegationKey(startsOn, expiresOn);
  const sasParams = generateBlobSASQueryParameters(
    { containerName: container, blobName, permissions: BlobSASPermissions.parse("r"), startsOn, expiresOn },
    userDelegationKey,
    config.account,
  );
  const encodedPath = blobPath.split("/").map(encodeURIComponent).join("/");
  return `https://${config.account}.blob.core.windows.net/${encodedPath}?${sasParams.toString()}`;
}
