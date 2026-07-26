import ReactMarkdown from "react-markdown";

export default function MemorySummary({ text }: { text: string }) {
  return (
    <div className="bg-[#0d1c2d] rounded p-4 max-h-80 overflow-auto">
      {text ? (
        <div className="prose prose-sm prose-invert max-w-none font-mono text-[13px] prose-headings:text-[#94a3b8] prose-strong:text-white">
          <ReactMarkdown>{text}</ReactMarkdown>
        </div>
      ) : (
        <p className="font-mono text-[13px] text-[#64748b]">(no memory yet)</p>
      )}
    </div>
  );
}
