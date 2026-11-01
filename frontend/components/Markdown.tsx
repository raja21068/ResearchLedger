import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Raw HTML in model output or workspace files is not rendered (react-markdown default).
export function Markdown({ text }: { text: string }) {
  return (
    <div className="prose-rl">
      <ReactMarkdown remarkPlugins={[remarkGfm]}
        components={{ a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer noopener">{children}</a> }}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
