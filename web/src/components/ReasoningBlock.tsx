import { useState } from "react";
import { IconBrain, IconChevronDown, IconChevronRight } from "@tabler/icons-react";

export default function ReasoningBlock({ text }: { text: string }) {
  const [open, setOpen] = useState(false);

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
