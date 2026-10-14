"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowUp, CircleAlert, Copy, Eye, Plus, Send, Trash2, Undo2, Users, X } from "lucide-react";
import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import LessonRail, { leftLesson } from "@/components/LessonRail";
import Markdown from "@/components/Markdown";
import Menu from "@/components/Menu";
import PageHeader from "@/components/PageHeader";
import { Label, publishLabel } from "@/components/Status";
import FileDrop from "@/components/teach/FileDrop";
import LessonTabs from "@/components/teach/LessonTabs";
import { api, type Course, type ManagedAssignment } from "@/lib/api";
import { formatWhen } from "@/lib/dates";
import { JSON_HEADERS, message } from "@/lib/errors";
import {
  BLOCK_LABELS, BLOCK_MENU, MAX_IMAGE_BYTES, MAX_OPTIONS, duplicate, importText, newId, outline, youtubeId,
  type Block, type Kind, type LessonDraft, type ManagedLesson, type Tone,
} from "@/lib/lessons";

type Saving = "saved" | "unsaved" | "saving" | "failed";
type Of<T extends Block["type"]> = Extract<Block, { type: T }>;

function make(kind: Kind): Block {
  return BLOCK_MENU.find((item) => item.kind === kind)!.make();
}

// What is sent to the server when the lesson is saved. An emptied title is left out: the saved one stays.
function toSave(title: string, summary: string, audience: string, blocks: Block[]): string {
  return JSON.stringify({
    ...(title.trim() ? { title } : {}),
    summary,
    for_everyone: audience === "everyone",
    course_id: audience === "none" || audience === "everyone" ? null : Number(audience),
    blocks,
  });
}

// Teach > Lessons > a lesson: the page a lesson is written on. Everything typed is saved a moment
// later as the working copy; students get it when Publish is pressed. The title and the summary are
// typed in the page's header, where they will stand for students too.
export default function LessonEditor({ lessonId }: { lessonId: string }) {
  const router = useRouter();
  const [lesson, setLesson] = useState<ManagedLesson | null>(null);
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [audience, setAudience] = useState("none");       // "none", "everyone", or the id of a course
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [assignments, setAssignments] = useState<ManagedAssignment[]>([]);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState<Saving>("saved");
  const [error, setError] = useState("");
  const [problems, setProblems] = useState("");           // why it could not be published
  const [busy, setBusy] = useState(false);
  const [focus, setFocus] = useState<string | null>(null);    // a block or option to put the cursor in
  const active = useRef<string | null>(null);             // the block being worked on: pasted pictures go after it

  const draft = useMemo(() => toSave(title, summary, audience, blocks), [title, summary, audience, blocks]);
  const latest = useRef(draft);                           // what is on screen
  latest.current = draft;
  const saved = useRef<string | null>(null);              // what the server has; null until the lesson is loaded
  const sending = useRef<Promise<boolean> | null>(null);

  useEffect(() => {
    Promise.all([
      api<LessonDraft>(`/teach/lessons/${lessonId}`), api<Course[]>("/teach/courses"), api<ManagedAssignment[]>("/teach/assignments"),
    ])
      .then(([loaded, classes, notebooks]) => {
        const given = loaded.for_everyone ? "everyone" : loaded.course_id !== null ? String(loaded.course_id) : "none";
        saved.current = toSave(loaded.title, loaded.summary, given, loaded.blocks);
        setLesson(loaded);
        setTitle(loaded.title);
        setSummary(loaded.summary);
        setAudience(given);
        if (loaded.blocks.length > 0) {
          setBlocks(loaded.blocks);
        } else {            // nothing written yet: start with a text block, ready to type in
          const first = make("text");
          setBlocks([first]);
          setFocus(first.id);
        }
        setCourses(classes);
        setAssignments(notebooks);
      })
      .catch((e) => setLoadError(message(e)));
  }, [lessonId]);

  // Saves what is on screen, if the server does not have it yet. One save at a time, so that an
  // older one can never land on top of a newer one.
  const save = useCallback(async (): Promise<boolean> => {
    while (sending.current) await sending.current;
    const body = latest.current;
    if (saved.current === null) return false;
    if (body === saved.current) return true;
    setSaving("saving");
    sending.current = api<ManagedLesson>(`/teach/lessons/${lessonId}`, { method: "PATCH", headers: JSON_HEADERS, body }).then(
      (details) => {
        saved.current = body;
        setLesson(details);
        setError("");
        setSaving(latest.current === body ? "saved" : "unsaved");
        return true;
      },
      (e) => {
        setError(`Not saved. ${message(e)}`);
        setSaving("failed");
        return false;
      },
    );
    const ok = await sending.current;
    sending.current = null;
    return ok;
  }, [lessonId]);

  // A moment after the last change, save.
  useEffect(() => {
    if (saved.current === null || draft === saved.current) return;
    setSaving((now) => (now === "saving" ? now : "unsaved"));
    const timer = setTimeout(save, 800);
    return () => clearTimeout(timer);
  }, [draft, save]);

  // Leaving with changes that are not saved yet: to another page of the site, save them now;
  // closing the tab, the browser asks first.
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (saved.current !== null && latest.current !== saved.current) e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => {
      window.removeEventListener("beforeunload", warn);
      leftLesson(save());       // the list beside the next lesson waits for this, to show what was just written
    };
  }, [save]);

  useEffect(() => {
    if (!focus) return;
    document.querySelector<HTMLElement>(`[data-focus="${focus}"]`)?.focus();
    setFocus(null);
  }, [focus]);

  function change(id: string, changes: Partial<Block>) {
    setBlocks((all) => all.map((b) => (b.id === id ? ({ ...b, ...changes } as Block) : b)));
  }

  function insert(index: number, block: Block) {
    setBlocks((all) => [...all.slice(0, index), block, ...all.slice(index)]);
    setFocus(block.id);
  }

  function remove(index: number) {
    setFocus(blocks[index - 1]?.id ?? blocks[index + 1]?.id ?? null);
    setBlocks((all) => all.filter((b) => b.id !== blocks[index].id));
  }

  function move(index: number, by: -1 | 1) {
    setBlocks((all) => {
      const moved = [...all];
      [moved[index], moved[index + by]] = [moved[index + by], moved[index]];
      return moved;
    });
  }

  // "/" in a text block: the block becomes the chosen one, or, when there is text above the "/",
  // the chosen one is added below it.
  function slash(block: Of<"text">, kind: Kind, before: string) {
    const made = make(kind);
    setBlocks((all) => all.flatMap((b) => {
      if (b.id !== block.id) return [b];
      return before.trim() === "" ? [made] : [{ ...block, text: before.trimEnd() }, made];
    }));
    setFocus(made.id);
  }

  async function uploadPicture(file: File): Promise<number | null> {
    setError("");
    if (file.size > MAX_IMAGE_BYTES) {      // a quick answer here; the server enforces the same limit
      setError("The picture is larger than 5 MB. Make it smaller and try again.");
      return null;
    }
    const form = new FormData();
    form.set("lesson_id", lessonId);
    form.set("file", file);
    try {
      return (await api<{ id: number }>("/teach/lesson-images", { method: "POST", body: form })).id;
    } catch (e) {
      setError(message(e));
      return null;
    }
  }

  // Pictures pasted or dropped anywhere in the lesson become picture blocks, below the block being worked on.
  async function addPictures(files: File[]) {
    for (const file of files) {
      const image_id = await uploadPicture(file);
      if (image_id === null) return;
      const block: Block = { type: "image", id: newId(), image_id, alt: "" };
      setBlocks((all) => {
        const index = all.findIndex((b) => b.id === active.current);
        const at = index === -1 ? all.length : index + 1;
        return [...all.slice(0, at), block, ...all.slice(at)];
      });
      active.current = block.id;
      setFocus(block.id);
    }
  }

  function pictures(files: FileList): File[] {
    return Array.from(files).filter((f) => f.type.startsWith("image/"));
  }

  async function publish() {
    setBusy(true);
    setProblems("");
    if (await save()) {
      try {
        setLesson(await api<ManagedLesson>(`/teach/lessons/${lessonId}/publish`, { method: "POST" }));
      } catch (e) {
        setProblems(message(e));
      }
    }
    setBusy(false);
  }

  async function unpublish() {
    setBusy(true);
    setProblems("");
    try {
      setLesson(await api<ManagedLesson>(`/teach/lessons/${lessonId}/unpublish`, { method: "POST" }));
    } catch (e) {
      setProblems(message(e));
    }
    setBusy(false);
  }

  async function preview() {
    if (await save()) router.push(`/lessons/${lessonId}`);
  }

  const upToDate = saving === "saved" && !lesson?.changed;
  // The lesson as it is on screen, for the list beside the editor, and the topics its headings make.
  const live = useMemo(
    () => lesson && { ...lesson, title: title.trim() || lesson.title, changed: lesson.published && !upToDate, blocks_count: blocks.length },
    [lesson, title, upToDate, blocks.length],
  );
  const topics = useMemo(() => outline(blocks), [blocks]);
  const rail = <LessonRail currentId={Number(lessonId)} live={live} topics={topics} />;
  const tabs = <LessonTabs id={lessonId} />;
  const crumbs = [{ label: "Lessons", href: "/teach/lessons" }];

  if (loadError) {
    return (
      <div className="writing">
        <PageHeader crumbs={crumbs} title="Lesson" tabs={tabs} />
        {rail}
        <div className="editor"><p className="error" role="alert">{loadError}</p></div>
      </div>
    );
  }
  if (!lesson) {
    return (
      <div className="writing">
        <PageHeader crumbs={crumbs} title="Lesson" tabs={tabs} />
        {rail}
        <div className="editor"><p className="muted">Loading…</p></div>
      </div>
    );
  }

  // What students see of it right now, in a few words, next to whether it is saved.
  const seen = !lesson.published ? "Students cannot see this lesson until you publish it."
    : upToDate ? "Students see the lesson as it is here."
      : `Students still see the version of ${formatWhen(lesson.published_at)}.`;

  return (
    <div
      className="writing"
      onPaste={(e) => {
        // Only when a picture is all there is: text copied from a document often carries a picture of itself.
        const found = pictures(e.clipboardData.files);
        if (found.length === 0 || e.clipboardData.getData("text/plain") !== "") return;
        e.preventDefault();
        addPictures(found);
      }}
      onDragOver={(e) => { if (e.dataTransfer.types.includes("Files")) e.preventDefault(); }}
      onDrop={(e) => {
        const found = pictures(e.dataTransfer.files);
        if (found.length === 0) return;
        e.preventDefault();
        addPictures(found);
      }}
    >
      <PageHeader
        crumbs={[...crumbs, { label: title.trim() || lesson.title }]}
        title={
          <input
            className="lesson-title" value={title} maxLength={120} placeholder="Lesson title" aria-label="Lesson title"
            onChange={(e) => setTitle(e.target.value)}
          />
        }
        status={<Label standing={publishLabel({ published: lesson.published, changed: !upToDate })} />}
        description={
          <input
            className="lesson-summary" value={summary} maxLength={300} aria-label="Summary"
            placeholder="One line about this lesson, shown on its card (optional)"
            onChange={(e) => setSummary(e.target.value)}
          />
        }
        meta={
          <>
            <label className="fact">
              <Users aria-hidden />For
              <select value={audience} onChange={(e) => setAudience(e.target.value)}>
                <option value="none">Nobody yet</option>
                <option value="everyone">All students</option>
                {courses.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.student_ids.length})</option>)}
              </select>
            </label>
            <span role="status">{saving === "saved" ? "Saved" : saving === "failed" ? "Not saved" : "Saving…"}</span>
            {saving === "failed" && <button className="text-button" onClick={save}>Try again</button>}
            <span>{seen}</span>
          </>
        }
        actions={
          <>
            <button className="secondary" onClick={preview}><Eye aria-hidden />Preview</button>
            <button disabled={busy || (lesson.published && upToDate)} onClick={publish}>
              <Send aria-hidden />{busy ? "Publishing…" : lesson.published ? "Publish changes" : "Publish"}
            </button>
            {lesson.published && (
              <Menu label="More for this lesson" items={[{ label: "Unpublish", icon: Undo2, disabled: busy, onSelect: unpublish }]} />
            )}
          </>
        }
        tabs={tabs}
      />
      {rail}

    <div className="editor">
      {title.trim() === "" && <p className="error">A lesson needs a title: until it has one, the earlier title is kept.</p>}
      {lesson.published && audience === "none" && (
        <p className="error">Published, but given to nobody: no student can see it. Choose who it is for, above.</p>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      {problems && <p className="error log" role="alert">Not published yet:{"\n"}{problems}</p>}
      {/* The header is out of sight while writing further down: a failed save shows here too, in a
          corner of the screen, until a save goes through. */}
      {saving === "failed" && (
        <p className="save-failed" role="alert">
          <CircleAlert aria-hidden />Your last changes are not saved.
          <button className="text-button" onClick={save}>Try again</button>
        </p>
      )}

      {blocks.map((block, index) => (
        <Fragment key={block.id}>
          {index > 0 && <AddHere onAdd={(kind) => insert(index, make(kind))} />}
          <div
            className="block"
            onFocus={() => { active.current = block.id; }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                insert(index + 1, make("text"));
              }
            }}
          >
            <div className="block-bar">
              <span className="check-label">{BLOCK_LABELS[block.type]}</span>
              <span className="spacer" />
              <button className="icon" title="Move up" aria-label="Move up" disabled={index === 0} onClick={() => move(index, -1)}><ArrowUp aria-hidden /></button>
              <button className="icon" title="Move down" aria-label="Move down" disabled={index === blocks.length - 1} onClick={() => move(index, 1)}><ArrowDown aria-hidden /></button>
              <button className="icon" title="Duplicate" aria-label="Duplicate" onClick={() => insert(index + 1, duplicate(block))}><Copy aria-hidden /></button>
              <button className="icon danger" title="Delete" aria-label="Delete" onClick={() => remove(index)}><Trash2 aria-hidden /></button>
            </div>
            {block.type === "text" && (
              <TextEditor
                block={block}
                onChange={(changes) => change(block.id, changes)}
                onSlash={(kind, before) => slash(block, kind, before)}
                onEmptyBackspace={() => { if (blocks.length > 1) remove(index); }}
              />
            )}
            {block.type === "multiple_choice" && <ChoiceEditor block={block} onChange={(changes) => change(block.id, changes)} onFocus={setFocus} />}
            {block.type === "short_answer" && <WrittenEditor block={block} onChange={(changes) => change(block.id, changes)} />}
            {block.type === "code" && (
              <>
                <input
                  className="language" value={block.language} maxLength={30} placeholder="Language" aria-label="Language"
                  onChange={(e) => change(block.id, { language: e.target.value.replace(/[^A-Za-z0-9+#. _-]/g, "") })}
                />
                <Growing
                  className="mono" data-focus={block.id} value={block.code} maxLength={20000} spellCheck={false}
                  placeholder="Code" aria-label="Code" onChange={(e) => change(block.id, { code: e.target.value })}
                />
              </>
            )}
            {block.type === "callout" && (
              <>
                <select value={block.tone} aria-label="Kind of callout" onChange={(e) => change(block.id, { tone: e.target.value as Tone })}>
                  <option value="note">Note</option>
                  <option value="tip">Tip</option>
                  <option value="warning">Warning</option>
                </select>
                <Growing
                  data-focus={block.id} value={block.text} maxLength={20000} placeholder="What readers should notice (Markdown)"
                  aria-label="Callout text" onChange={(e) => change(block.id, { text: e.target.value })}
                />
              </>
            )}
            {block.type === "image" && (
              <PictureEditor block={block} lessonId={lessonId} upload={uploadPicture} onChange={(changes) => change(block.id, changes)} />
            )}
            {block.type === "video" && <VideoEditor block={block} onChange={(changes) => change(block.id, changes)} />}
            {block.type === "assignment" && (
              <>
                <select
                  data-focus={block.id} value={block.assignment_id ?? ""} aria-label="Notebook assignment"
                  onChange={(e) => change(block.id, { assignment_id: e.target.value === "" ? null : Number(e.target.value) })}
                >
                  <option value="">Choose a notebook assignment…</option>
                  {assignments.map((a) => <option key={a.id} value={a.id}>{a.title}{a.published ? "" : " (draft)"}</option>)}
                </select>
                <p className="muted">
                  Readers get a link to open the notebook. Only students the assignment was given to see the link:
                  give it to them under <Link href="/teach/assignments">Assignments</Link>.
                </p>
              </>
            )}
          </div>
        </Fragment>
      ))}

      <div className="add-block">
        <span className="muted">Add</span>
        {BLOCK_MENU.map((item) => (
          <button key={item.kind} className="secondary" onClick={() => insert(blocks.length, make(item.kind))}>{item.label}</button>
        ))}
      </div>
      <p className="muted hint">
        Quicker from the keyboard: type <kbd>/</kbd> on an empty line of a text block to turn it into another block,
        press <kbd>Ctrl</kbd>/<kbd>⌘</kbd>+<kbd>Enter</kbd> for a new text block below, and paste or drop pictures anywhere.
      </p>
      <ImportText onImport={(made) => { setBlocks((all) => [...all, ...made]); setFocus(made[0]?.id ?? null); }} />
    </div>
    </div>
  );
}

// A text field that is as tall as what is written in it.
function Growing({ inputRef, value, ...rest }: React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  value: string;
  inputRef?: React.RefObject<HTMLTextAreaElement | null>;
}) {
  const own = useRef<HTMLTextAreaElement | null>(null);
  const ref = inputRef ?? own;
  useLayoutEffect(() => {
    const area = ref.current;
    if (!area) return;
    area.style.height = "auto";
    area.style.height = `${area.scrollHeight + 2}px`;
  }, [ref, value]);
  return <textarea ref={ref} rows={1} value={value} {...rest} />;
}

// The row between two blocks: a "+" that opens the list of blocks to add there.
function AddHere({ onAdd }: { onAdd: (kind: Kind) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`add-here ${open ? "open" : ""}`}>
      <button className="icon" title="Add a block here" aria-label="Add a block here" aria-expanded={open} onClick={() => setOpen(!open)}><Plus aria-hidden /></button>
      {open && BLOCK_MENU.map((item) => (
        <button key={item.kind} className="secondary" onClick={() => { setOpen(false); onAdd(item.kind); }}>{item.label}</button>
      ))}
    </div>
  );
}

// Text is shown as readers will see it, and becomes a text field while it is being edited, like a
// text cell in a notebook. A last line that starts with "/" opens the menu of blocks.
function TextEditor({ block, onChange, onSlash, onEmptyBackspace }: {
  block: Of<"text">;
  onChange: (changes: Partial<Of<"text">>) => void;
  onSlash: (kind: Kind, before: string) => void;
  onEmptyBackspace: () => void;
}) {
  const [editing, setEditing] = useState(block.text.trim() === "");
  const [picked, setPicked] = useState(0);
  const [menuClosed, setMenuClosed] = useState(false);    // by Esc, until the text changes
  const area = useRef<HTMLTextAreaElement | null>(null);
  const takeCursor = useRef(false);

  useEffect(() => {
    if (!editing || !takeCursor.current) return;
    takeCursor.current = false;
    area.current?.focus();
    area.current?.setSelectionRange(area.current.value.length, area.current.value.length);
  }, [editing]);

  if (!editing) {
    const edit = () => { takeCursor.current = true; setEditing(true); };
    return (
      <div className="rendered" tabIndex={0} data-focus={block.id} title="Click to edit" onClick={edit} onFocus={edit}>
        <Markdown text={block.text} anchors={block.id} />
      </div>
    );
  }

  const lastLine = block.text.slice(block.text.lastIndexOf("\n") + 1);
  const typed = /^\/[a-z ]{0,20}$/i.test(lastLine) ? lastLine.slice(1).toLowerCase() : null;
  const menu = typed === null || menuClosed ? [] : BLOCK_MENU.filter((item) => item.words.some((word) => word.startsWith(typed)));
  const choose = (kind: Kind) => onSlash(kind, block.text.slice(0, block.text.length - lastLine.length));

  return (
    <div className="text-editor">
      <Growing
        inputRef={area} data-focus={block.id} value={block.text} maxLength={20000} aria-label="Text"
        placeholder="Write here (Markdown), or type / for a question, code, a picture…"
        onChange={(e) => { setMenuClosed(false); setPicked(0); onChange({ text: e.target.value }); }}
        onBlur={() => { if (block.text.trim() !== "") setEditing(false); }}
        onKeyDown={(e) => {
          if (menu.length > 0 && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
            e.preventDefault();
            setPicked((n) => (n + (e.key === "ArrowDown" ? 1 : menu.length - 1)) % menu.length);
          } else if (menu.length > 0 && (e.key === "Enter" || e.key === "Tab")) {
            e.preventDefault();
            e.stopPropagation();
            choose(menu[Math.min(picked, menu.length - 1)].kind);
          } else if (menu.length > 0 && e.key === "Escape") {
            setMenuClosed(true);
          } else if (e.key === "Backspace" && block.text === "") {
            e.preventDefault();
            onEmptyBackspace();
          }
        }}
      />
      {menu.length > 0 && (
        <ul className="slash-menu" role="listbox" aria-label="Blocks">
          {menu.map((item, n) => (
            <li
              key={item.kind} role="option" aria-selected={n === picked} className={n === picked ? "picked" : ""}
              onMouseDown={(e) => { e.preventDefault(); choose(item.kind); }}
            >
              {item.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ChoiceEditor({ block, onChange, onFocus }: {
  block: Of<"multiple_choice">;
  onChange: (changes: Partial<Of<"multiple_choice">>) => void;
  onFocus: (id: string) => void;
}) {
  const { options } = block;
  const correct = options.filter((o) => o.correct).length;

  function setOption(id: string, changes: { text?: string; correct?: boolean }) {
    onChange({ options: options.map((o) => (o.id === id ? { ...o, ...changes } : o)) });
  }

  function addOption(after: number) {
    if (options.length >= MAX_OPTIONS) return;
    const added = { id: newId(), text: "", correct: false };
    onChange({ options: [...options.slice(0, after + 1), added, ...options.slice(after + 1)] });
    onFocus(added.id);
  }

  function removeOption(index: number) {
    onChange({ options: options.filter((_, n) => n !== index) });
    onFocus(options[index - 1]?.id ?? options[index + 1]?.id ?? block.id);
  }

  return (
    <>
      <Growing
        className="question" data-focus={block.id} value={block.question} maxLength={2000} placeholder="Question"
        aria-label="Question" onChange={(e) => onChange({ question: e.target.value })}
      />
      <ul className="option-list">
        {options.map((option, index) => (
          <li key={option.id}>
            {/* The text comes before its tick box here, so that Tab goes from the question straight to the first option; the page shows the tick box first. */}
            <input
              data-focus={option.id} value={option.text} maxLength={500} placeholder={`Option ${index + 1}`} aria-label={`Option ${index + 1}`}
              onChange={(e) => {
                // "*" in front ticks the option: marking the right answer without leaving the keyboard.
                const text = e.target.value;
                setOption(option.id, text.startsWith("*") ? { text: text.slice(1).trimStart(), correct: true } : { text });
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.metaKey && !e.ctrlKey) {
                  e.preventDefault();
                  const next = options[index + 1];
                  if (next && next.text === "") onFocus(next.id);     // an empty one is waiting below: use it
                  else addOption(index);
                } else if (e.key === "Backspace" && option.text === "" && options.length > 1) {
                  e.preventDefault();
                  removeOption(index);
                }
              }}
            />
            <input
              type="checkbox" checked={option.correct} title="This option is correct" aria-label={`Option ${index + 1} is correct`}
              onChange={(e) => setOption(option.id, { correct: e.target.checked })}
            />
            <button className="icon danger" title="Remove this option" aria-label={`Remove option ${index + 1}`} onClick={() => removeOption(index)}><X aria-hidden /></button>
          </li>
        ))}
      </ul>
      <p className="row muted">
        <button className="secondary" disabled={options.length >= MAX_OPTIONS} onClick={() => addOption(options.length - 1)}>Add an option</button>
        <span>
          {correct === 0 && "Tick the correct option, or start it with *. "}
          {correct === 1 && "Students choose one option. "}
          {correct > 1 && "Students must choose every ticked option. "}
          Enter adds an option; options left empty are ignored.
        </span>
      </p>
      <Growing
        value={block.explanation} maxLength={2000} aria-label="Explanation"
        placeholder="Explanation, shown once the question is answered (optional)"
        onChange={(e) => onChange({ explanation: e.target.value })}
      />
    </>
  );
}

function WrittenEditor({ block, onChange }: { block: Of<"short_answer">; onChange: (changes: Partial<Of<"short_answer">>) => void }) {
  return (
    <>
      <Growing
        className="question" data-focus={block.id} value={block.question} maxLength={2000} placeholder="Question"
        aria-label="Question" onChange={(e) => onChange({ question: e.target.value })}
      />
      <Growing
        value={block.answers.join("\n")} aria-label="Accepted answers"
        placeholder="Accepted answers, one per line. Capital letters and extra spaces do not matter."
        onChange={(e) => onChange({ answers: e.target.value.split("\n").slice(0, 10).map((answer) => answer.slice(0, 200)) })}
      />
      <Growing
        value={block.explanation} maxLength={2000} aria-label="Explanation"
        placeholder="Explanation, shown once the question is answered (optional)"
        onChange={(e) => onChange({ explanation: e.target.value })}
      />
    </>
  );
}

function PictureEditor({ block, lessonId, upload, onChange }: {
  block: Of<"image">;
  lessonId: string;
  upload: (file: File) => Promise<number | null>;
  onChange: (changes: Partial<Of<"image">>) => void;
}) {
  const [busy, setBusy] = useState(false);

  async function chosen(file: File | null) {
    if (!file) return;
    setBusy(true);
    const image_id = await upload(file);
    if (image_id !== null) onChange({ image_id });
    setBusy(false);
  }

  if (block.image_id === null) {
    return (
      <FileDrop
        accept="image/png,image/jpeg,image/gif,image/webp" what="a picture" busy={busy} focusId={block.id} onFile={chosen}
        hint="PNG, JPEG, GIF or WebP, up to 5 MB. Pasting a picture anywhere in the lesson works too."
      />
    );
  }
  return (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element -- served by the backend, to logged-in readers only */}
      <img className="picture" src={`/api/lessons/${lessonId}/images/${block.image_id}`} alt={block.alt} />
      <p className="row">
        <input
          className="grow" data-focus={block.id} value={block.alt} maxLength={300} aria-label="Description of the picture"
          placeholder="Describe the picture, for readers who cannot see it" onChange={(e) => onChange({ alt: e.target.value })}
        />
        <button className="secondary" onClick={() => onChange({ image_id: null })}>Change picture</button>
      </p>
    </>
  );
}

function VideoEditor({ block, onChange }: { block: Of<"video">; onChange: (changes: Partial<Of<"video">>) => void }) {
  const id = youtubeId(block.url);
  return (
    <>
      <input
        className="grow" data-focus={block.id} value={block.url} maxLength={300} placeholder="Paste a YouTube link" aria-label="YouTube link"
        onChange={(e) => onChange({ url: e.target.value })}
      />
      {block.url.trim() !== "" && !id && <p className="error">This is not a link to a YouTube video.</p>}
      {id && (
        <div className="video">
          <iframe
            src={`https://www.youtube-nocookie.com/embed/${id}`} title="Video" loading="lazy" allow="fullscreen; picture-in-picture; encrypted-media"
            sandbox="allow-scripts allow-same-origin allow-presentation allow-popups" referrerPolicy="strict-origin-when-cross-origin"
          />
        </div>
      )}
    </>
  );
}

const EXAMPLE = `## Why HTTPS matters
HTTPS wraps HTTP in **TLS**, so nobody on the network can read or change the traffic.

> [!TIP] Look for the padlock in the address bar.

\`\`\` python
import ssl
print(ssl.OPENSSL_VERSION)
\`\`\`

?? Which port does HTTPS use unless told otherwise?
- [ ] 80
- [x] 443
- [ ] 22
> Port 443. Port 80 is plain HTTP.

?? What does TLS stand for?
= Transport Layer Security
> It replaced SSL.
`;

// A whole lesson written or pasted as text, turned into blocks (the format is in lib/lessons.ts).
function ImportText({ onImport }: { onImport: (blocks: Block[]) => void }) {
  const [text, setText] = useState("");
  const [told, setTold] = useState("");

  function add() {
    const made = importText(text);
    if (made.length === 0) return;
    onImport(made);
    setText("");
    setTold(`Added ${made.length === 1 ? "1 block" : `${made.length} blocks`} at the end of the lesson.`);
  }

  return (
    <details className="import">
      <summary>Write or paste a whole lesson as text</summary>
      <p className="muted">
        The fastest way to start: write the lesson in one go, here or anywhere else, and turn it into blocks.
        Text is Markdown, and each heading starts a new text block. <code>?? </code> starts a question, followed by
        its options (<code>- [ ]</code> wrong, <code>- [x]</code> correct) or its accepted answers (<code>= answer</code>),
        and <code>&gt; </code> its explanation. <code>```</code> starts and ends code, and <code>&gt; [!NOTE]</code>,{" "}
        <code>[!TIP]</code> or <code>[!WARNING]</code> a callout.
      </p>
      <textarea
        className="mono" rows={14} value={text} spellCheck={false} aria-label="Lesson as text" placeholder={EXAMPLE}
        onChange={(e) => { setText(e.target.value); setTold(""); }}
      />
      <p className="row">
        <button className="secondary" disabled={text.trim() === ""} onClick={add}>Add as blocks</button>
        <button className="secondary" onClick={() => setText(EXAMPLE)}>Show an example</button>
        {told && <span className="muted" role="status">{told}</span>}
      </p>
    </details>
  );
}
