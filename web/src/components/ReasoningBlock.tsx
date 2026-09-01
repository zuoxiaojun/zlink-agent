import { useState } from "react";
import { IconBrain, IconChevronDown, IconChevronRight } from "@tabler/icons-react";

/**
 * 思考过程折叠块。
 *
 * `defaultOpen` 只在挂载时读一次；需要从“展开”回到“收起”时（如流式结束），
 * 由调用方用 key 重挂载来重置，而不是用 effect 把 prop 同步进 state
 * （react-hooks/set-state-in-effect）。
 */
export default function ReasoningBlock({ text, defaultOpen = false }: { text: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);

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
