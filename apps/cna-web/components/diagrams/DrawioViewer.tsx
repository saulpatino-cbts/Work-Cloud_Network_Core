"use client";

import { useEffect, useState } from "react";

interface DrawioViewerProps {
  /** Public URL of the pre-rendered SVG. Rendered inline. */
  svgUrl?: string;
  /** Public URL of the original .drawio XML. Offered as a download. */
  xmlUrl?: string;
  /** Public URL of the rasterised PNG. Offered as a download. */
  pngUrl?: string;
  /** Public URL of the PDF wrap. Offered as a download. */
  pdfUrl?: string;
  /** Diagram display name (used as filename stem). */
  name: string;
  /** Optional class for the outer wrapper. */
  className?: string;
}

/**
 * Renders the pre-exported SVG of a draw.io diagram and links to the other
 * formats produced by the Python export pipeline.
 *
 * The interactive draw.io studio (iframe to viewer.diagrams.net) is a
 * follow-up: it requires loosening the global CSP `frame-src` directive and
 * a postMessage bridge to the in-app MCP surface. Until that ships, this
 * component is the deliverable-page viewer; the SVG is fully accessible.
 */
export function DrawioViewer({
  svgUrl,
  xmlUrl,
  pngUrl,
  pdfUrl,
  name,
  className,
}: DrawioViewerProps) {
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!svgUrl) return;
    let cancelled = false;
    setError(null);
    fetch(svgUrl, { credentials: "same-origin" })
      .then((r) => {
        if (!r.ok) throw new Error(`SVG fetch failed: ${r.status}`);
        return r.text();
      })
      .then((text) => {
        if (cancelled) return;
        // Light sanitisation: strip <script> tags. The pipeline-produced
        // SVGs are trusted but we still want defence-in-depth before
        // inlining via dangerouslySetInnerHTML.
        setSvg(text.replace(/<script[\s\S]*?<\/script>/gi, ""));
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [svgUrl]);

  return (
    <div className={className}>
      <div className="rounded border border-gray-200 bg-white p-4 overflow-auto">
        {svgUrl ? (
          error ? (
            <p className="text-sm text-red-600">Failed to load diagram: {error}</p>
          ) : svg ? (
            <div
              className="drawio-svg"
              // eslint-disable-next-line react/no-danger -- trusted pipeline output, scripts stripped above
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          ) : (
            <p className="text-sm text-gray-500">Loading diagram…</p>
          )
        ) : (
          <p className="text-sm text-gray-500">
            No rendered SVG available for {name}.
          </p>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-sm">
        {xmlUrl && (
          <a
            href={xmlUrl}
            download={`${name}.drawio`}
            className="text-blue-700 underline hover:no-underline"
          >
            Download .drawio
          </a>
        )}
        {pngUrl && (
          <a
            href={pngUrl}
            download={`${name}.png`}
            className="text-blue-700 underline hover:no-underline"
          >
            Download .png
          </a>
        )}
        {pdfUrl && (
          <a
            href={pdfUrl}
            download={`${name}.pdf`}
            className="text-blue-700 underline hover:no-underline"
          >
            Download .pdf
          </a>
        )}
      </div>
    </div>
  );
}

export default DrawioViewer;
