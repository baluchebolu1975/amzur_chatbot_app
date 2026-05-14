import { GoogleLogin } from "@react-oauth/google";

type GoogleOAuthButtonProps = {
  onCredential: (idToken: string) => Promise<void>;
};

export function GoogleOAuthButton({ onCredential }: GoogleOAuthButtonProps) {
  return (
    <div className="glass-effect space-y-3 rounded-3xl p-8">
      <p className="text-sm font-semibold text-slate-700">
        🚀 Continue with Google
      </p>
      <div className="[&_.google-button]:!w-full [&_.google-button]:!rounded-xl [&_.google-button]:!border [&_.google-button]:!border-slate-200 [&_.google-button]:!shadow-sm [&_.google-button]:!transition [&_.google-button:hover]:!bg-slate-50">
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
    </div>
  );
}
