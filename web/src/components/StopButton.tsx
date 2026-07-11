import { IconSquare } from "@tabler/icons-react";

export default function StopButton({ onStop }: { onStop: () => void }) {
  return (
    <div className="stop-bar">
      <button className="stop-btn" onClick={onStop}>
        <IconSquare size={12} /> 停止生成
      </button>
    </div>
  );
}
