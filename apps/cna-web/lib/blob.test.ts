import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  send: vi.fn(), destroy: vi.fn(), sign: vi.fn(),
  upload: vi.fn(), deleteBlob: vi.fn(), deleteContainer: vi.fn(),
  delegation: vi.fn(), sas: vi.fn(), permissions: vi.fn(),
  container: vi.fn(), blob: vi.fn(),
}));

vi.mock("@aws-sdk/client-s3", async (importOriginal) => ({
  ...await importOriginal<typeof import("@aws-sdk/client-s3")>(),
  S3Client: vi.fn(class {
    send = mocks.send;
    destroy = mocks.destroy;
  }),
}));
vi.mock("@aws-sdk/s3-request-presigner", () => ({ getSignedUrl: mocks.sign }));
vi.mock("@azure/identity", () => ({ DefaultAzureCredential: vi.fn(class {}) }));
vi.mock("@azure/storage-blob", () => ({
  BlobServiceClient: vi.fn(class {
    getContainerClient = mocks.container;
    getUserDelegationKey = mocks.delegation;
  }),
  BlobSASPermissions: { parse: mocks.permissions },
  generateBlobSASQueryParameters: mocks.sas,
}));

import {
  DeleteObjectCommand, DeleteObjectsCommand, GetObjectCommand,
  ListObjectsV2Command, PutObjectCommand, S3Client,
} from "@aws-sdk/client-s3";
import { BlobServiceClient } from "@azure/storage-blob";
import { deleteBlob, deleteContainer, generateSasUrl, uploadDeliverable, uploadEngagementFile } from "./blob";

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubEnv("CNA_APPLIANCE_CLOUD", "aws");
  vi.stubEnv("CNA_STORAGE_BUCKET", "cna-test-artifacts");
  vi.stubEnv("AZURE_STORAGE_ACCOUNT_NAME", "cnateststorage");
  vi.stubEnv("AZURE_STORAGE_CONTAINER_ENGAGEMENTS", undefined);
  mocks.send.mockResolvedValue({});
  mocks.sign.mockResolvedValue("https://signed.invalid/download");
  mocks.container.mockReturnValue({ getBlockBlobClient: mocks.blob, delete: mocks.deleteContainer });
  mocks.blob.mockReturnValue({ upload: mocks.upload, delete: mocks.deleteBlob });
  mocks.delegation.mockResolvedValue({ signedOid: "test-delegation" });
  mocks.sas.mockReturnValue({ toString: () => "read-only-test-sas" });
  mocks.permissions.mockReturnValue("read-only");
});
afterEach(() => { vi.unstubAllEnvs(); vi.useRealTimers(); });

describe("AWS storage transport", () => {
  it("uploads documents and nested diagrams with their metadata via workload credentials", async () => {
    const body = Buffer.from("<mxfile/>");
    const path = await uploadEngagementFile("eng-a", "diagrams/source.drawio", body, "application/xml");
    expect(path).toBe("raw-artifacts/eng-a/diagrams/source.drawio");
    expect(S3Client).toHaveBeenCalledWith({});
    expect(mocks.send.mock.calls[0][0]).toBeInstanceOf(PutObjectCommand);
    expect(mocks.send.mock.calls[0][0].input).toEqual({
      Bucket: "cna-test-artifacts", Key: path, Body: body, ContentType: "application/xml",
    });
    expect(BlobServiceClient).not.toHaveBeenCalled();
    expect(mocks.destroy).toHaveBeenCalledOnce();
  });

  it("uploads UTF-8 deliverables and returns the canonical relative path", async () => {
    expect(await uploadDeliverable("eng-a", "report.md", "# Résumé")).toBe("deliverables/eng-a/report.md");
    expect(mocks.send.mock.calls[0][0].input).toEqual({
      Bucket: "cna-test-artifacts", Key: "deliverables/eng-a/report.md",
      Body: Buffer.from("# Résumé", "utf8"), ContentType: "text/markdown; charset=utf-8",
    });
  });

  it("deletes only the expected key and treats S3's empty missing-key result as success", async () => {
    await deleteBlob("deliverables/eng-a/report.md", "eng-a");
    expect(mocks.send.mock.calls[0][0]).toBeInstanceOf(DeleteObjectCommand);
    expect(mocks.send.mock.calls[0][0].input).toEqual({
      Bucket: "cna-test-artifacts", Key: "deliverables/eng-a/report.md",
    });
  });

  it.each([undefined, 1, 0.25, 1 / 3600])("signs GET only with bounded seconds: %s", async (ttl) => {
    const path = "deliverables/eng-a/report.md";
    await expect(generateSasUrl(path, "eng-a", ttl)).resolves.toBe("https://signed.invalid/download");
    const [, command, options] = mocks.sign.mock.calls[0];
    expect(command).toBeInstanceOf(GetObjectCommand);
    expect(command.input).toEqual({ Bucket: "cna-test-artifacts", Key: path });
    expect(options).toEqual({ expiresIn: ttl === undefined ? 3600 : Math.floor(ttl * 3600) });
    expect(mocks.send).not.toHaveBeenCalled();
    expect(mocks.destroy).toHaveBeenCalledOnce();
  });

  it("propagates upload, delete and signing failures and releases each client", async () => {
    mocks.send.mockRejectedValue(new Error("AccessDenied"));
    await expect(uploadDeliverable("eng-a", "report.md", "report")).rejects.toThrow("AccessDenied");
    await expect(deleteBlob("deliverables/eng-a/report.md", "eng-a")).rejects.toThrow("AccessDenied");
    mocks.sign.mockRejectedValue(new Error("Signing failed"));
    await expect(generateSasUrl("deliverables/eng-a/report.md", "eng-a")).rejects.toThrow("Signing failed");
    expect(mocks.destroy).toHaveBeenCalledTimes(3);
  });
});

describe.each(["aws", "azure"])("%s scope and input boundaries", (cloud) => {
  beforeEach(() => vi.stubEnv("CNA_APPLIANCE_CLOUD", cloud));

  it.each([
    "", "/deliverables/eng-a/report.md", "deliverables/eng-a",
    "deliverables/eng-b/report.md", "deliverables/eng-ab/report.md",
    "raw-artifacts/eng-a/../eng-b/file.txt", "deliverables/eng-a/./file",
    "deliverables/eng-a//file", "deliverables/eng-a/dir\\file",
    "deliverables/eng-a/%2e%2e/file", "deliverables/eng-a/report?x",
    "deliverables/eng-a/report#x", "deliverables/eng-a/file\u0000",
    "s3://cna-test-artifacts/deliverables/eng-a/file",
    "s3://other-bucket/deliverables/eng-a/file",
    "https://cnateststorage.blob.core.windows.net/deliverables/eng-a/file",
    "https://evil.invalid/deliverables/eng-a/file", "//evil.invalid/file",
    "other/eng-a/file", "portal-eng-a/index.html",
  ])("rejects unsafe or wrong-owner read/delete paths before SDK use: %s", async (path) => {
    await expect(deleteBlob(path, "eng-a")).rejects.toThrow();
    await expect(generateSasUrl(path, "eng-a")).rejects.toThrow();
    expect(S3Client).not.toHaveBeenCalled();
    expect(BlobServiceClient).not.toHaveBeenCalled();
    expect(mocks.sign).not.toHaveBeenCalled();
  });

  it.each(["", ".", "..", "../file", "a/../file", "/file", "a//file", "a\\file", "file%2fother", "https://other/file"])(
    "rejects unsafe upload paths: %s", async (file) => {
      await expect(uploadEngagementFile("eng-a", file, Buffer.from("data"), "text/plain")).rejects.toThrow();
      await expect(uploadDeliverable("eng-a", file, "data")).rejects.toThrow();
      expect(S3Client).not.toHaveBeenCalled();
      expect(BlobServiceClient).not.toHaveBeenCalled();
    },
  );

  it.each(["", "..", "eng/a", "eng\\a", "eng%2fa", "eng?a", "a".repeat(129)])(
    "rejects unsafe engagement IDs on all five operations: %s", async (id) => {
      await expect(uploadEngagementFile(id, "file", Buffer.from("x"), "text/plain")).rejects.toThrow();
      await expect(uploadDeliverable(id, "file.md", "x")).rejects.toThrow();
      await expect(deleteBlob(`deliverables/${id}/file`, id)).rejects.toThrow();
      await expect(generateSasUrl(`deliverables/${id}/file`, id)).rejects.toThrow();
      await expect(deleteContainer(`portal-${id}`, id)).rejects.toThrow();
      expect(S3Client).not.toHaveBeenCalled();
      expect(BlobServiceClient).not.toHaveBeenCalled();
    },
  );

  it.each([0, -1, NaN, Infinity, 1.01, 24, 1 / 7200])("rejects invalid URL expiry: %s", async (ttl) => {
    await expect(generateSasUrl("deliverables/eng-a/file", "eng-a", ttl)).rejects.toThrow("lifetime");
    expect(S3Client).not.toHaveBeenCalled();
    expect(BlobServiceClient).not.toHaveBeenCalled();
  });

  it.each(["", "portal-eng-ab", "raw-artifacts", "deliverables", "portal-eng-a/child", "../portal-eng-a"])(
    "rejects unsafe container cleanup scope: %s", async (container) => {
      await expect(deleteContainer(container, "eng-a")).rejects.toThrow();
      expect(S3Client).not.toHaveBeenCalled();
      expect(BlobServiceClient).not.toHaveBeenCalled();
    },
  );

  it("fails closed on missing configuration for all five operations", async () => {
    vi.stubEnv("CNA_STORAGE_BUCKET", undefined);
    vi.stubEnv("AZURE_STORAGE_ACCOUNT_NAME", undefined);
    await expect(uploadEngagementFile("eng-a", "file", Buffer.from("x"), "text/plain")).rejects.toThrow();
    await expect(uploadDeliverable("eng-a", "file", "x")).rejects.toThrow();
    await expect(deleteBlob("deliverables/eng-a/file", "eng-a")).rejects.toThrow();
    await expect(deleteContainer("portal-eng-a", "eng-a")).rejects.toThrow();
    await expect(generateSasUrl("deliverables/eng-a/file", "eng-a")).rejects.toThrow();
    expect(S3Client).not.toHaveBeenCalled();
    expect(BlobServiceClient).not.toHaveBeenCalled();
  });
});

describe("S3 portal prefix cleanup", () => {
  it("paginates and batches only slash-delimited portal objects, never the bucket", async () => {
    const keys = Array.from({ length: 1001 }, (_, index) => ({ Key: `portal-eng-a/${index}.html` }));
    mocks.send.mockResolvedValueOnce({ Contents: keys, IsTruncated: true, NextContinuationToken: "page2" })
      .mockResolvedValueOnce({}).mockResolvedValueOnce({})
      .mockResolvedValueOnce({ Contents: [{ Key: "portal-eng-a/index.html" }], IsTruncated: false })
      .mockResolvedValueOnce({});
    await deleteContainer("portal-eng-a", "eng-a");
    const commands = mocks.send.mock.calls.map(([command]) => command);
    expect(commands[0]).toBeInstanceOf(ListObjectsV2Command);
    expect(commands[0].input).toEqual({ Bucket: "cna-test-artifacts", Prefix: "portal-eng-a/", ContinuationToken: undefined });
    expect(commands[1]).toBeInstanceOf(DeleteObjectsCommand);
    expect(commands[1].input.Delete.Objects).toHaveLength(1000);
    expect(commands[2].input.Delete.Objects).toHaveLength(1);
    expect(commands[3]).toBeInstanceOf(ListObjectsV2Command);
    expect(commands[3].input.ContinuationToken).toBe("page2");
    expect(commands[4].input.Delete.Objects).toEqual([{ Key: "portal-eng-a/index.html" }]);
    expect(commands.every((command) => command instanceof ListObjectsV2Command || command instanceof DeleteObjectsCommand)).toBe(true);
    expect(mocks.destroy).toHaveBeenCalledOnce();
  });

  it("succeeds on an absent/empty prefix without issuing a deletion", async () => {
    await deleteContainer("portal-eng-a", "eng-a");
    expect(mocks.send).toHaveBeenCalledOnce();
    expect(mocks.send.mock.calls[0][0]).toBeInstanceOf(ListObjectsV2Command);
  });

  it("propagates HTTP-success partial delete errors and stops before the next page", async () => {
    mocks.send.mockResolvedValueOnce({
      Contents: [{ Key: "portal-eng-a/file" }], IsTruncated: true, NextContinuationToken: "next",
    }).mockResolvedValueOnce({ Errors: [{ Key: "portal-eng-a/file", Code: "AccessDenied" }] });
    await expect(deleteContainer("portal-eng-a", "eng-a")).rejects.toThrow("one or more objects");
    expect(mocks.send).toHaveBeenCalledTimes(2);
    expect(mocks.destroy).toHaveBeenCalledOnce();
  });

  it.each(["list", "delete"])("propagates %s failures and releases the client", async (operation) => {
    if (operation === "delete") mocks.send.mockResolvedValueOnce({ Contents: [{ Key: "portal-eng-a/file" }] });
    mocks.send.mockRejectedValueOnce(new Error("AccessDenied"));
    await expect(deleteContainer("portal-eng-a", "eng-a")).rejects.toThrow("AccessDenied");
    expect(mocks.destroy).toHaveBeenCalledOnce();
  });

  it.each(["portal-eng-ab/file", "deliverables/eng-a/file", undefined])(
    "rejects out-of-prefix or missing keys before batch deletion: %s", async (key) => {
      mocks.send.mockResolvedValueOnce({ Contents: [{ Key: "portal-eng-a/good" }, { Key: key }] });
      await expect(deleteContainer("portal-eng-a", "eng-a")).rejects.toThrow("outside the portal scope");
      expect(mocks.send).toHaveBeenCalledOnce();
    },
  );

  it("rejects truncated results without a continuation token", async () => {
    mocks.send.mockResolvedValueOnce({ IsTruncated: true });
    await expect(deleteContainer("portal-eng-a", "eng-a")).rejects.toThrow("pagination");
  });

  it("rejects repeated tokens instead of looping forever", async () => {
    mocks.send.mockResolvedValue({ IsTruncated: true, NextContinuationToken: "repeat" });
    await expect(deleteContainer("portal-eng-a", "eng-a")).rejects.toThrow("pagination");
    expect(mocks.send).toHaveBeenCalledTimes(2);
  });
});

describe("Azure storage compatibility", () => {
  beforeEach(() => vi.stubEnv("CNA_APPLIANCE_CLOUD", "azure"));

  it("preserves custom document containers, nested diagrams, headers and buffer length", async () => {
    vi.stubEnv("AZURE_STORAGE_CONTAINER_ENGAGEMENTS", "engagements");
    const body = Buffer.from("diagram");
    expect(await uploadEngagementFile("eng-a", "diagrams/a.drawio", body, "application/xml")).toBe("engagements/eng-a/diagrams/a.drawio");
    expect(BlobServiceClient).toHaveBeenCalledWith("https://cnateststorage.blob.core.windows.net", expect.any(Object));
    expect(mocks.container).toHaveBeenCalledWith("engagements");
    expect(mocks.blob).toHaveBeenCalledWith("eng-a/diagrams/a.drawio");
    expect(mocks.upload).toHaveBeenCalledWith(body, body.length, { blobHTTPHeaders: { blobContentType: "application/xml" } });
    expect(S3Client).not.toHaveBeenCalled();
  });

  it("preserves deliverable path and UTF-8 markdown headers", async () => {
    expect(await uploadDeliverable("eng-a", "a.md", "Résumé")).toBe("deliverables/eng-a/a.md");
    const body = Buffer.from("Résumé");
    expect(mocks.upload).toHaveBeenCalledWith(body, body.length, { blobHTTPHeaders: { blobContentType: "text/markdown; charset=utf-8" } });
  });

  it("generates read-only delegation SAS, encodes the URL path, and caps expiration", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-04T12:00:00Z"));
    expect(await generateSasUrl("deliverables/eng-a/Résumé file.md", "eng-a")).toBe(
      "https://cnateststorage.blob.core.windows.net/deliverables/eng-a/R%C3%A9sum%C3%A9%20file.md?read-only-test-sas",
    );
    expect(mocks.delegation).toHaveBeenCalledWith(new Date("2026-11-04T12:00:00Z"), new Date("2026-11-04T13:00:00Z"));
    expect(mocks.permissions).toHaveBeenCalledWith("r");
    expect(mocks.sas).toHaveBeenCalledWith(expect.objectContaining({
      containerName: "deliverables", blobName: "eng-a/Résumé file.md", permissions: "read-only",
    }), { signedOid: "test-delegation" }, "cnateststorage");
  });

  it("deletes only the scoped object and per-engagement container", async () => {
    await deleteBlob("raw-artifacts/eng-a/diagrams/file", "eng-a");
    expect(mocks.container).toHaveBeenCalledWith("raw-artifacts");
    expect(mocks.blob).toHaveBeenCalledWith("eng-a/diagrams/file");
    expect(mocks.deleteBlob).toHaveBeenCalledOnce();
    await deleteContainer("portal-eng-a", "eng-a");
    expect(mocks.container).toHaveBeenLastCalledWith("portal-eng-a");
    expect(mocks.deleteContainer).toHaveBeenCalledOnce();
  });

  it("preserves idempotent 404 cleanup but propagates permission failures", async () => {
    mocks.deleteBlob.mockRejectedValueOnce({ statusCode: 404 }).mockRejectedValueOnce(new Error("Denied"));
    mocks.deleteContainer.mockRejectedValueOnce({ statusCode: 404 }).mockRejectedValueOnce(new Error("Denied"));
    await expect(deleteBlob("deliverables/eng-a/file", "eng-a")).resolves.toBeUndefined();
    await expect(deleteContainer("portal-eng-a", "eng-a")).resolves.toBeUndefined();
    await expect(deleteBlob("deliverables/eng-a/file", "eng-a")).rejects.toThrow("Denied");
    await expect(deleteContainer("portal-eng-a", "eng-a")).rejects.toThrow("Denied");
  });

  it("propagates upload and delegation failures", async () => {
    mocks.upload.mockRejectedValue(new Error("Denied"));
    mocks.delegation.mockRejectedValue(new Error("Denied"));
    await expect(uploadDeliverable("eng-a", "file.md", "x")).rejects.toThrow("Denied");
    await expect(generateSasUrl("deliverables/eng-a/file", "eng-a")).rejects.toThrow("Denied");
  });
});
