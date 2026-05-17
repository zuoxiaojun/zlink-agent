import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function StreamingText({ text }: { text: string }) {
  if (!text) {
    return (
      <div className="msg-bubble">
        <div className="thinking-indicator">
          <span />
          <span />
          <span />
        </div>
      </div>
    );
  }
  return (
    <div className="msg-bubble" style={{ minWidth: "60px" }}>
      <div className="streaming-text">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
      </div>
    </div>
  );
}
