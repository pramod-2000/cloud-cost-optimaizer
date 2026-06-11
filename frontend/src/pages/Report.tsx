import { useLocation, useNavigate } from 'react-router-dom';

type Issue = {
  title: string;
  severity: 'high' | 'medium' | 'low';
  resource: string;
  finding: string;
  estimated_monthly_savings: string;
  recommendation: string;
  fix_commands: string[];
};

type ReportData = {
  scan?: { resource_count?: number };
  analysis?: {
    summary?: string;
    estimated_monthly_savings?: string;
    issues?: Issue[];
  };
};

function badgeColor(severity: string) {
  if (severity === 'high') return 'bg-red-500/15 text-red-200 ring-red-400/30';
  if (severity === 'medium') return 'bg-amber-500/15 text-amber-200 ring-amber-400/30';
  return 'bg-emerald-500/15 text-emerald-200 ring-emerald-400/30';
}

function issueType(issue: Issue) {
  const text = `${issue.title} ${issue.finding}`.toLowerCase();
  if (text.includes('over-provision') || text.includes('oversized') || text.includes('rightsizing')) return 'over-provisioned';
  if (text.includes('unused') || text.includes('idle') || text.includes('orphan')) return 'unused';
  if (text.includes('misconfig') || text.includes('pricing') || text.includes('on-demand')) return 'misconfigured';
  return 'optimization';
}

export default function Report() {
  const location = useLocation();
  const navigate = useNavigate();
  const report: ReportData | undefined = location.state?.analysis ? location.state : location.state?.analysis_result;
  const analysis = report?.analysis;
  const issues = analysis?.issues || [];
  const resourcesScanned = report?.scan?.resource_count ?? location.state?.resources_scanned ?? 0;

  if (!analysis) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-8">
        <p className="text-slate-300">No report selected.</p>
        <button onClick={() => navigate('/history')} className="mt-4 rounded-xl bg-cyan-400 px-4 py-2 font-semibold text-slate-950">Open history</button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-8">
        <p className="text-sm font-medium uppercase tracking-[0.25em] text-cyan-300">Analysis Report</p>
        <h1 className="mt-3 text-3xl font-bold text-white">Cloud cost findings</h1>
        <p className="mt-4 text-slate-300">{analysis.summary}</p>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
            <p className="text-sm text-slate-400">Resources scanned</p>
            <p className="mt-2 text-2xl font-bold text-white">{resourcesScanned}</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
            <p className="text-sm text-slate-400">Issues found</p>
            <p className="mt-2 text-2xl font-bold text-white">{issues.length}</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
            <p className="text-sm text-slate-400">Estimated savings</p>
            <p className="mt-2 text-2xl font-bold text-cyan-200">{analysis.estimated_monthly_savings || 'unknown'}</p>
          </div>
        </div>
      </section>

      <section className="space-y-4">
        {issues.map((issue: Issue, index: number) => (
          <article key={`${issue.title}-${index}`} className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">{issueType(issue)}</p>
                <h2 className="mt-2 text-xl font-semibold text-white">{issue.title}</h2>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase ring-1 ${badgeColor(issue.severity)}`}>{issue.severity}</span>
            </div>
            <p className="mt-3 text-sm text-slate-500 break-all">{issue.resource || 'Resource not specified'}</p>
            <p className="mt-4 text-slate-300">{issue.finding}</p>
            <p className="mt-3 text-slate-300"><span className="font-semibold text-white">Recommendation:</span> {issue.recommendation}</p>
            <p className="mt-2 text-sm text-cyan-200">Savings: {issue.estimated_monthly_savings}</p>
            {issue.fix_commands?.length > 0 && (
              <div className="mt-4 space-y-3">
                {issue.fix_commands.map((command) => (
                  <div key={command} className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                    <div className="mb-2 flex justify-end">
                      <button onClick={() => navigator.clipboard.writeText(command)} className="text-xs text-cyan-300 hover:text-cyan-200">Copy</button>
                    </div>
                    <code className="block whitespace-pre-wrap text-sm text-slate-200">{command}</code>
                  </div>
                ))}
              </div>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}
