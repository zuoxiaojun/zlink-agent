import { useMemo } from "react";
import { Markdown } from "./MessageContent";
import { splitStreamingText } from "../utils/streamingSplit";

// 流式期间专用：已闭合块（memo 冻结，不重解析）+ 尾部实时块（每帧重解析）
// done 后 ChatMessage 的 isStreaming 变 false，本组件卸载，最终消息走 MessageContent 全量解析
export default function StreamingMarkdown({ text }: { text: string }) {
  const { closed, tail } = useMemo(() => splitStreamingText(text), [text]);
  return (
    <div className="streaming-split">
      <div className="streaming-closed">
        <Markdown text={closed} />
      </div>
      {tail !== "" && (
        <div className="streaming-tail">
          <Markdown text={tail} />
        </div>
      )}
    </div>
  );
}
