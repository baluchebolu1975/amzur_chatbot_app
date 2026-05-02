import { type FormEvent, useState } from "react";

type InputBarProps = {
  disabled: boolean;
  onSend: (message: string) => Promise<void>;
};

export function InputBar({ disabled, onSend }: InputBarProps) {
  const [message, setMessage] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) {
      return;
    }
    setMessage("");
    await onSend(trimmed);
  };

  return (
    <form onSubmit={submit} className="border-t border-slate-200 bg-white p-4">
      <div className="flex gap-3">
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          className="h-20 flex-1 resize-none rounded-xl border border-slate-300 px-3 py-2 outline-none focus:border-cyan-700"
          placeholder="Type your question..."
        />
        <button
          type="submit"
          disabled={disabled}
          className="rounded-xl bg-cyan-700 px-5 py-2 text-white disabled:opacity-60"
        >
          Send
        </button>
      </div>
    </form>
  );
}
