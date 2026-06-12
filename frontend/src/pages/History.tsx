import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from '../App';

type AnalysisHistoryItem = {
  id: string;
  region: string;
  resources_scanned: number;
  issues_found: number;
  estimated_savings: string;
  analysis_result: unknown;
  created_at: string;
};

export default function History() {
  const navigate = useNavigate();
  const [items, setItems] = useState<AnalysisHistoryItem[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    apiFetch('/api/history')
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Unable to load history');
        setItems(data.analyses || []);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load history'));
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium uppercase tracking-[0.25em] text-cyan-300">History</p>
        <h1 className="mt-3 text-3xl font-bold text-white">Past analyses</h1>
      </div>
      {error && <p className="text-sm text-red-300">{error}</p>}
      <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/80">
        {items.length === 0 ? (
          <p className="p-6 text-slate-400">No analyses stored yet.</p>
        ) : (
          <div className="divide-y divide-slate-800">
            {items.map((item) => (
              <button key={item.id} onClick={() => navigate('/report', { state: item })} className="grid w-full gap-3 p-5 text-left hover:bg-slate-800/60 md:grid-cols-5">
                <span className="font-semibold text-white">{item.region}</span>
                <span className="text-slate-300">{new Date(item.created_at).toLocaleString()}</span>
                <span className="text-slate-300">{item.resources_scanned} resources</span>
                <span className="text-slate-300">{item.issues_found} issues</span>
                <span className="text-cyan-200">{item.estimated_savings}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
