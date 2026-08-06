import type { Message, ToolCall } from "../types";

interface ToolStepCardProps {
  call: ToolCall;
  result?: Message;
  onChoiceSelect?: (text: string) => void;
}

export default function ToolStepCard({ result, onChoiceSelect }: ToolStepCardProps) {
  const rawText = (() => {
    if (!result) return "";
    if (typeof result.content === "string") return result.content;
    if (Array.isArray(result.content)) {
      return result.content.map(p => p.type === "text" ? p.text || "" : "").join("\n");
    }
    return "";
  })();

  let clarifyParsed: { choices?: string[]; question?: string; data?: string } | null = null;
  if (rawText.trim()) {
    try {
      const candidate = JSON.parse(rawText) as { choices?: string[]; question?: string; data?: string };
      if (candidate && Array.isArray(candidate.choices)) clarifyParsed = candidate;
    } catch { /* ignore */ }
  }
  if (!clarifyParsed) return null;

  return (
    <div className="clarify-prompt">
      <p className="clarify-question">{clarifyParsed.question || clarifyParsed.data || ""}</p>
      {clarifyParsed.choices && clarifyParsed.choices.length > 0 && (
        <div className="clarify-choices">
          {clarifyParsed.choices.map((choice, i) => (
            <button key={i} className="clarify-chip" onClick={() => onChoiceSelect?.(choice)}>
              {choice}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
