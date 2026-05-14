import { type FormEvent, useState } from "react";

type LoginFormProps = {
  onLogin: (payload: { email: string; password: string }) => Promise<void>;
  onRegister: (payload: {
    email: string;
    password: string;
    full_name?: string;
  }) => Promise<void>;
  loading: boolean;
};

export function LoginForm({ onLogin, onRegister, loading }: LoginFormProps) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isRegister) {
      await onRegister({ email, password, full_name: fullName || undefined });
      return;
    }
    await onLogin({ email, password });
  };

  return (
    <form onSubmit={submit} className="glass-effect space-y-5 rounded-3xl p-8">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          {isRegister ? "Create Account" : "Welcome Back"}
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          {isRegister
            ? "Join thousands using AI responsibly"
            : "Sign in to your dashboard"}
        </p>
      </div>

      {isRegister ? (
        <div className="group">
          <label className="mb-2 block text-sm font-semibold text-slate-700">
            Full Name
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">
              👤
            </span>
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="John Doe"
              className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-4 text-slate-900 placeholder-slate-400 shadow-sm transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
            />
          </div>
        </div>
      ) : null}

      <div className="group">
        <label className="mb-2 block text-sm font-semibold text-slate-700">
          Email Address
        </label>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">
            ✉️
          </span>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            type="email"
            required
            className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-4 text-slate-900 placeholder-slate-400 shadow-sm transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
          />
        </div>
      </div>

      <div className="group">
        <label className="mb-2 block text-sm font-semibold text-slate-700">
          Password
        </label>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">
            🔐
          </span>
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            type="password"
            required
            minLength={8}
            className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-4 text-slate-900 placeholder-slate-400 shadow-sm transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="group relative w-full overflow-hidden rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 py-3 font-semibold text-white shadow-lg shadow-blue-500/30 transition duration-300 hover:from-blue-700 hover:to-cyan-600 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <div className="absolute inset-0 bg-gradient-to-r from-cyan-500 to-blue-600 opacity-0 transition group-hover:opacity-100"></div>
        <span className="relative flex items-center justify-center gap-2">
          {loading ? (
            <>
              <span className="spin-smooth inline-block h-4 w-4 rounded-full border-2 border-white/30 border-t-white"></span>
              Processing...
            </>
          ) : isRegister ? (
            "Create Account"
          ) : (
            "Sign In"
          )}
        </span>
      </button>

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-200"></div>
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="bg-white px-2 text-slate-500">or</span>
        </div>
      </div>

      <button
        type="button"
        onClick={() => {
          setIsRegister((value) => !value);
          setEmail("");
          setPassword("");
          setFullName("");
        }}
        className="w-full rounded-xl border border-slate-200 bg-white py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 hover:text-slate-900"
      >
        {isRegister
          ? "Already have an account? Sign In"
          : "Don't have an account? Register"}
      </button>
    </form>
  );
}
