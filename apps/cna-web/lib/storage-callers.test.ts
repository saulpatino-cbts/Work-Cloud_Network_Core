import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(), member: vi.fn(), deliverable: vi.fn(), document: vi.fn(),
  documents: vi.fn(), deliverables: vi.fn(), removeDeliverable: vi.fn(),
  removeDocument: vi.fn(), removeEngagement: vi.fn(), upload: vi.fn(),
  createDocument: vi.fn(), updateEngagement: vi.fn(),
  deleteBlob: vi.fn(), deleteContainer: vi.fn(), sign: vi.fn(),
  fetch: vi.fn(),
}));
vi.mock("@/lib/auth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/prisma", () => ({ prisma: {
  engagementMember: { findUnique: mocks.member },
  deliverable: {
    findUnique: mocks.deliverable, findFirst: mocks.deliverable,
    findMany: mocks.deliverables, deleteMany: mocks.removeDeliverable,
  },
  ingestedDocument: {
    findFirst: mocks.document, findMany: mocks.documents,
    deleteMany: mocks.removeDocument, create: mocks.createDocument,
  },
  engagement: { delete: mocks.removeEngagement, updateMany: mocks.updateEngagement },
} }));
vi.mock("@/lib/blob", () => ({
  deleteBlob: mocks.deleteBlob, deleteContainer: mocks.deleteContainer,
  generateSasUrl: mocks.sign, uploadEngagementFile: mocks.upload,
  uploadDeliverable: vi.fn(),
}));
vi.mock("@/lib/storage", async () => await import("./storage"));
vi.mock("@/lib/openai", () => ({ generateDeliverableContent: vi.fn(), analyzeEngagement: vi.fn() }));
vi.mock("@/lib/report-orchestrator", () => ({ generateComprehensiveReport: vi.fn() }));
vi.mock("@/lib/rate-limit", () => ({ checkRateLimit: vi.fn() }));
vi.mock("@/lib/api-client", () => ({ apiHeaders: vi.fn() }));
vi.mock("@/lib/summarize-error", () => ({ sanitizeBackendDetail: vi.fn() }));
vi.mock("@/lib/sanitize-href", () => ({ escapeHtml: vi.fn(), sanitizeHref: vi.fn() }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("next/navigation", () => ({
  redirect: vi.fn(() => { throw new Error("test redirect"); }),
}));

import { GET } from "../app/api/deliverables/[id]/route";
import { deleteEngagement } from "../app/(dashboard)/dashboard/actions";
import { deleteDeliverable } from "../app/(dashboard)/engagements/[id]/deliverables/actions";
import {
  deleteDeliverableFromPortal, deleteDocument, publishClientPortal,
} from "../app/(dashboard)/engagements/[id]/client-deliverables/actions";
import { uploadDocument } from "../app/(dashboard)/engagements/[id]/documents/actions";
import { saveDiagramSource } from "../app/(dashboard)/engagements/[id]/diagram/actions";

function form() {
  const data = new FormData();
  data.set("engagementId", "eng-a");
  data.set("deliverableId", "report-a");
  data.set("documentId", "document-a");
  return data;
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", mocks.fetch);
  vi.stubEnv("CNA_APPLIANCE_CLOUD", "aws");
  vi.stubEnv("CNA_STORAGE_BUCKET", "cna-test-artifacts");
  vi.stubEnv("AZURE_STORAGE_ACCOUNT_NAME", "cnateststorage");
  mocks.auth.mockResolvedValue({ user: { id: "user-a", role: "ANALYST" } });
  mocks.member.mockResolvedValue({ role: "ADMIN" });
  mocks.deliverable.mockResolvedValue({
    engagementId: "eng-a", status: "COMPLETED", content: null,
    blobPath: "deliverables/eng-a/report.md",
    engagement: { members: [{ userId: "user-a" }] },
  });
  mocks.document.mockResolvedValue({ blobPath: "raw-artifacts/eng-a/file.txt" });
  mocks.documents.mockResolvedValue([{ blobPath: "raw-artifacts/eng-a/file.txt" }]);
  mocks.deliverables.mockResolvedValue([{ blobPath: "deliverables/eng-a/report.md" }]);
  mocks.sign.mockResolvedValue("https://signed.invalid/download");
  mocks.upload.mockResolvedValue("raw-artifacts/eng-a/file.txt");
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe.each(["aws", "azure"])("%s authorized storage callers", (cloud) => {
  beforeEach(() => vi.stubEnv("CNA_APPLIANCE_CLOUD", cloud));

  it("passes the record's engagement to signing only after download membership authorization", async () => {
    const response = await GET(new Request("https://app.invalid/api/deliverables/report-a"), {
      params: Promise.resolve({ id: "report-a" }),
    });
    expect(response.status).toBe(302);
    expect(mocks.sign).toHaveBeenCalledWith("deliverables/eng-a/report.md", "eng-a");
    expect(response.headers.get("location")).toBe("https://signed.invalid/download");
    expect(response.headers.get("cache-control")).toBe("private, no-store");
  });

  it("rejects unauthenticated and cross-engagement downloads without signing", async () => {
    mocks.auth.mockResolvedValueOnce(null);
    const params = () => ({ params: Promise.resolve({ id: "report-a" }) });
    expect((await GET(new Request("https://app.invalid"), params())).status).toBe(401);
    mocks.deliverable.mockResolvedValueOnce({
      engagement: { members: [{ userId: "other-user" }] },
    });
    expect((await GET(new Request("https://app.invalid"), params())).status).toBe(403);
    expect(mocks.sign).not.toHaveBeenCalled();
  });

  it("returns a clean unavailable response for a misconfigured download backend", async () => {
    vi.stubEnv("CNA_STORAGE_BUCKET", undefined);
    vi.stubEnv("AZURE_STORAGE_ACCOUNT_NAME", undefined);
    const response = await GET(new Request("https://app.invalid"), { params: Promise.resolve({ id: "report-a" }) });
    expect(response.status).toBe(501);
    expect(mocks.sign).not.toHaveBeenCalled();
  });

  it.each([
    ["assessment", deleteDeliverable], ["portal deliverable", deleteDeliverableFromPortal],
    ["document", deleteDocument],
  ] as const)("scopes %s deletion lookup and storage cleanup to the authorized engagement", async (kind, action) => {
    await action(form());
    expect(mocks.member).toHaveBeenCalledWith({
      where: { engagementId_userId: { engagementId: "eng-a", userId: "user-a" } },
    });
    const document = kind === "document";
    expect(document ? mocks.document : mocks.deliverable).toHaveBeenCalledWith({
      where: { id: document ? "document-a" : "report-a", engagementId: "eng-a" },
      select: { blobPath: true },
    });
    expect(mocks.deleteBlob).toHaveBeenCalledWith(
      document ? "raw-artifacts/eng-a/file.txt" : "deliverables/eng-a/report.md", "eng-a",
    );
  });

  it.each([deleteDeliverable, deleteDeliverableFromPortal, deleteDocument])(
    "never calls storage when membership or the engagement-scoped row is absent", async (action) => {
      mocks.member.mockResolvedValueOnce(null);
      await action(form());
      mocks.deliverable.mockResolvedValue(null);
      mocks.document.mockResolvedValue(null);
      await action(form());
      expect(mocks.deleteBlob).not.toHaveBeenCalled();
      expect(mocks.removeDocument).not.toHaveBeenCalled();
      expect(mocks.removeDeliverable).not.toHaveBeenCalled();
    },
  );

  it("keeps engagement teardown admin-only and passes exact scope to both storage deletion operations", async () => {
    mocks.member.mockResolvedValueOnce({ role: "ANALYST" });
    await deleteEngagement(form());
    expect(mocks.deleteBlob).not.toHaveBeenCalled();
    expect(mocks.removeEngagement).not.toHaveBeenCalled();
    await expect(deleteEngagement(form())).rejects.toThrow("test redirect");
    expect(mocks.deleteBlob).toHaveBeenCalledWith("raw-artifacts/eng-a/file.txt", "eng-a");
    expect(mocks.deleteBlob).toHaveBeenCalledWith("deliverables/eng-a/report.md", "eng-a");
    expect(mocks.deleteContainer).toHaveBeenCalledWith("portal-eng-a", "eng-a");
    expect(mocks.removeEngagement).toHaveBeenCalledWith({ where: { id: "eng-a" } });
  });

  it("enables document and nested diagram uploads only after membership authorization", async () => {
    const documentForm = form();
    documentForm.set("docType", "NETWORK_DIAGRAM");
    documentForm.set("file", new File(["text"], "notes.txt", { type: "text/plain" }));
    mocks.member.mockResolvedValueOnce(null);
    expect(await uploadDocument(null, documentForm)).toEqual({ error: "Access denied." });
    expect(mocks.upload).not.toHaveBeenCalled();
    expect(await uploadDocument(null, documentForm)).toEqual({ success: true });
    expect(mocks.upload).toHaveBeenCalledWith("eng-a", "notes.txt", Buffer.from("text"), "text/plain");
    const diagramForm = form();
    diagramForm.set("sourceFile", new File(["<mxfile/>"], "map.drawio", { type: "application/xml" }));
    expect(await saveDiagramSource(null, diagramForm)).toEqual({ success: true });
    expect(mocks.upload).toHaveBeenLastCalledWith(
      "eng-a", expect.stringMatching(/^diagrams\/\d+-map.drawio$/), Buffer.from("<mxfile/>"), "application/xml",
    );
  });
});

it("keeps external portal publishing disabled on AWS before any API call", async () => {
  expect(await publishClientPortal("eng-a")).toEqual({
    error: "External client portal publishing is not available on this appliance.",
  });
  expect(mocks.fetch).not.toHaveBeenCalled();
});

it("retains the configured Azure API publishing path and membership gate", async () => {
  vi.stubEnv("CNA_APPLIANCE_CLOUD", "azure");
  vi.stubEnv("CNA_API_INTERNAL_URL", "https://api.invalid");
  mocks.member.mockResolvedValueOnce(null);
  expect(await publishClientPortal("eng-a")).toEqual({ error: "Access denied." });
  expect(mocks.fetch).not.toHaveBeenCalled();
  mocks.fetch.mockResolvedValue({
    ok: true, json: async () => ({ portal_url: "https://portal.invalid", expires_at: "later", deliverable_count: 1 }),
  });
  await publishClientPortal("eng-a");
  expect(mocks.fetch).toHaveBeenCalledWith("https://api.invalid/publish", expect.objectContaining({
    method: "POST", body: JSON.stringify({ engagement_id: "eng-a", ttl_hours: 168 }),
  }));
});
