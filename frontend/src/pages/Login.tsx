import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { API_BASE, TOKEN_KEY } from '../App';

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Login failed');
      localStorage.setItem(TOKEN_KEY, data.token);
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-slate-800 bg-slate-900/80 p-8 shadow-2xl shadow-cyan-950/20">
      <h1 className="text-2xl font-bold text-white">Welcome back</h1>
      <p className="mt-2 text-sm text-slate-400">Sign in to review cloud cost analysis history.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <input className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 outline-none focus:border-cyan-400" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 outline-none focus:border-cyan-400" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <p className="text-sm text-red-300">{error}</p>}
        <button disabled={loading} className="w-full rounded-xl bg-cyan-400 px-4 py-3 font-semibold text-slate-950 disabled:opacity-60">
          {loading ? 'Signing in...' : 'Login'}
        </button>
      </form>
      <p className="mt-4 text-sm text-slate-400">No account? <Link className="text-cyan-300" to="/signup">Create one</Link></p>
    </div>
  );
}
