import {
  conversationStatusMeta,
  ticketPriorityMeta,
  ticketStatusMeta,
} from "../lib/format";

function Badge({ label, tone }: { label: string; tone: string }) {
  return (
    <span className={`ops-badge ops-badge--${tone}`}>
      <span />
      {label}
    </span>
  );
}

export function ConversationStatusBadge({ status }: { status: string }) {
  const meta = conversationStatusMeta(status);
  return <Badge label={meta.label} tone={meta.tone} />;
}

export function TicketStatusBadge({ status }: { status: string }) {
  const meta = ticketStatusMeta(status);
  return <Badge label={meta.label} tone={meta.tone} />;
}

export function TicketPriorityBadge({ priority }: { priority: string }) {
  const meta = ticketPriorityMeta(priority);
  return <Badge label={meta.label} tone={meta.tone} />;
}
