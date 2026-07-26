export default function BentoCard({
  title,
  icon,
  action,
  children,
  className = "",
}: {
  title: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`bg-surface-bright border border-outline-variant rounded overflow-hidden ${className}`}>
      <div className="px-4 py-3 border-b border-outline-variant flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="text-[11px] font-bold uppercase tracking-wide text-on-surface-variant">{title}</h2>
        </div>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}
