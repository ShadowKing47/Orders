import { listRunEvents } from "@/lib/api";
import { HistoryIcon } from "@/app/components/icons";

const EVENT_LABELS: Record<string, string> = {
  tool_executed: "Tool executed",
  memory_compacted: "Memory compacted",
  system_error: "System error",
  instruction_added: "Instruction added",
  order_event: "Order event",
};

function summarizePayload(payload: Record<string, unknown>): string {
  const entries = Object.entries(payload);
  if (entries.length === 0) return "";
  return entries
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(", ");
}

export default async function Timeline({ runId }: { runId: string }) {
  const events = await listRunEvents(runId);

  if (events.length === 0) {
    return (
      <div className="p-6 flex flex-col items-center justify-center border-dashed bg-surface-container-low border border-outline-variant rounded text-center">
        <HistoryIcon className="w-6 h-6 text-outline mb-2" />
        <p className="text-[10px] font-bold uppercase tracking-wide text-secondary mb-1">Event Timeline</p>
        <p className="text-[11px] text-on-surface-variant opacity-70">No recorded activity yet</p>
      </div>
    );
  }

  return (
    <ul className="flex flex-col divide-y divide-outline-variant max-h-72 overflow-auto">
      {events.map((event) => (
        <li key={event.id} className="py-2.5 first:pt-0 last:pb-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium text-on-surface">
              {EVENT_LABELS[event.event_type] ?? event.event_type}
            </span>
            <span className="text-[10px] font-mono text-on-surface-variant whitespace-nowrap">
              {new Date(event.created_at).toLocaleTimeString()}
            </span>
          </div>
          {summarizePayload(event.payload) && (
            <p className="text-[11px] font-mono text-on-surface-variant mt-0.5 truncate">
              {summarizePayload(event.payload)}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
