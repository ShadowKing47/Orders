"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createSupervisorConfig } from "@/lib/api";

export default function CreateSupervisorForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await createSupervisorConfig({
        name,
        description,
        extra_instructions: instructions
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
      });
      router.refresh();
      setName("");
      setDescription("");
      setInstructions("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create supervisor config");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <label className="text-[10px] font-bold uppercase tracking-wide text-secondary">Name</label>
        <input
          className="w-full border border-outline-variant rounded p-2 text-sm bg-surface-container-low focus:ring-2 focus:ring-primary focus:border-primary"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-[10px] font-bold uppercase tracking-wide text-secondary">Description</label>
        <textarea
          className="w-full border border-outline-variant rounded p-2 text-sm bg-surface-container-low focus:ring-2 focus:ring-primary focus:border-primary resize-none"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-[10px] font-bold uppercase tracking-wide text-secondary">
          Extra Instructions (one per line)
        </label>
        <textarea
          className="w-full border border-outline-variant rounded p-2 font-mono text-[13px] bg-surface-container-low focus:ring-2 focus:ring-primary focus:border-primary resize-none"
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          rows={3}
        />
      </div>
      {error && <p className="text-xs text-error">{error}</p>}
      <button
        type="submit"
        disabled={isSubmitting}
        className="bg-primary text-on-primary text-[11px] font-bold uppercase tracking-wide px-4 py-3 rounded hover:opacity-90 active:scale-[0.98] transition-all disabled:opacity-50"
      >
        {isSubmitting ? "Creating..." : "Create Supervisor Config"}
      </button>
    </form>
  );
}
