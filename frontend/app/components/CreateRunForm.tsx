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
    return <p className="text-sm text-on-surface-variant">Create a supervisor config first.</p>;
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <label className="text-[10px] font-bold uppercase tracking-wide text-secondary">Supervisor Config</label>
        <select
          className="w-full border border-outline-variant rounded p-2 text-sm bg-surface-container-low focus:ring-2 focus:ring-primary focus:border-primary"
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
      <div className="flex flex-col gap-1">
        <label className="text-[10px] font-bold uppercase tracking-wide text-secondary">Order ID</label>
        <input
          className="w-full border border-outline-variant rounded p-2 font-mono text-[13px] bg-surface-container-low focus:ring-2 focus:ring-primary focus:border-primary"
          value={orderId}
          onChange={(e) => setOrderId(e.target.value)}
          required
        />
      </div>
      {error && <p className="text-xs text-error">{error}</p>}
      <button
        type="submit"
        disabled={isSubmitting}
        className="bg-primary text-on-primary text-[11px] font-bold uppercase tracking-wide px-4 py-3 rounded hover:opacity-90 active:scale-[0.98] transition-all disabled:opacity-50"
      >
        {isSubmitting ? "Starting..." : "Start Run"}
      </button>
    </form>
  );
}
