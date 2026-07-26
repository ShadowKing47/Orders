import { getRun, getSupervisorConfig } from "@/lib/api";
import BentoCard from "@/app/components/BentoCard";
import StatusPill from "@/app/components/StatusPill";
import ControlPanel from "@/app/components/ControlPanel";
import EventInjector from "@/app/components/EventInjector";
import InstructionAdder from "@/app/components/InstructionAdder";
import MemorySummary from "@/app/components/MemorySummary";
import Timeline from "@/app/components/Timeline";
import FinalSummary from "@/app/components/FinalSummary";
import { MemoryIcon, ScheduleIcon, ShieldIcon } from "@/app/components/icons";

export default async function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const run = await getRun(id);
  const supervisorConfig = await getSupervisorConfig(run.supervisor_config_id);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold text-on-surface">Order #{run.order_id}</h1>
        <StatusPill status={run.status} />
      </div>
      <p className="text-xs font-mono text-on-surface-variant -mt-3">{run.run_id}</p>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-8 flex flex-col gap-6">
          {(run.status === "COMPLETED" || run.status === "TERMINATED") && <FinalSummary runId={run.run_id} />}

          <BentoCard title="Agent Memory" icon={<MemoryIcon className="w-4 h-4 text-secondary" />}>
            <MemorySummary text={run.memory_summary} />
          </BentoCard>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <InstructionAdder runId={run.run_id} />
            <EventInjector runId={run.run_id} />
          </div>

          <BentoCard title="Manual Overrides">
            <ControlPanel runId={run.run_id} status={run.status} />
          </BentoCard>
        </div>

        <div className="col-span-12 lg:col-span-4">
          <div className="flex flex-col gap-6 sticky top-24">
            <BentoCard title="Run Metadata">
              <div className="flex flex-col gap-5">
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="text-[10px] font-bold uppercase tracking-wide text-secondary mb-1">
                      Next Wake Up
                    </h4>
                    <p className="text-sm text-on-surface">
                      {run.next_wake_up_at ? new Date(run.next_wake_up_at).toLocaleString() : "—"}
                    </p>
                  </div>
                  <ScheduleIcon className="w-5 h-5 text-on-surface" />
                </div>
                <div className="flex justify-between items-start pt-4 border-t border-outline-variant">
                  <div>
                    <h4 className="text-[10px] font-bold uppercase tracking-wide text-secondary mb-1">
                      Supervisor Config
                    </h4>
                    <p className="text-sm text-on-surface">{supervisorConfig.name}</p>
                    <p className="text-xs font-mono text-on-surface-variant">{run.supervisor_config_id}</p>
                  </div>
                  <ShieldIcon className="w-5 h-5 text-secondary" />
                </div>
                <div className="pt-4 border-t border-outline-variant">
                  <h4 className="text-[10px] font-bold uppercase tracking-wide text-secondary mb-1">Created</h4>
                  <p className="text-sm text-on-surface">{new Date(run.created_at).toLocaleString()}</p>
                </div>
              </div>
            </BentoCard>

            <BentoCard title="Recent Timeline">
              <Timeline runId={run.run_id} />
            </BentoCard>
          </div>
        </div>
      </div>
    </div>
  );
}
