"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { startRun, type SupervisorConfig } from "@/lib/api";

export default function CreateRunForm({ supervisorConfigs }: { supervisorConfigs: SupervisorConfig[] }) {
  const router = useRouter();
  const [configId, setConfigId] = useState(supervisorConfigs[0]?.id ?? "");
  const [orderId, setOrderId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const run = await startRun(configId, orderId);
      router.push(`/runs/${run.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (supervisorConfigs.length === 0) {
    return <p className="text-sm text-gray-500">Create a supervisor config first.</p>;
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border rounded-md bg-white p-4">
      <div>
        <label className="block text-sm font-medium mb-1">Supervisor Config</label>
        <select
          className="w-full border rounded px-3 py-2 text-sm"
          value={configId}
          onChange={(e) => setConfigId(e.target.value)}
        >
          {supervisorConfigs.map((config) => (
            <option key={config.id} value={config.id}>
              {config.name}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Order ID</label>
        <input
          className="w-full border rounded px-3 py-2 text-sm"
          value={orderId}
          onChange={(e) => setOrderId(e.target.value)}
          required
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={isSubmitting}
        className="bg-gray-900 text-white text-sm px-4 py-2 rounded disabled:opacity-50"
      >
        {isSubmitting ? "Starting..." : "Start Run"}
      </button>
    </form>
  );
}
