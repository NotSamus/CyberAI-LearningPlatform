"use client";
import { FileCheck, Upload } from "lucide-react";
import { useRef, useState } from "react";

// A file field as a place to drop a file onto, or to tap to choose one, in place of the browser's
// "Choose File / No file chosen". The real field is inside it, out of sight but reached with Tab like
// any other, so a form's `required` and screen readers work as before. Browsers do not hold a dropped
// file to `accept`, so that is checked here.
export default function FileDrop({ accept, what, hint, file = null, busy = false, required, focusId, onFile }: {
  accept: string;             // as on <input type="file">: ".ipynb", or "image/png,image/jpeg"
  what: string;               // what to choose, in words: "a .ipynb file", "a picture"
  hint?: string;              // which files, and how large they may be
  file?: File | null;         // the one chosen, shown with its size
  busy?: boolean;             // it is being uploaded: nothing else can be chosen meanwhile
  required?: boolean;
  focusId?: string;           // for the lesson editor, which puts the cursor in a block by its data-focus
  onFile: (file: File | null) => void;
}) {
  const input = useRef<HTMLInputElement | null>(null);
  const depth = useRef(0);            // dragenter and dragleave also fire for the parts inside: they are counted
  const [over, setOver] = useState(false);
  const [refused, setRefused] = useState("");

  function fits(f: File): boolean {
    return accept.split(",").map((kind) => kind.trim().toLowerCase()).some((kind) =>
      kind.startsWith(".") ? f.name.toLowerCase().endsWith(kind)
        : kind.endsWith("/*") ? f.type.startsWith(kind.slice(0, -1))
          : f.type === kind);
  }

  function drop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();        // the lesson editor around a picture block would otherwise add the picture again, as a block of its own
    depth.current = 0;
    setOver(false);
    const dropped = e.dataTransfer.files[0];
    if (busy || !dropped) return;
    if (!fits(dropped)) {
      setRefused(`${dropped.name} is not ${what}.`);
      return;
    }
    setRefused("");
    // Into the real field too, so that the form has it (and a required field counts as filled).
    const list = new DataTransfer();
    list.items.add(dropped);
    if (input.current) input.current.files = list.files;
    onFile(dropped);
  }

  const files = (e: React.DragEvent) => e.dataTransfer.types.includes("Files");
  return (
    <label
      className={`file-drop ${over ? "over" : ""}`}
      onDragEnter={(e) => { if (!files(e)) return; e.preventDefault(); depth.current += 1; setOver(true); }}
      onDragOver={(e) => { if (files(e)) e.preventDefault(); }}
      onDragLeave={(e) => {
        if (!files(e)) return;
        depth.current = Math.max(0, depth.current - 1);
        if (depth.current === 0) setOver(false);
      }}
      onDrop={drop}
    >
      <input
        ref={input} type="file" className="visually-hidden" accept={accept} required={required} disabled={busy} data-focus={focusId}
        onChange={(e) => { setRefused(""); onFile(e.target.files?.[0] ?? null); }}
      />
      <span className="tile">{file && !busy ? <FileCheck aria-hidden /> : <Upload aria-hidden />}</span>
      <span className="file-drop-words">
        {busy ? <strong>Uploading…</strong>
          : file ? <strong>{file.name}</strong>
            : <span><strong>Choose {what}</strong> or drop it here</span>}
        {!busy && (file
          ? <span className="muted">{size(file.size)}. To change it, choose another or drop it here.</span>
          : hint && <span className="muted">{hint}</span>)}
        {refused && <span className="error" role="alert">{refused}</span>}
      </span>
    </label>
  );
}

function size(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
