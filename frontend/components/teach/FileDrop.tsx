"use client";
import { FileCheck, Upload } from "lucide-react";
import { useRef, useState } from "react";

// A file field as a place to drop a file onto, or to tap to choose one, in place of the browser's
// "Choose File / No file chosen". The real field is inside it, out of sight but reached with Tab like
// any other, so a form's `required` and screen readers work as before. Browsers do not hold a dropped
// file to `accept`, so that is checked here. `multiple`: several files at once (`files`, `onFiles`).
export default function FileDrop({ accept = "", what, hint, file = null, files = [], multiple = false, busy = false, required, focusId, onFile, onFiles }: {
  accept?: string;            // as on <input type="file">: ".ipynb", or "image/png,image/jpeg"; any file when left out
  what: string;               // what to choose, in words: "a .ipynb file", "a picture", "data files"
  hint?: string;              // which files, and how large they may be
  file?: File | null;         // the one chosen, shown with its size
  files?: File[];             // with `multiple`: the ones chosen
  multiple?: boolean;
  busy?: boolean;             // it is being uploaded: nothing else can be chosen meanwhile
  required?: boolean;
  focusId?: string;           // for the lesson editor, which puts the cursor in a block by its data-focus
  onFile?: (file: File | null) => void;
  onFiles?: (files: File[]) => void;
}) {
  const input = useRef<HTMLInputElement | null>(null);
  const depth = useRef(0);            // dragenter and dragleave also fire for the parts inside: they are counted
  const [over, setOver] = useState(false);
  const [refused, setRefused] = useState("");

  function fits(f: File): boolean {
    if (!accept) return true;
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
    const dropped = multiple ? Array.from(e.dataTransfer.files) : Array.from(e.dataTransfer.files).slice(0, 1);
    if (busy || dropped.length === 0) return;
    const wrong = dropped.find((f) => !fits(f));
    if (wrong) {
      setRefused(`${wrong.name} is not ${what}.`);
      return;
    }
    setRefused("");
    // Into the real field too, so that the form has it (and a required field counts as filled).
    const list = new DataTransfer();
    dropped.forEach((f) => list.items.add(f));
    if (input.current) input.current.files = list.files;
    if (multiple) onFiles?.(dropped); else onFile?.(dropped[0]);
  }

  const chosen = multiple ? files : file ? [file] : [];

  const carriesFiles = (e: React.DragEvent) => e.dataTransfer.types.includes("Files");
  return (
    <label
      className={`file-drop ${over ? "over" : ""}`}
      onDragEnter={(e) => { if (!carriesFiles(e)) return; e.preventDefault(); depth.current += 1; setOver(true); }}
      onDragOver={(e) => { if (carriesFiles(e)) e.preventDefault(); }}
      onDragLeave={(e) => {
        if (!carriesFiles(e)) return;
        depth.current = Math.max(0, depth.current - 1);
        if (depth.current === 0) setOver(false);
      }}
      onDrop={drop}
    >
      <input
        ref={input} type="file" className="visually-hidden" accept={accept || undefined} multiple={multiple} required={required}
        disabled={busy} data-focus={focusId}
        onChange={(e) => {
          setRefused("");
          if (multiple) onFiles?.(Array.from(e.target.files ?? [])); else onFile?.(e.target.files?.[0] ?? null);
        }}
      />
      <span className="tile">{chosen.length > 0 && !busy ? <FileCheck aria-hidden /> : <Upload aria-hidden />}</span>
      <span className="file-drop-words">
        {busy ? <strong>Uploading…</strong>
          : chosen.length > 0 ? <strong>{chosen.map((f) => f.name).join(", ")}</strong>
            : <span><strong>Choose {what}</strong> or drop {multiple ? "them" : "it"} here</span>}
        {!busy && (chosen.length > 0
          ? (
            <span className="muted">
              {fileSize(chosen.reduce((sum, f) => sum + f.size, 0))}
              {multiple ? ` in ${chosen.length === 1 ? "1 file" : `${chosen.length} files`}. To change them, choose others or drop them here.`
                : ". To change it, choose another or drop it here."}
            </span>
          )
          : hint && <span className="muted">{hint}</span>)}
        {refused && <span className="error" role="alert">{refused}</span>}
      </span>
    </label>
  );
}

export function fileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
