import { GoogleLogin } from "@react-oauth/google";

type GoogleOAuthButtonProps = {
  onCredential: (idToken: string) => Promise<void>;
};

export function GoogleOAuthButton({ onCredential }: GoogleOAuthButtonProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <p className="mb-4 text-sm text-slate-600">Google OAuth</p>
      <GoogleLogin
        onSuccess={async (credentialResponse) => {
          const token = credentialResponse.credential;
          if (!token) {
            return;
          }
          await onCredential(token);
        }}
        onError={() => {
          // noop: error handled by page-level state.
        }}
      />
    </div>
  );
}
