"use client";
import Link from "next/link";
import { useState } from "react";
import { ArrowRight, CircleCheck, CircleSlash, CircleX, Info, Lightbulb, NotebookPen, RotateCcw, TriangleAlert } from "lucide-react";
import Chip from "@/components/Chip";
import CodeBlock from "@/components/learn/CodeBlock";
import Markdown from "@/components/Markdown";
import { api } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";
import type { CheckState, ViewBlock } from "@/lib/lessons";

type Choice = Extract<ViewBlock, { type: "multiple_choice" }>;
type Written = Extract<ViewBlock, { type: "short_answer" }>;
type Answered = (blockId: string, state: CheckState) => void;

const TONES = { note: { label: "Note", icon: Info }, tip: { label: "Tip", icon: Lightbulb }, warning: { label: "Warning", icon: TriangleAlert } };

// Where each knowledge check is on the page: "go to it" at the end of the lesson scrolls there.
export function checkAnchor(blockId: string): string {
  return `check-${blockId}`;
}

// A lesson as its readers see it. Knowledge checks are sent to the server to be checked: this page
// never has the right answers before the server gives them.
export default function LessonBlocks({ lessonId, blocks, onAnswered }: { lessonId: number; blocks: ViewBlock[]; onAnswered: Answered }) {
  return (
    <div className="lesson-blocks">
      {blocks.map((block) => {
        switch (block.type) {
          case "text":
            return <Markdown key={block.id} text={block.text} anchors={block.id} />;
          case "code":
            return <CodeBlock key={block.id} language={block.language} code={block.code} />;
          case "callout": {
            const { label, icon: Icon } = TONES[block.tone];
            return (
              <aside key={block.id} className={`callout ${block.tone}`}>
                <p className="callout-label"><Icon aria-hidden />{label}</p>
                <Markdown text={block.text} />
              </aside>
            );
          }
          case "image":
            // eslint-disable-next-line @next/next/no-img-element -- served by the backend, to logged-in readers only
            return <img key={block.id} className="picture" src={block.url} alt={block.alt} loading="lazy" />;
          case "video":
            return (
              <div key={block.id} className="video">
                <iframe
                  src={`https://www.youtube-nocookie.com/embed/${block.video_id}`}
                  title="Video"
                  loading="lazy"
                  allow="fullscreen; picture-in-picture; encrypted-media"
                  sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"
                  referrerPolicy="strict-origin-when-cross-origin"
                />
              </div>
            );
          case "assignment":
            return (
              <Link key={block.id} href={`/assignments/${block.assignment_id}`} className="card practice">
                <span className="tile"><NotebookPen aria-hidden /></span>
                <span className="grow">
                  <span className="check-label">Notebook assignment</span>
                  <strong>{block.title}</strong>
                </span>
                <span className="go">Open the notebook <ArrowRight aria-hidden /></span>
              </Link>
            );
          case "multiple_choice":
            return <ChoiceCheck key={block.id} lessonId={lessonId} block={block} onAnswered={onAnswered} />;
          case "short_answer":
            return <WrittenCheck key={block.id} lessonId={lessonId} block={block} onAnswered={onAnswered} />;
        }
      })}
    </div>
  );
}

// Sends one answer to be checked and hands the new state of the question to the page.
function useCheck(lessonId: number, blockId: string, onAnswered: Answered) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function check(given: { choices: string[] } | { text: string }) {
    setBusy(true);
    setError("");
    try {
      const state = await api<CheckState>(`/lessons/${lessonId}/answers`, {
        method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ block_id: blockId, ...given }),
      });
      onAnswered(blockId, state);
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
  }

  return { busy, error, check };
}

function tone(state: CheckState | null): string {
  return state?.closed ? (state.correct ? "right" : "wrong") : "";
}

// The top line of a check: what it is, and where the reader stands with it (the try they are on,
// or how it ended). The server says how many tries there are: the tries used and the tries left.
function CheckHead({ state, multiple }: { state: CheckState | null; multiple?: boolean }) {
  const tries = state ? state.attempts + state.tries_left : 0;
  return (
    <div className="quiz-head">
      <p className="check-label">Knowledge check{multiple && ": choose every answer that applies"}</p>
      {state?.closed ? (
        state.correct
          ? <Chip tone="good" icon={CircleCheck}>Right</Chip>
          : <Chip tone="neutral" icon={CircleSlash}>Out of tries</Chip>
      ) : state && state.attempts > 0 && (
        <span className="tries">Try {state.attempts + 1} of {tries}</span>
      )}
    </div>
  );
}

// What came of the last answer: a band under the question, in the tone of how it went. A wrong
// answer with tries left is yellow (it is not an error: try again), the end green or grey.
function Outcome({ state, error, solution }: { state: CheckState | null; error: string; solution?: string }) {
  if (error) return <p className="error" role="alert">{error}</p>;
  if (!state) return null;
  if (!state.closed) {
    return (
      <p className="outcome again" role="status">
        <RotateCcw aria-hidden />
        <span><strong>Not quite.</strong> Try again: {state.tries_left === 1 ? "one try left" : `${state.tries_left} tries left`}.</span>
      </p>
    );
  }
  const Icon = state.correct ? CircleCheck : Info;
  return (
    <div className={`outcome ${state.correct ? "right" : "shown"}`} role="status">
      <Icon aria-hidden />
      <div>
        <p>
          <strong>{state.correct ? (state.attempts === 1 ? "Correct, at the first try." : "Correct.") : "That was the last try."}</strong>
          {!state.correct && solution && <> The answer is: <strong className="answer">{solution}</strong></>}
          {!state.correct && !solution && " The right answer is marked above."}
        </p>
        {state.explanation && <Markdown text={state.explanation} />}
      </div>
    </div>
  );
}

const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

function ChoiceCheck({ lessonId, block, onAnswered }: { lessonId: number; block: Choice; onAnswered: Answered }) {
  const { state } = block;
  const [chosen, setChosen] = useState<string[]>(state?.choices ?? []);
  const { busy, error, check } = useCheck(lessonId, block.id, onAnswered);
  const closed = state?.closed ?? false;
  const solution = closed && Array.isArray(state?.solution) ? state.solution : [];

  function pick(id: string) {
    if (!block.multiple) setChosen([id]);
    else setChosen((ids) => (ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]));
  }

  return (
    <section id={checkAnchor(block.id)} tabIndex={-1} className={`quiz ${tone(state)}`} aria-label="Knowledge check">
      <CheckHead state={state} multiple={block.multiple} />
      <Markdown text={block.question} />
      <div className="options">
        {block.options.map((option, n) => {
          const picked = chosen.includes(option.id);
          const mark = solution.includes(option.id) ? "correct" : closed && picked ? "incorrect" : "";
          return (
            <label key={option.id} className={`option ${mark}`}>
              <input
                type={block.multiple ? "checkbox" : "radio"} name={block.id} checked={picked}
                disabled={closed || busy} onChange={() => pick(option.id)}
              />
              <span className="letter" aria-hidden>{LETTERS[n] ?? ""}</span>
              <Markdown text={option.text} />
              {mark === "correct" && <span className="verdict good"><CircleCheck aria-hidden />{picked ? "Your answer, right" : "Right answer"}</span>}
              {mark === "incorrect" && <span className="verdict bad"><CircleX aria-hidden />Your answer</span>}
            </label>
          );
        })}
      </div>
      {!closed && (
        <button onClick={() => check({ choices: chosen })} disabled={busy || chosen.length === 0}>
          {busy ? "Checking…" : "Check"}
        </button>
      )}
      <Outcome state={state} error={error} />
    </section>
  );
}

function WrittenCheck({ lessonId, block, onAnswered }: { lessonId: number; block: Written; onAnswered: Answered }) {
  const { state } = block;
  const [text, setText] = useState(state?.text ?? "");
  const { busy, error, check } = useCheck(lessonId, block.id, onAnswered);
  const closed = state?.closed ?? false;

  return (
    <section id={checkAnchor(block.id)} tabIndex={-1} className={`quiz ${tone(state)}`} aria-label="Knowledge check">
      <CheckHead state={state} />
      <Markdown text={block.question} />
      <form className="written" onSubmit={(e) => { e.preventDefault(); check({ text }); }}>
        <input
          className={closed ? (state?.correct ? "correct" : "incorrect") : ""}
          value={text} maxLength={200} disabled={closed || busy} placeholder="Your answer"
          aria-label="Your answer" onChange={(e) => setText(e.target.value)}
        />
        {!closed && <button type="submit" disabled={busy || text.trim() === ""}>{busy ? "Checking…" : "Check"}</button>}
      </form>
      <Outcome state={state} error={error} solution={typeof state?.solution === "string" ? state.solution : undefined} />
    </section>
  );
}
