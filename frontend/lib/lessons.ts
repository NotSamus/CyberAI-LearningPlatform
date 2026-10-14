import type { Student } from "@/lib/api";

// A lesson is a list of blocks. These are the blocks as teachers edit them; the server checks the
// same shapes (api/app/lessons.py) and never sends them to students.
export type Option = { id: string; text: string; correct: boolean };
export type Tone = "note" | "tip" | "warning";
export type Block =
  | { type: "text"; id: string; text: string }                                    // Markdown
  | { type: "code"; id: string; language: string; code: string }
  | { type: "callout"; id: string; tone: Tone; text: string }
  | { type: "image"; id: string; image_id: number | null; alt: string }
  | { type: "video"; id: string; url: string }                                    // a YouTube link
  | { type: "assignment"; id: string; assignment_id: number | null }              // a link to a notebook assignment
  | { type: "multiple_choice"; id: string; question: string; options: Option[]; explanation: string }
  | { type: "short_answer"; id: string; question: string; answers: string[]; explanation: string };

// Where the reader is with one knowledge check. The explanation and the right answer (`solution`:
// option ids, or the accepted answer) only arrive once it is closed: answered correctly, or out of tries.
export type CheckState = {
  attempts: number;
  tries_left: number;
  correct: boolean;
  closed: boolean;
  choices?: string[];
  text?: string;
  explanation?: string;
  solution?: string[] | string;
};

// The blocks as a reader gets them: nothing in them gives away an answer.
export type ViewBlock =
  | { type: "text"; id: string; text: string }
  | { type: "code"; id: string; language: string; code: string }
  | { type: "callout"; id: string; tone: Tone; text: string }
  | { type: "image"; id: string; url: string; alt: string }
  | { type: "video"; id: string; video_id: string }
  | { type: "assignment"; id: string; assignment_id: number; title: string }
  | { type: "multiple_choice"; id: string; question: string; options: { id: string; text: string }[]; multiple: boolean; state: CheckState | null }
  | { type: "short_answer"; id: string; question: string; state: CheckState | null };

// A knowledge check, as a reader gets it.
export type CheckBlock = Extract<ViewBlock, { type: "multiple_choice" | "short_answer" }>;

export function isCheck(block: ViewBlock): block is CheckBlock {
  return block.type === "multiple_choice" || block.type === "short_answer";
}

// About how many minutes the lesson's text takes to read, at some 200 words a minute (0: it has no text).
export function readingMinutes(blocks: ViewBlock[]): number {
  const words = blocks.reduce((sum, block) => sum + (block.type === "text" ? block.text.split(/\s+/).filter(Boolean).length : 0), 0);
  return words === 0 ? 0 : Math.max(1, Math.round(words / 200));
}

// How many of the knowledge checks the reader got right at the first try. Only from what the
// server said about each check: the page never knows the answers.
export function rightFirstTime(blocks: ViewBlock[]): number {
  return blocks.filter((block) => isCheck(block) && block.state?.correct && block.state.attempts === 1).length;
}

export type Lesson = {
  id: number;
  title: string;
  summary: string;
  published: boolean;         // false only for teachers looking at a draft
  course_id: number | null;
  course: string | null;
  questions: number;          // how many knowledge checks it has
};

// With the logged-in person's own progress.
export type MyLesson = Lesson & { opened_at: string | null; completed_at: string | null; answered: number };
export type LessonPage = MyLesson & {
  preview: boolean;           // a teacher trying out the working copy
  max_tries: number;
  blocks: ViewBlock[];
  next: { id: number; title: string } | null;
};

// What Teach > Lessons works with (teachers and admins only).
export type ManagedLesson = Lesson & {
  for_everyone: boolean;
  published_at: string | null;
  changed: boolean;           // edited since it was published: students still have the published version
  blocks_count: number;
};
export type LessonDraft = ManagedLesson & { blocks: Block[] };

type Tally = { answered: number; correct: number; first_try: number; missed: number };
export type LessonProgress = {
  lesson: ManagedLesson;
  questions: ({ id: string; question: string } & Tally)[];
  students: (Student & { opened_at: string | null; completed_at: string | null } & Tally)[];
};

export const MAX_OPTIONS = 8;
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;     // same as MAX_IMAGE_BYTES in api/app/lessons.py

// Ids for blocks and options. Not crypto.randomUUID: that one is missing when the site is opened
// over plain http at a network address (./dev.sh --lan).
export function newId(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(6)), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function option(text = "", correct = false): Option {
  return { id: newId(), text, correct };
}

// The blocks a teacher can add: the menu of the editor. `words` are what typing "/" looks through.
export type Kind = "text" | "multiple_choice" | "true_false" | "short_answer" | "code" | "callout" | "image" | "video" | "assignment";
export const BLOCK_MENU: { kind: Kind; label: string; words: string[]; make: () => Block }[] = [
  { kind: "text", label: "Text", words: ["text", "paragraph", "heading"], make: () => ({ type: "text", id: newId(), text: "" }) },
  {
    kind: "multiple_choice", label: "Multiple choice", words: ["multiple choice", "mc", "choice", "question", "quiz"],
    make: () => ({ type: "multiple_choice", id: newId(), question: "", options: [option(), option()], explanation: "" }),
  },
  {
    kind: "true_false", label: "True or false", words: ["true or false", "tf", "false"],
    make: () => ({ type: "multiple_choice", id: newId(), question: "", options: [option("True"), option("False")], explanation: "" }),
  },
  {
    kind: "short_answer", label: "Short answer", words: ["short answer", "answer", "fill"],
    make: () => ({ type: "short_answer", id: newId(), question: "", answers: [], explanation: "" }),
  },
  { kind: "code", label: "Code", words: ["code", "snippet"], make: () => ({ type: "code", id: newId(), language: "python", code: "" }) },
  { kind: "callout", label: "Callout", words: ["callout", "note", "tip", "warning"], make: () => ({ type: "callout", id: newId(), tone: "note", text: "" }) },
  { kind: "image", label: "Picture", words: ["picture", "image", "photo"], make: () => ({ type: "image", id: newId(), image_id: null, alt: "" }) },
  { kind: "video", label: "Video", words: ["video", "youtube"], make: () => ({ type: "video", id: newId(), url: "" }) },
  { kind: "assignment", label: "Notebook", words: ["notebook", "assignment", "lab"], make: () => ({ type: "assignment", id: newId(), assignment_id: null }) },
];

export const BLOCK_LABELS: Record<Block["type"], string> = {
  text: "Text", code: "Code", callout: "Callout", image: "Picture", video: "Video", assignment: "Notebook assignment",
  multiple_choice: "Multiple choice", short_answer: "Short answer",
};

// A copy of a block with ids of its own.
export function duplicate(block: Block): Block {
  if (block.type === "multiple_choice") {
    return { ...block, id: newId(), options: block.options.map((o) => ({ ...o, id: newId() })) };
  }
  return { ...block, id: newId() };
}

// A heading written in a lesson's text ("#", "##" or "###"): one line of the index beside the lesson.
// `id` is also the id of the heading on the page (components/Markdown.tsx gives it), and `block`
// the text block the heading is in.
export type Topic = { id: string; block: string; level: number; text: string };

export function topicId(block: string, line: number): string {
  return `topic-${block}-${line}`;
}

// The headings of a lesson, in order: lines of its text blocks that start with one to three "#".
// A "#" inside code (between ``` lines) is a comment, not a heading.
export function outline(blocks: (Block | ViewBlock)[]): Topic[] {
  const topics: Topic[] = [];
  for (const block of blocks) {
    if (block.type !== "text") continue;
    let inCode = false;
    block.text.split("\n").forEach((line, index) => {
      if (/^ {0,3}(```|~~~)/.test(line)) inCode = !inCode;
      const heading = inCode ? null : line.match(/^ {0,3}(#{1,3})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$/);
      if (!heading) return;
      // As it reads, without the marks for bold, code and links.
      const text = heading[2].replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/\*\*|__|\*|`|~~/g, "").trim();
      if (text) topics.push({ id: topicId(block.id, index + 1), block: block.id, level: heading[1].length, text });
    });
  }
  return topics;
}

// The same rule as `video_id` in api/app/lessons.py, to show the video while editing. What students
// get is decided by the server.
const YOUTUBE = /^https?:\/\/(?:www\.|m\.)?(?:youtube(?:-nocookie)?\.com\/(?:watch\?(?:[^#]*&)?v=|embed\/|shorts\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{11})(?:[?&#/].*)?$/;

export function youtubeId(url: string): string | null {
  return url.trim().match(YOUTUBE)?.[1] ?? null;
}

// Turns a lesson written as one piece of text into blocks, for the editor's "Paste a whole lesson".
//
//   Markdown text. A heading (#, ##, ...) starts a new text block.
//   ``` python          a code block, up to the closing ```
//   > [!TIP] ...        a callout: NOTE, TIP or WARNING
//   ?? A question       a knowledge check, up to the next empty line:
//   - [ ] an option       wrong
//   - [x] an option       correct (several may be)
//   = an answer           an accepted answer: makes it a short-answer question
//   > why                 the explanation
export function importText(source: string): Block[] {
  const blocks: Block[] = [];
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  let prose: string[] = [];
  const endProse = () => {
    const text = prose.join("\n").trim();
    if (text) blocks.push({ type: "text", id: newId(), text });
    prose = [];
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const fence = line.match(/^```\s*([\w+#.-]*)\s*$/);
    const question = line.match(/^\?\?\s*(.+)$/);
    const callout = line.match(/^>\s*\[!(NOTE|TIP|WARNING|IMPORTANT|CAUTION)\]\s*(.*)$/i);

    if (fence) {
      endProse();
      const code: string[] = [];
      for (i++; i < lines.length && !/^```\s*$/.test(lines[i]); i++) code.push(lines[i]);
      i++;    // the closing ```
      blocks.push({ type: "code", id: newId(), language: fence[1], code: code.join("\n") });
    } else if (question) {
      endProse();
      const asked = [question[1]], options: Option[] = [], answers: string[] = [], why: string[] = [];
      for (i++; i < lines.length && lines[i].trim() !== ""; i++) {
        const choice = lines[i].match(/^\s*[-*]\s*\[([ xX])\]\s*(.+)$/);
        const accepted = lines[i].match(/^\s*=\s*(.+)$/);
        const reason = lines[i].match(/^\s*>\s?(.*)$/);
        if (choice) options.push(option(choice[2].trim(), choice[1] !== " "));
        else if (accepted) answers.push(accepted[1].trim());
        else if (reason) why.push(reason[1]);
        else if (options.length === 0 && answers.length === 0) asked.push(lines[i]);     // the question goes on
        else break;
      }
      const shared = { id: newId(), question: asked.join("\n").trim(), explanation: why.join("\n").trim() };
      blocks.push(
        options.length === 0 && answers.length > 0
          ? { type: "short_answer", ...shared, answers }
          : { type: "multiple_choice", ...shared, options: options.slice(0, MAX_OPTIONS) },
      );
    } else if (callout) {
      endProse();
      const said = callout[2] ? [callout[2]] : [];
      for (i++; i < lines.length && lines[i].startsWith(">"); i++) said.push(lines[i].replace(/^>\s?/, ""));
      const kind = callout[1].toUpperCase();
      const tone: Tone = kind === "TIP" ? "tip" : kind === "WARNING" || kind === "CAUTION" ? "warning" : "note";
      blocks.push({ type: "callout", id: newId(), tone, text: said.join("\n").trim() });
    } else {
      if (/^#{1,6}\s/.test(line)) endProse();
      prose.push(line);
      i++;
    }
  }
  endProse();
  return blocks;
}
