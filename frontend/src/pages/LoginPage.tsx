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
    <main className="relative min-h-screen overflow-hidden bg-transparent">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-32 -right-20 h-[26rem] w-[26rem] rounded-full bg-blue-300/25 blur-3xl"></div>
        <div className="absolute -bottom-32 -left-20 h-[24rem] w-[24rem] rounded-full bg-cyan-300/25 blur-3xl"></div>
        <div className="absolute top-1/2 left-1/2 h-[30rem] w-[30rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-100/70 blur-3xl"></div>
      </div>

      {/* Content */}
      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-4 py-10">
        <div className="w-full max-w-5xl">
          {/* Header */}
          <div className="mb-12 text-center slide-down">
            <h1 className="mb-3 bg-gradient-to-r from-slate-900 via-blue-900 to-slate-700 bg-clip-text text-5xl font-extrabold tracking-tight text-transparent">
              Amzur AI Chat
            </h1>
            <p className="text-lg text-slate-600">
              Enterprise-grade AI conversation platform
            </p>
          </div>

          {/* Main Grid */}
          <div className="grid gap-8 md:grid-cols-2">
            {/* Left Panel - Info */}
            <section className="glass-effect slide-up rounded-3xl p-8">
              <div className="space-y-8">
                <div>
                  <p className="mb-2 inline-block rounded-full bg-blue-50 px-4 py-1 text-xs font-semibold uppercase tracking-widest text-blue-800">
                    ✨ Platform Features
                  </p>
                  <h2 className="mt-4 text-2xl font-bold tracking-tight text-slate-900">
                    Secure, Scalable, Intelligent
                  </h2>
                </div>

                <div className="space-y-4">
                  {[
                    {
                      icon: "🔒",
                      title: "Bank-Grade Security",
                      desc: "JWT in httpOnly cookies, zero direct provider exposure",
                    },
                    {
                      icon: "💬",
                      title: "Persistent Threads",
                      desc: "All conversations saved and searchable in real-time",
                    },
                    {
                      icon: "⚡",
                      title: "LiteLLM Routing",
                      desc: "Intelligent model selection and failover handling",
                    },
                    {
                      icon: "🎨",
                      title: "Rich Interface",
                      desc: "Chat, image gen, RAG, and database query support",
                    },
                  ].map((feature, idx) => (
                    <div
                      key={idx}
                      className="group rounded-2xl border border-slate-200/70 bg-white/90 p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
                    >
                      <div className="flex gap-3">
                        <span className="text-2xl">{feature.icon}</span>
                        <div>
                          <p className="font-semibold text-slate-900">
                            {feature.title}
                          </p>
                          <p className="text-sm text-slate-600">
                            {feature.desc}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            {/* Right Panel - Auth */}
            <section className="slide-up space-y-4 [animation-delay:100ms]">
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
                <div className="slide-up rounded-2xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
                  <p className="font-semibold">Authentication Error</p>
                  <p className="mt-1 text-xs">
                    {typeof error === "object" &&
                    error !== null &&
                    "response" in error
                      ? (error as any).response?.data?.detail?.message ||
                        (error as any).response?.data?.detail ||
                        "Authentication failed"
                      : String(error)}
                  </p>
                </div>
              ) : null}
            </section>
          </div>

          {/* Footer */}
          <p className="mt-12 text-center text-xs text-slate-500">
            © 2026 Amzur AI. All rights reserved. | Production-Grade Platform
          </p>
        </div>
      </div>
    </main>
  );
}
