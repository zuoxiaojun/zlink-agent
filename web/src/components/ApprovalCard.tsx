import { IconAlertTriangle, IconCircleCheck, IconCircleX } from "@tabler/icons-react";
import type { ApprovalState } from "../types";

interface ApprovalCardProps {
  approval: ApprovalState;
  onApprove: () => void;
  onDeny: () => void;
}

export default function ApprovalCard({ approval, onApprove, onDeny }: ApprovalCardProps) {
  if (approval.resolved) return null;

  return (
    <div className="approval-card">
      <div className="approval-card-header">
        <IconAlertTriangle size={16} />
        <span>需要你的确认</span>
      </div>
      <div className="approval-card-body">
        <div className="approval-card-detail">
          <span className="approval-card-label">工具:</span>
          <code>{approval.tool_name}</code>
        </div>
        <div className="approval-card-detail">
          <span className="approval-card-label">操作:</span>
          <span>{approval.reason}</span>
        </div>
      </div>
      <div className="approval-card-actions">
        <button className="btn btn-primary" onClick={onApprove}>
          <IconCircleCheck size={14} /> 批准
        </button>
        <button className="btn btn-secondary" onClick={onDeny}>
          <IconCircleX size={14} /> 拒绝
        </button>
      </div>
    </div>
  );
}
