import { auth } from "@/lib/auth";
import { generateSasUrl } from "@/lib/blob";
import { prisma } from "@/lib/prisma";
import { NextResponse } from "next/server";

// Wraps Markdown content in a minimal print-friendly HTML page.
function markdownToHtml(title: string, markdown: string): string {
  // Escape HTML entities in the content so it renders safely inside <pre>.
  const escaped = markdown
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title.replace(/</g, "&lt;")}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f172a;
    color: #cbd5e1;
    padding: 2rem;
    line-height: 1.6;
  }
  .toolbar {
    position: fixed; top: 0; left: 0; right: 0;
    background: #1e293b;
    border-bottom: 1px solid #334155;
    padding: 0.75rem 2rem;
    display: flex; align-items: center; justify-content: space-between;
    z-index: 100;
  }
  .toolbar h1 { font-size: 0.875rem; font-weight: 600; color: #f1f5f9; }
  .btn-print {
    background: #0d9488; color: #fff; border: none;
    padding: 0.4rem 1rem; border-radius: 0.5rem; font-size: 0.8rem;
    font-weight: 600; cursor: pointer;
  }
  .btn-print:hover { background: #0f766e; }
  .content {
    margin-top: 3.5rem;
    max-width: 960px;
    margin-left: auto; margin-right: auto;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 0.75rem;
    padding: 2rem;
  }
  pre {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: "Consolas", "Monaco", "Courier New", monospace;
    font-size: 0.85rem;
    line-height: 1.7;
    color: #e2e8f0;
  }
  @media print {
    .toolbar { display: none; }
    body { background: #fff; color: #000; padding: 1rem; }
    .content { margin-top: 0; background: transparent; border: none; }
    pre { color: #000; }
  }
</style>
</head>
<body>
<div class="toolbar">
  <h1>${title.replace(/</g, "&lt;")}</h1>
  <button class="btn-print" onclick="window.print()">Print / Save as PDF</button>
</div>
<div class="content">
  <pre>${escaped}</pre>
</div>
</body>
</html>`;
}

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user?.id) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const { id } = await params;

  const deliverable = await prisma.deliverable.findUnique({
    where: { id },
    include: {
      engagement: {
        select: {
          members: { select: { userId: true } },
        },
      },
    },
  });

  if (!deliverable) {
    return new NextResponse("Not found", { status: 404 });
  }

  const isMember = deliverable.engagement.members.some(
    (m) => m.userId === session.user!.id,
  );
  if (!isMember) {
    return new NextResponse("Forbidden", { status: 403 });
  }

  if (!deliverable.content) {
    if (!deliverable.blobPath) {
      return new NextResponse("No content available for this deliverable.", {
        status: 404,
      });
    }
    const sasUrl = await generateSasUrl(deliverable.blobPath, 1);
    return NextResponse.redirect(sasUrl, { status: 302 });
  }

  const content = deliverable.content;
  const isHtml =
    deliverable.type === "COMPREHENSIVE_ASSESSMENT" ||
    content.trimStart().startsWith("<!DOCTYPE") ||
    content.trimStart().startsWith("<html");

  if (isHtml) {
    return new NextResponse(content, {
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
      },
    });
  }

  // Wrap Markdown in a print-friendly HTML page
  const html = markdownToHtml(deliverable.title, content);
  return new NextResponse(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Disposition": "inline",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
