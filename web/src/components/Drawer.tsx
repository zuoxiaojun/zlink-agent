import { useEffect } from "react";
import type { ReactNode } from "react";
import { IconX } from "@tabler/icons-react";

interface DrawerProps {
  open: boolean;
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  width?: number;
}

/** 右侧滑出抽屉：遮罩点击 / Esc 关闭。 */
export default function Drawer({ open, title, onClose, children, width = 520 }: DrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div
        className="drawer"
        style={{ width, maxWidth: "92vw" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="drawer-header">
          <div className="drawer-title">{title}</div>
          <button className="btn btn-ghost icon-btn-sm" onClick={onClose} title="关闭">
            <IconX size={16} />
          </button>
        </div>
        <div className="drawer-body">{children}</div>
      </div>
    </div>
  );
}
