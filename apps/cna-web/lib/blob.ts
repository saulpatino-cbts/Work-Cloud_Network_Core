import { BlobServiceClient } from "@azure/storage-blob";
import { DefaultAzureCredential } from "@azure/identity";

function getBlobServiceClient(): BlobServiceClient {
  const accountName = process.env.AZURE_STORAGE_ACCOUNT_NAME;
  if (!accountName) {
    throw new Error("AZURE_STORAGE_ACCOUNT_NAME is not set");
  }
  const credential = new DefaultAzureCredential();
  return new BlobServiceClient(
    `https://${accountName}.blob.core.windows.net`,
    credential,
  );
}

/**
 * Upload a document file to the raw-artifacts container.
 * Returns the blob path: raw-artifacts/{engagementId}/{fileName}
 */
export async function uploadEngagementFile(
  engagementId: string,
  fileName: string,
  buffer: Buffer,
  contentType: string,
): Promise<string> {
  const container =
    process.env.AZURE_STORAGE_CONTAINER_ENGAGEMENTS ?? "raw-artifacts";
  const client = getBlobServiceClient();
  const containerClient = client.getContainerClient(container);
  const blobName = `${engagementId}/${fileName}`;
  const blockBlobClient = containerClient.getBlockBlobClient(blobName);
  await blockBlobClient.upload(buffer, buffer.length, {
    blobHTTPHeaders: { blobContentType: contentType },
  });
  return `${container}/${blobName}`;
}

/**
 * Upload a generated deliverable to the deliverables container.
 * Returns the blob path: deliverables/{engagementId}/{fileName}
 */
export async function uploadDeliverable(
  engagementId: string,
  fileName: string,
  content: string,
): Promise<string> {
  const client = getBlobServiceClient();
  const containerClient = client.getContainerClient("deliverables");
  const blobName = `${engagementId}/${fileName}`;
  const blockBlobClient = containerClient.getBlockBlobClient(blobName);
  const buffer = Buffer.from(content, "utf-8");
  await blockBlobClient.upload(buffer, buffer.length, {
    blobHTTPHeaders: { blobContentType: "text/markdown; charset=utf-8" },
  });
  return `deliverables/${blobName}`;
}
