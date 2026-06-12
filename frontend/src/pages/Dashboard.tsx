import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { WS_BASE, apiFetch } from '../App';
import ProgressTracker from '../components/ProgressTracker';

export default function Dashboard() {
  const navigate = useNavigate();
  const [regions, setRegions] = useState<string[]>([]);
  const [region, setRegion] = useState('');
  const [messages, setMessages] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiFetch('/api/regions')
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Unable to load AWS regions');
        setRegions(data.regions || []);
        setRegion(data.regions?.[0] || '');
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load AWS regions.'));
  }, []);

  async function runAnalysis() {
    if (!region) return;
    const analysisId = crypto.randomUUID();
    let socket: WebSocket | undefined;

    setError('');
    setMessages([]);
    setLoading(true);

    try {
      socket = new WebSocket(`${WS_BASE}/ws/progress/${analysisId}`);
      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setMessages((current) => [...current, data.message]);
      };

      await new Promise((resolve) => {
        socket!.onopen = () => resolve(null);
        setTimeout(() => resolve(null), 500);
      });

      const response = await apiFetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ region, analysis_id: analysisId })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Analysis failed');
      navigate('/report', { state: data });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      socket?.close();
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_420px]">
      <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-8 shadow-xl shadow-cyan-950/10">
        <p className="text-sm font-medium uppercase tracking-[0.25em] text-cyan-300">Dashboard</p>
        <h1 className="mt-3 text-3xl font-bold text-white">Find AWS cost issues with AI</h1>
        <p className="mt-3 max-w-2xl text-slate-400">Select a region, scan tagged resources, and ask Gemini to identify cost optimization opportunities.</p>
        <div className="mt-8 space-y-4">
          <label className="block text-sm font-medium text-slate-300">AWS Region</label>
          <select className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 outline-none focus:border-cyan-400" value={region} onChange={(e) => setRegion(e.target.value)}>
            {regions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          {error && <p className="text-sm text-red-300">{error}</p>}
          <button onClick={runAnalysis} disabled={loading || !region} className="rounded-xl bg-cyan-400 px-5 py-3 font-semibold text-slate-950 disabled:opacity-60">
            {loading ? 'Running analysis...' : 'Run Analysis'}
          </button>
        </div>
      </section>
      <ProgressTracker messages={messages} />
    </div>
  );
}
