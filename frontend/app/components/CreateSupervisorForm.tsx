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
    <form onSubmit={handleSubmit} className="space-y-3 border rounded-md bg-white p-4">
      <div>
        <label className="block text-sm font-medium mb-1">Name</label>
        <input
          className="w-full border rounded px-3 py-2 text-sm"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Description</label>
        <textarea
          className="w-full border rounded px-3 py-2 text-sm"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
        />
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Extra Instructions (one per line)</label>
        <textarea
          className="w-full border rounded px-3 py-2 text-sm"
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          rows={3}
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={isSubmitting}
        className="bg-gray-900 text-white text-sm px-4 py-2 rounded disabled:opacity-50"
      >
        {isSubmitting ? "Creating..." : "Create Supervisor Config"}
      </button>
    </form>
  );
}
