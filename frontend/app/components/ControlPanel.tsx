"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { getRunFinalOutput, interruptRun, resumeRun, terminateRun, type RunStatus } from "@/lib/api";

const FINAL_OUTPUT_POLL_INTERVAL_MS = 2000;
const FINAL_OUTPUT_POLL_TIMEOUT_MS = 60000;

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default function ControlPanel({ runId, status }: { runId: string; status: RunStatus }) {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAwaitingSummary, setIsAwaitingSummary] = useState(false);

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

  async function handleTerminate() {
    setIsSubmitting(true);
    try {
      await terminateRun(runId);
      router.refresh();
      setIsAwaitingSummary(true);
      const deadline = Date.now() + FINAL_OUTPUT_POLL_TIMEOUT_MS;
      while (Date.now() < deadline) {
        await sleep(FINAL_OUTPUT_POLL_INTERVAL_MS);
        const finalOutput = await getRunFinalOutput(runId);
        if (finalOutput) {
          router.refresh();
          break;
        }
      }
    } finally {
      setIsSubmitting(false);
      setIsAwaitingSummary(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <p className="text-xs text-on-surface-variant">Emergency state management controls</p>
      <div className="flex items-center gap-3">
        <button
          onClick={() => handle(() => interruptRun(runId))}
          disabled={isSubmitting || isTerminal || status === "PAUSED"}
          className="px-5 py-2 border border-outline-variant text-secondary rounded text-[11px] font-bold uppercase tracking-wide hover:bg-surface-container transition-colors disabled:opacity-40"
        >
          Pause
        </button>
        <button
          onClick={() => handle(() => resumeRun(runId))}
          disabled={isSubmitting || isTerminal || status !== "PAUSED"}
          className="px-5 py-2 border border-outline-variant text-secondary rounded text-[11px] font-bold uppercase tracking-wide hover:bg-surface-container transition-colors disabled:opacity-40"
        >
          Resume
        </button>
        <button
          onClick={handleTerminate}
          disabled={isSubmitting || isTerminal}
          className="px-5 py-2 border border-error bg-error-container text-error rounded text-[11px] font-bold uppercase tracking-wide hover:bg-error hover:text-white transition-all disabled:opacity-40"
        >
          Terminate
        </button>
      </div>
      {isAwaitingSummary && (
        <p className="text-[11px] text-on-surface-variant w-full">Generating final summary…</p>
      )}
    </div>
  );
}
