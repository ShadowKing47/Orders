"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { injectEvent } from "@/lib/api";

export default function EventInjector({ runId }: { runId: string }) {
  const router = useRouter();
  const [eventType, setEventType] = useState("");
  const [payload, setPayload] = useState("{}");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const parsedPayload = payload.trim() ? JSON.parse(payload) : {};
      await injectEvent(runId, eventType, parsedPayload);
      setEventType("");
      setPayload("{}");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to inject event");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2 border rounded-md bg-white p-4">
      <h2 className="text-sm font-semibold">Inject Event</h2>
      <input
        className="w-full border rounded px-3 py-2 text-sm"
        placeholder="event_type (e.g. payment_failed)"
        value={eventType}
        onChange={(e) => setEventType(e.target.value)}
        required
      />
      <textarea
        className="w-full border rounded px-3 py-2 text-sm font-mono"
        placeholder="payload JSON"
        value={payload}
        onChange={(e) => setPayload(e.target.value)}
        rows={3}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={isSubmitting}
        className="bg-gray-900 text-white text-sm px-4 py-2 rounded disabled:opacity-50"
      >
        {isSubmitting ? "Sending..." : "Send Event"}
      </button>
    </form>
  );
}
