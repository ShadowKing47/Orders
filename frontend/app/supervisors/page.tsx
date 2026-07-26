import { listSupervisorConfigs } from "@/lib/api";
import CreateSupervisorForm from "@/app/components/CreateSupervisorForm";
import BentoCard from "@/app/components/BentoCard";
import { ShieldIcon } from "@/app/components/icons";

export default async function SupervisorsPage() {
  const configs = await listSupervisorConfigs();

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold text-on-surface">Supervisor Configs</h1>

      <BentoCard title="Configs">
        <ul className="flex flex-col divide-y divide-outline-variant">
          {configs.map((config) => (
            <li key={config.id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
              <ShieldIcon className="w-4 h-4 text-secondary mt-0.5" />
              <div>
                <p className="text-sm font-medium text-on-surface">{config.name}</p>
                <p className="text-xs text-on-surface-variant">{config.description}</p>
                {config.extra_instructions.length > 0 && (
                  <ul className="mt-2 text-xs text-on-surface-variant list-disc list-inside space-y-0.5">
                    {config.extra_instructions.map((instruction, idx) => (
                      <li key={idx}>{instruction}</li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          ))}
          {configs.length === 0 && <p className="text-sm text-on-surface-variant py-2">No supervisor configs yet.</p>}
        </ul>
      </BentoCard>

      <BentoCard title="Create Supervisor Config">
        <CreateSupervisorForm />
      </BentoCard>
    </div>
  );
}
