import { memo } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";
import CodeBlock from "./CodeBlock";
import type { Message } from "../types";

const markdownComponents: Components = {
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  table: ({ children }) => (
    <div className="table-wrap">
      <table>{children}</table>
    </div>
  ),
};

export const Markdown = memo(function Markdown({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight]}
      components={markdownComponents}
    >
      {text}
    </ReactMarkdown>
  );
});

function MessageContent({ content }: { content: Message["content"] }) {
  if (typeof content === "string") {
    return <Markdown text={content} />;
  }
  if (Array.isArray(content)) {
    return content.map((part, i) =>
      part.type === "text" ? (
        <ReactMarkdown
          key={i}
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight]}
          components={markdownComponents}
        >
          {part.text || ""}
        </ReactMarkdown>
      ) : part.type === "image_url" ? (
        <img key={i} src={part.image_url?.url} alt="" />
      ) : null
    );
  }
  return <>{String(content)}</>;
}

export default memo(MessageContent);
