import { useNavigate } from "react-router-dom";

import { GoogleOAuthButton } from "../components/auth/GoogleOAuthButton";
import { LoginForm } from "../components/auth/LoginForm";
import { useAuthActions } from "../hooks/useAuth";

export default function LoginPage() {
  const navigate = useNavigate();
  const { loginMutation, registerMutation, googleMutation } = useAuthActions();

  const busy =
    loginMutation.isPending ||
    registerMutation.isPending ||
    googleMutation.isPending;
  const error =
    loginMutation.error || registerMutation.error || googleMutation.error;

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_#dff4ff_0%,_#f4fbff_35%,_#eef2ff_100%)] px-4 py-10">
      <div className="mx-auto grid max-w-5xl gap-6 md:grid-cols-2">
        <section className="rounded-2xl bg-slate-900 p-8 text-white shadow-lg">
          <p className="mb-4 text-sm uppercase tracking-[0.2em] text-cyan-300">
            Context
          </p>
          <h1 className="mb-3 text-3xl font-bold">Amzur AI Chat</h1>
          <p className="text-slate-200">
            Internal multi-user conversational AI platform with persistent
            threads and secure OAuth.
          </p>

          <div className="mt-8 space-y-3 text-sm">
            <p>
              <span className="font-semibold">Goal:</span> Secure login +
              persistent chat + LiteLLM-only routing.
            </p>
            <p>
              <span className="font-semibold">Rules:</span> JWT in httpOnly
              cookie, no direct provider calls.
            </p>
            <p>
              <span className="font-semibold">Output:</span> Production-ready,
              testable foundations.
            </p>
          </div>
        </section>

        <section className="space-y-4">
          <LoginForm
            loading={busy}
            onLogin={async (payload) => {
              await loginMutation.mutateAsync(payload);
              navigate("/chat");
            }}
            onRegister={async (payload) => {
              await registerMutation.mutateAsync(payload);
              navigate("/chat");
            }}
          />

          <GoogleOAuthButton
            onCredential={async (idToken) => {
              await googleMutation.mutateAsync(idToken);
              navigate("/chat");
            }}
          />

          {error ? (
            <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {typeof error === "object" &&
              error !== null &&
              "response" in error
                ? (error as any).response?.data?.detail?.message ||
                  (error as any).response?.data?.detail ||
                  "Authentication failed"
                : String(error)}
            </p>
          ) : null}
        </section>
      </div>
    </main>
  );
}
