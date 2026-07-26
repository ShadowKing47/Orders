import { getRun } from "@/lib/api";
import ControlPanel from "@/app/components/ControlPanel";
import EventInjector from "@/app/components/EventInjector";
import InstructionAdder from "@/app/components/InstructionAdder";

export default async function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const run = await getRun(id);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold">{run.order_id}</h1>
        <p className="text-xs text-gray-500">{run.run_id}</p>
      </div>

      <ControlPanel runId={run.run_id} status={run.status} />

      <div className="border rounded-md bg-white p-4">
        <h2 className="text-sm font-semibold mb-2">Status</h2>
        <dl className="text-sm grid grid-cols-2 gap-y-1">
          <dt className="text-gray-500">Status</dt>
          <dd>{run.status}</dd>
          <dt className="text-gray-500">Next wake up</dt>
          <dd>{run.next_wake_up_at ? new Date(run.next_wake_up_at).toLocaleString() : "—"}</dd>
          <dt className="text-gray-500">Created</dt>
          <dd>{new Date(run.created_at).toLocaleString()}</dd>
        </dl>
      </div>

      <div className="border rounded-md bg-white p-4">
        <h2 className="text-sm font-semibold mb-2">Memory Summary</h2>
        <p className="text-sm whitespace-pre-wrap">{run.memory_summary || "(empty)"}</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <EventInjector runId={run.run_id} />
        <InstructionAdder runId={run.run_id} />
      </div>
    </div>
  );
}
