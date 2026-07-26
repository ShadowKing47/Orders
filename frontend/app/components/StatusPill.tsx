import type { RunStatus } from "@/lib/api";

const STATUS_STYLES: Record<RunStatus, string> = {
  RUNNING: "bg-secondary-container text-on-secondary-container",
  SLEEPING: "bg-surface-container text-on-surface-variant",
  COMPLETED: "bg-secondary-container text-on-secondary-container",
  TERMINATED: "bg-error-container text-error",
  PAUSED: "bg-surface-container text-secondary",
};

export default function StatusPill({ status }: { status: RunStatus }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase tracking-wide ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  );
}
