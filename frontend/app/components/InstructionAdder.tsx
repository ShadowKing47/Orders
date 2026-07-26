"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { addInstruction } from "@/lib/api";
import BentoCard from "@/app/components/BentoCard";

export default function InstructionAdder({ runId }: { runId: string }) {
  const router = useRouter();
  const [instruction, setInstruction] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await addInstruction(runId, instruction);
      setInstruction("");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add instruction");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <BentoCard title="Add Instruction" className="flex flex-col">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3 flex-grow">
        <textarea
          className="w-full flex-grow border border-outline-variant rounded p-3 font-mono text-[13px] focus:ring-2 focus:ring-primary focus:border-primary transition-shadow resize-none bg-surface-container-low"
          placeholder="e.g. Always escalate refund requests over $500"
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          rows={5}
          required
        />
        {error && <p className="text-xs text-error">{error}</p>}
        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full bg-primary text-on-primary text-[11px] font-bold uppercase tracking-wide py-3 rounded hover:opacity-90 active:scale-[0.98] transition-all disabled:opacity-50"
        >
          {isSubmitting ? "Committing..." : "Commit Instruction"}
        </button>
      </form>
    </BentoCard>
  );
}
