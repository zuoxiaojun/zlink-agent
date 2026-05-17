import { Square } from "lucide-react";

export default function StopButton({ onStop }: { onStop: () => void }) {
  return (
    <div className="stop-bar">
      <button className="stop-btn" onClick={onStop}>
        <Square size={12} /> 停止生成
      </button>
    </div>
  );
}
