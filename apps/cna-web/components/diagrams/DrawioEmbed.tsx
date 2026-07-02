"use client";

import { useEffect, useRef } from "react";

const DRAWIO_ORIGIN = "https://embed.diagrams.net";

/**
 * Embedded draw.io editor with the proto=json handshake completed.
 *
 * With proto=json, embed.diagrams.net shows its spinner and waits for the
 * host page to answer its "init" postMessage with a "load" action carrying
 * diagram XML. Without that reply the editor spins forever — which is
 * exactly what the previous bare <iframe> did. This component answers the
 * handshake with a blank canvas so the editor becomes usable immediately.
 */
export function DrawioEmbed({ initialXml = "" }: { initialXml?: string }) {
  const frameRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (event.origin !== DRAWIO_ORIGIN) return;
      if (event.source !== frameRef.current?.contentWindow) return;

      let msg: { event?: string } | null = null;
      try {
        msg = JSON.parse(event.data as string) as { event?: string };
      } catch {
        return;
      }
      if (msg?.event === "init") {
        frameRef.current?.contentWindow?.postMessage(
          JSON.stringify({ action: "load", xml: initialXml, autosave: 0 }),
          DRAWIO_ORIGIN,
        );
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [initialXml]);

  return (
    <iframe
      ref={frameRef}
      title="draw.io editor"
      src={`${DRAWIO_ORIGIN}/?embed=1&ui=min&spin=1&proto=json&libraries=1`}
      className="h-[560px] w-full"
    />
  );
}
