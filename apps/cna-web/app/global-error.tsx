"use client";

// Last-resort boundary: catches errors thrown by the root layout itself.
// Must render its own <html>/<body> because it replaces the root layout.
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", display: "grid", placeItems: "center", minHeight: "100vh", margin: 0, background: "#0b1526", color: "#e2e8f0" }}>
        <div style={{ textAlign: "center", maxWidth: 420, padding: 24 }}>
          <h1 style={{ fontSize: 18, fontWeight: 800 }}>This page couldn&apos;t load</h1>
          <p style={{ fontSize: 13, color: "#94a3b8" }}>
            A server error occurred and has been logged.
            {error.digest ? ` Error reference: ${error.digest}` : ""}
          </p>
          <button
            onClick={reset}
            style={{ marginTop: 16, padding: "8px 16px", borderRadius: 8, border: 0, background: "#0d9488", color: "#fff", fontWeight: 700, cursor: "pointer" }}
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
