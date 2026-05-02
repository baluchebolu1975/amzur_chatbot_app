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
    <form
      onSubmit={submit}
      className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <div>
        <h2 className="text-xl font-semibold text-slate-900">
          {isRegister ? "Create account" : "Sign in"}
        </h2>
        <p className="text-sm text-slate-600">
          Use email/password or Google OAuth.
        </p>
      </div>

      {isRegister ? (
        <input
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="Full name"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-cyan-600"
        />
      ) : null}

      <input
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        type="email"
        required
        className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-cyan-600"
      />

      <input
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        type="password"
        required
        minLength={8}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-cyan-600"
      />

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-cyan-700 px-3 py-2 font-medium text-white transition hover:bg-cyan-800 disabled:opacity-60"
      >
        {loading ? "Please wait..." : isRegister ? "Create account" : "Sign in"}
      </button>

      <button
        type="button"
        onClick={() => setIsRegister((value) => !value)}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700"
      >
        {isRegister
          ? "Already have an account? Sign in"
          : "Don't have an account? Register"}
      </button>
    </form>
  );
}
