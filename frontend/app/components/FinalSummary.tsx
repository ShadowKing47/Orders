import ReactMarkdown from "react-markdown";
import { getRunFinalOutput } from "@/lib/api";
import BentoCard from "@/app/components/BentoCard";
import { ShieldIcon } from "@/app/components/icons";

export default async function FinalSummary({ runId }: { runId: string }) {
  const finalOutput = await getRunFinalOutput(runId);

  if (!finalOutput) {
    return null;
  }

  return (
    <BentoCard title="Final Summary" icon={<ShieldIcon className="w-4 h-4 text-secondary" />}>
      <div className="prose prose-sm max-w-none">
        <ReactMarkdown>{finalOutput.summary}</ReactMarkdown>
      </div>
      <p className="text-[10px] font-mono text-on-surface-variant mt-3">
        Generated {new Date(finalOutput.created_at).toLocaleString()}
      </p>
    </BentoCard>
  );
}
