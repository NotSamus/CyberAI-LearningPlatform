import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Markdown as teachers write it in lessons (the same as in a notebook's text cells, with tables).
// HTML written in it is never run, and pictures from other sites are not loaded: a lesson's
// pictures are its picture blocks. Links open in a new tab.
export default function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        disallowedElements={["img"]}
        components={{
          a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
