import { listSupervisorConfigs } from "@/lib/api";
import CreateSupervisorForm from "@/app/components/CreateSupervisorForm";

export default async function SupervisorsPage() {
  const configs = await listSupervisorConfigs();

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-xl font-semibold mb-4">Supervisor Configs</h1>
        <ul className="space-y-2">
          {configs.map((config) => (
            <li key={config.id} className="border rounded-md bg-white p-4">
              <p className="font-medium">{config.name}</p>
              <p className="text-sm text-gray-600">{config.description}</p>
              {config.extra_instructions.length > 0 && (
                <ul className="mt-2 text-sm text-gray-500 list-disc list-inside">
                  {config.extra_instructions.map((instruction, idx) => (
                    <li key={idx}>{instruction}</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
          {configs.length === 0 && <p className="text-sm text-gray-500">No supervisor configs yet.</p>}
        </ul>
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-4">Create Supervisor Config</h2>
        <CreateSupervisorForm />
      </div>
    </div>
  );
}
