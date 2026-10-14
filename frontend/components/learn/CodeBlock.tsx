"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";
import { highlighted } from "@/lib/highlight";

// A code block of a lesson: a strip with its language and a button that copies the code, and the
// code in the colours of its language (lib/highlight.ts).
export default function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState<"" | "copied" | "selected">("");
  const pre = useRef<HTMLPreElement | null>(null);
  const coloured = useMemo(() => highlighted(language, code), [language, code]);

  // "Copied" for a moment, then the button is back to what it was.
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(""), 2000);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copy() {
    try {
      // Missing when the site is opened over plain http at a network address (./dev.sh --lan): then it throws.
      await navigator.clipboard.writeText(code);
      setCopied("copied");
    } catch {
      // The code is selected instead, to be copied by hand.
      const selection = window.getSelection();
      if (!pre.current || !selection) return;
      const range = document.createRange();
      range.selectNodeContents(pre.current);
      selection.removeAllRanges();
      selection.addRange(range);
      setCopied("selected");
    }
  }

  return (
    <figure className="code">
      <figcaption>
        <span className="language">{language}</span>
        <button type="button" className="copy" onClick={copy} aria-live="polite">
          {copied === "copied" ? <><Check aria-hidden />Copied</>
            : copied === "selected" ? "Selected: copy it now"
            : <><Copy aria-hidden />Copy</>}
        </button>
      </figcaption>
      <pre ref={pre}><code className="hljs">{coloured}</code></pre>
    </figure>
  );
}
