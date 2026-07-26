import Link from "next/link";
import { listRuns, listSupervisorConfigs } from "@/lib/api";
import CreateRunForm from "@/app/components/CreateRunForm";
import BentoCard from "@/app/components/BentoCard";
import StatusPill from "@/app/components/StatusPill";
import { PackageIcon } from "@/app/components/icons";

export default async function RunsPage() {
  const [runs, configs] = await Promise.all([listRuns(), listSupervisorConfigs()]);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold text-on-surface">Runs</h1>

      <BentoCard title="Active & Completed Runs">
        <ul className="flex flex-col divide-y divide-outline-variant">
          {runs.map((run) => (
            <li key={run.run_id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
              <div className="flex items-center gap-3">
                <PackageIcon className="w-4 h-4 text-secondary" />
                <div>
                  <Link href={`/runs/${run.run_id}`} className="text-sm font-medium text-on-surface hover:underline">
                    {run.order_id}
                  </Link>
                  <p className="text-xs font-mono text-on-surface-variant">{run.run_id}</p>
                </div>
              </div>
              <StatusPill status={run.status} />
            </li>
          ))}
          {runs.length === 0 && <p className="text-sm text-on-surface-variant py-2">No runs yet.</p>}
        </ul>
      </BentoCard>

      <BentoCard title="Start New Run">
        <CreateRunForm supervisorConfigs={configs} />
      </BentoCard>
    </div>
  );
}
