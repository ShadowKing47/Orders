"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { injectEvent } from "@/lib/api";
import BentoCard from "@/app/components/BentoCard";

type PayloadField = { key: string; value: string };

function buildPayload(fields: PayloadField[]): Record<string, string> {
  const payload: Record<string, string> = {};
  for (const { key, value } of fields) {
    const trimmedKey = key.trim();
    if (trimmedKey) payload[trimmedKey] = value;
  }
  return payload;
}

export default function EventInjector({ runId }: { runId: string }) {
  const router = useRouter();
  const [eventType, setEventType] = useState("");
  const [fields, setFields] = useState<PayloadField[]>([{ key: "", value: "" }]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateField(index: number, patch: Partial<PayloadField>) {
    setFields((prev) => prev.map((field, i) => (i === index ? { ...field, ...patch } : field)));
  }

  function addField() {
    setFields((prev) => [...prev, { key: "", value: "" }]);
  }

  function removeField(index: number) {
    setFields((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await injectEvent(runId, eventType, buildPayload(fields));
      setEventType("");
      setFields([{ key: "", value: "" }]);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to inject event");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <BentoCard title="Inject Event" className="flex flex-col">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-bold uppercase tracking-wide text-secondary">Event Type</label>
          <input
            className="w-full border border-outline-variant rounded p-2 font-mono text-[13px] bg-surface-container-low focus:ring-2 focus:ring-primary focus:border-primary transition-shadow"
            placeholder="e.g. payment_failed"
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            required
          />
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-[10px] font-bold uppercase tracking-wide text-secondary">Payload Details</label>
          {fields.map((field, index) => (
            <div key={index} className="flex gap-2">
              <input
                className="w-2/5 border border-outline-variant rounded p-2 text-[13px] bg-surface-container-low focus:ring-2 focus:ring-primary focus:border-primary"
                placeholder="field name"
                value={field.key}
                onChange={(e) => updateField(index, { key: e.target.value })}
              />
              <input
                className="flex-1 border border-outline-variant rounded p-2 text-[13px] bg-surface-container-low focus:ring-2 focus:ring-primary focus:border-primary"
                placeholder="value"
                value={field.value}
                onChange={(e) => updateField(index, { value: e.target.value })}
              />
              <button
                type="button"
                onClick={() => removeField(index)}
                disabled={fields.length === 1}
                className="px-2 text-on-surface-variant hover:text-error disabled:opacity-30 transition-colors"
                aria-label="Remove field"
              >
                &times;
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={addField}
            className="self-start text-[11px] font-bold uppercase tracking-wide text-secondary hover:text-on-surface transition-colors"
          >
            + Add field
          </button>
        </div>

        {error && <p className="text-xs text-error">{error}</p>}
        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full bg-surface-container text-on-surface text-[11px] font-bold uppercase tracking-wide py-3 border border-outline-variant rounded hover:bg-outline-variant/40 active:scale-[0.98] transition-all mt-auto disabled:opacity-50"
        >
          {isSubmitting ? "Sending..." : "Inject Event"}
        </button>
      </form>
    </BentoCard>
  );
}
