import { listRunEvents } from "@/lib/api";
import { HistoryIcon } from "@/app/components/icons";
import TimelineEntry from "@/app/components/TimelineEntry";

const EVENT_LABELS: Record<string, string> = {
  tool_executed: "Tool executed",
  memory_compacted: "Memory compacted",
  system_error: "System error",
  instruction_added: "Instruction added",
  order_event: "Order event",
};

function summarizePayload(eventType: string, payload: Record<string, unknown>): string {
  if (eventType === "tool_executed" && typeof payload.tool_name === "string") {
    return payload.tool_name;
  }
  if (eventType === "memory_compacted") {
    const text = payload.final_summary ?? payload.summary;
    if (typeof text === "string") return text;
  }

  const entries = Object.entries(payload);
  if (entries.length === 0) return "";
  return entries
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`)
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
        <TimelineEntry
          key={event.id}
          label={EVENT_LABELS[event.event_type] ?? event.event_type}
          time={new Date(event.created_at).toLocaleTimeString()}
          detail={summarizePayload(event.event_type, event.payload)}
        />
      ))}
    </ul>
  );
}
