import { statusLabel, statusTone } from "../lib/format";

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`status-badge status-badge--${statusTone(status)}`}>
      <span />
      {statusLabel(status)}
    </span>
  );
}
