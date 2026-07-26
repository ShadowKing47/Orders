"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { interruptRun, resumeRun, terminateRun, type RunStatus } from "@/lib/api";

export default function ControlPanel({ runId, status }: { runId: string; status: RunStatus }) {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isTerminal = status === "COMPLETED" || status === "TERMINATED";

  async function handle(action: () => Promise<unknown>) {
    setIsSubmitting(true);
    try {
      await action();
      router.refresh();
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="border rounded-md bg-white p-4 flex gap-3">
      <button
        onClick={() => handle(() => interruptRun(runId))}
        disabled={isSubmitting || isTerminal || status === "PAUSED"}
        className="text-sm px-3 py-1.5 rounded border disabled:opacity-40"
      >
        Pause
      </button>
      <button
        onClick={() => handle(() => resumeRun(runId))}
        disabled={isSubmitting || isTerminal || status !== "PAUSED"}
        className="text-sm px-3 py-1.5 rounded border disabled:opacity-40"
      >
        Resume
      </button>
      <button
        onClick={() => handle(() => terminateRun(runId))}
        disabled={isSubmitting || isTerminal}
        className="text-sm px-3 py-1.5 rounded border border-red-300 text-red-700 disabled:opacity-40"
      >
        Terminate
      </button>
    </div>
  );
}
