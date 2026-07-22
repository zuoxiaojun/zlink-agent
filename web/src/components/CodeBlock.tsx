import React, { useState } from "react";
import { IconCheck, IconCopy } from "@tabler/icons-react";

function extractText(node: React.ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (React.isValidElement(node)) {
    return extractText((node.props as { children?: React.ReactNode }).children);
  }
  return "";
}

export default function CodeBlock({ children }: { children?: React.ReactNode }) {
  const [copied, setCopied] = useState(false);
  let language = "";
  const child = React.Children.toArray(children)[0];
  if (React.isValidElement(child)) {
    const cls = (child.props as { className?: string }).className || "";
    const m = cls.match(/language-([\w-]+)/);
    if (m) language = m[1];
  }
  const raw = extractText(children).replace(/\n$/, "");

  // Auto-format JSON content for display
  let display = raw;
  if (language === "json" || raw.match(/^[{[]/)) {
    try {
      display = JSON.stringify(JSON.parse(raw), null, 2);
    } catch { /* keep raw */ }
  }

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(raw);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard 不可用时静默 */
    }
  };

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span className="code-block-lang">{language || "code"}</span>
        <button type="button" className="code-block-copy" onClick={onCopy}>
          {copied ? <IconCheck size={13} /> : <IconCopy size={13} />}
          {copied ? "已复制" : "复制"}
        </button>
      </div>
      <pre>{display !== raw ? display : children}</pre>
    </div>
  );
}
