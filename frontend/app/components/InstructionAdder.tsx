"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { addInstruction } from "@/lib/api";

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
    <form onSubmit={handleSubmit} className="space-y-2 border rounded-md bg-white p-4">
      <h2 className="text-sm font-semibold">Add Instruction</h2>
      <textarea
        className="w-full border rounded px-3 py-2 text-sm"
        placeholder="e.g. Always escalate refund requests over $500"
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        rows={3}
        required
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={isSubmitting}
        className="bg-gray-900 text-white text-sm px-4 py-2 rounded disabled:opacity-50"
      >
        {isSubmitting ? "Adding..." : "Add Instruction"}
      </button>
    </form>
  );
}
