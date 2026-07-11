import { useEffect, useRef } from "react";
import type { SlashCommandInfo } from "../types";

interface SlashCommandPopupProps {
  /** Filtered list of commands to display */
  commands: SlashCommandInfo[];
  /** Index of the currently highlighted item (for keyboard nav) */
  activeIndex: number;
  /** Called when a command is selected (via Enter click) */
  onSelect: (name: string) => void;
  /** Called when the popup should close */
  onClose: () => void;
  /** Called when mouse hovers over an item (syncs keyboard activeIndex) */
  onHover?: (index: number) => void;
}

export default function SlashCommandPopup({
  commands,
  activeIndex,
  onSelect,
  onClose,
  onHover,
}: SlashCommandPopupProps) {
  const popupRef = useRef<HTMLDivElement>(null);

  // Close when clicking outside the popup
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    // Use mousedown (fires before blur) to avoid race with item clicks
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [onClose]);

  // Scroll active item into view when it changes
  useEffect(() => {
    if (!popupRef.current) return;
    const activeEl = popupRef.current.querySelector(
      `.slash-popup-item:nth-child(${activeIndex + 1})`
    ) as HTMLElement | null;
    activeEl?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  if (commands.length === 0) {
    return (
      <div className="slash-popup" ref={popupRef}>
        <div className="slash-popup-empty">无匹配命令</div>
      </div>
    );
  }

  return (
    <div className="slash-popup" ref={popupRef}>
      {commands.map((cmd, i) => (
        <div
          key={cmd.name}
          className={`slash-popup-item${i === activeIndex ? " active" : ""}`}
          onClick={() => onSelect(cmd.name)}
          onMouseEnter={() => onHover?.(i)}
        >
          <span className="slash-popup-name">{cmd.usage}</span>
          <span className="slash-popup-desc">{cmd.description}</span>
        </div>
      ))}
    </div>
  );
}
