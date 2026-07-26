import Link from "next/link";
import { listRuns, listSupervisorConfigs } from "@/lib/api";
import CreateRunForm from "@/app/components/CreateRunForm";

const STATUS_COLORS: Record<string, string> = {
  RUNNING: "bg-blue-100 text-blue-800",
  SLEEPING: "bg-gray-100 text-gray-700",
  COMPLETED: "bg-green-100 text-green-800",
  TERMINATED: "bg-red-100 text-red-800",
  PAUSED: "bg-yellow-100 text-yellow-800",
};

export default async function RunsPage() {
  const [runs, configs] = await Promise.all([listRuns(), listSupervisorConfigs()]);

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-xl font-semibold mb-4">Runs</h1>
        <ul className="space-y-2">
          {runs.map((run) => (
            <li key={run.run_id} className="border rounded-md bg-white p-4 flex items-center justify-between">
              <div>
                <Link href={`/runs/${run.run_id}`} className="font-medium hover:underline">
                  {run.order_id}
                </Link>
                <p className="text-xs text-gray-500">{run.run_id}</p>
              </div>
              <span className={`text-xs px-2 py-1 rounded ${STATUS_COLORS[run.status] ?? ""}`}>{run.status}</span>
            </li>
          ))}
          {runs.length === 0 && <p className="text-sm text-gray-500">No runs yet.</p>}
        </ul>
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-4">Start New Run</h2>
        <CreateRunForm supervisorConfigs={configs} />
      </div>
    </div>
  );
}
