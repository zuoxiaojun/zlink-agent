import { useState } from "react";
import { IconBrain, IconChevronDown, IconChevronRight } from "@tabler/icons-react";

export default function ReasoningBlock({ text, streaming }: { text: string; streaming?: boolean }) {
  const [open, setOpen] = useState(!!streaming);
  const [prevStreaming, setPrevStreaming] = useState(!!streaming);

  // React 推荐的 render 期状态调整：streaming 翻转时同步展开/收起，不用 effect
  if (streaming !== undefined && !!streaming !== prevStreaming) {
    setPrevStreaming(!!streaming);
    setOpen(!!streaming);
  }

  return (
    <div className="reasoning-block">
      <button type="button" className="reasoning-header" onClick={() => setOpen(!open)}>
        <IconBrain size={13} />
        <span>思考过程</span>
        {open ? <IconChevronDown size={13} /> : <IconChevronRight size={13} />}
      </button>
      {open && <div className="reasoning-content">{text}</div>}
    </div>
  );
}
