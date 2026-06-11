type ProgressTrackerProps = {
  messages: string[];
};

export default function ProgressTracker({ messages }: ProgressTrackerProps) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-cyan-950/10">
      <h2 className="mb-4 text-lg font-semibold text-white">Live progress</h2>
      {messages.length === 0 ? (
        <p className="text-sm text-slate-400">Progress updates will appear here after you start an analysis.</p>
      ) : (
        <ol className="space-y-3">
          {messages.map((message, index) => {
            const active = index === messages.length - 1;
            return (
              <li key={`${message}-${index}`} className="flex items-start gap-3 text-sm transition-all duration-300 ease-out animate-[fadeIn_0.25s_ease-out]">
                <span className={`mt-1 h-3 w-3 rounded-full ${active ? 'animate-pulse bg-cyan-300 shadow-lg shadow-cyan-300/60' : 'bg-emerald-400'}`} />
                <span className={active ? 'font-medium text-white' : 'text-slate-300'}>{message}</span>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
