import { Link, useNavigate } from 'react-router-dom';
import { TOKEN_KEY, getToken } from '../App';

export default function Navbar() {
  const navigate = useNavigate();
  const isAuthed = Boolean(getToken());

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    navigate('/login');
  }

  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Link to="/" className="text-lg font-semibold tracking-tight text-cyan-300">
          AI Cloud Cost Detective
        </Link>
        <div className="flex items-center gap-4 text-sm text-slate-300">
          {isAuthed ? (
            <>
              <Link className="hover:text-white" to="/">Dashboard</Link>
              <Link className="hover:text-white" to="/history">History</Link>
              <button onClick={logout} className="rounded-lg border border-slate-700 px-3 py-1.5 hover:border-cyan-400 hover:text-white">
                Logout
              </button>
            </>
          ) : (
            <>
              <Link className="hover:text-white" to="/login">Login</Link>
              <Link className="rounded-lg bg-cyan-400 px-3 py-1.5 font-medium text-slate-950" to="/signup">Sign up</Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
