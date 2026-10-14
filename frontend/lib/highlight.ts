import { toJsxRuntime } from "hast-util-to-jsx-runtime";
import { common, createLowlight } from "lowlight";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";

// Colours for code in lessons. highlight.js (through lowlight) only finds the parts of the code
// (keywords, strings, comments...) and marks each with a class such as `hljs-keyword`; the colours
// are in app/styles/learn.css, and each theme has its own (app/styles/themes.css). It hands back a
// tree that React draws, never HTML text, so nothing in a lesson's code can run in the page.

// The common languages: Python, Bash and shell sessions, JavaScript and TypeScript, SQL, JSON,
// C, C++, C#, Java, Go, Rust, HTML/XML, CSS, YAML, Markdown, diff and about twenty more.
export const LANGUAGES = common;

// Names teachers may write that highlight.js knows by another one
export const ALIASES = { python: ["python3", "py3"], bash: ["terminal"], plaintext: ["text", "txt", "output"] };

const lowlight = createLowlight(LANGUAGES);
lowlight.registerAlias(ALIASES);

// `code` in colour, as React nodes, when `language` is one highlight.js knows; otherwise as it is.
export function highlighted(language: string, code: string): React.ReactNode {
  const name = language.trim().toLowerCase();
  if (!name || !lowlight.registered(name)) return code;
  return toJsxRuntime(lowlight.highlight(name, code), { Fragment, jsx, jsxs });
}
