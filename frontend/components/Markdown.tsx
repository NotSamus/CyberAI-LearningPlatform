import { useMemo } from "react";
import ReactMarkdown, { type Components, type ExtraProps } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import { ALIASES, LANGUAGES } from "@/lib/highlight";
import { topicId } from "@/lib/lessons";

type HeadingProps = React.HTMLAttributes<HTMLHeadingElement> & ExtraProps;

// Colours for code in the text: only for a language that is written, never guessed.
const HIGHLIGHT: React.ComponentProps<typeof ReactMarkdown>["rehypePlugins"] = [[rehypeHighlight, { languages: LANGUAGES, aliases: ALIASES, detect: false }]];

// Links open in a new tab. With `anchors` (the id of a lesson's text block), headings get the id
// that `outline` in lib/lessons.ts gives the same heading: the block, and the line it is written on.
function parts(anchors?: string): Components {
  const heading = (Tag: "h1" | "h2" | "h3") =>
    function Heading({ node, children }: HeadingProps) {
      const line = node?.position?.start.line;
      return <Tag id={anchors && line ? topicId(anchors, line) : undefined}>{children}</Tag>;
    };
  return {
    a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
    ...(anchors ? { h1: heading("h1"), h2: heading("h2"), h3: heading("h3") } : {}),
  };
}

// Markdown as teachers write it in lessons (the same as in a notebook's text cells, with tables).
// HTML written in it is never run, and pictures from other sites are not loaded: a lesson's
// pictures are its picture blocks. Code between ``` lines is coloured when its language is
// written after the first ``` (```python), as code blocks are (lib/highlight.ts).
export default function Markdown({ text, anchors }: { text: string; anchors?: string }) {
  const components = useMemo(() => parts(anchors), [anchors]);
  return (
    <div className="markdown" id={anchors ? `text-${anchors}` : undefined}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={HIGHLIGHT} skipHtml disallowedElements={["img"]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
