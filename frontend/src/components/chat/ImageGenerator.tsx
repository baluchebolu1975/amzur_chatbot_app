import { useState } from "react";

import { generateImage } from "../../lib/api";

type ImageGeneratorProps = {
  onImageGenerated: (url: string) => void;
};

export function ImageGenerator({ onImageGenerated }: ImageGeneratorProps) {
  const [prompt, setPrompt] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setError("Please enter a prompt");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await generateImage(prompt.trim());
      setPrompt("");
      onImageGenerated(result.url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Image generation failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="font-semibold text-slate-900">Generate Image</h3>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Describe the image you want to generate..."
        className="w-full resize-none rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-cyan-700"
        rows={3}
        disabled={isLoading}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        onClick={handleGenerate}
        disabled={isLoading || !prompt.trim()}
        className="w-full rounded-lg bg-cyan-700 px-4 py-2 text-white disabled:opacity-60"
      >
        {isLoading ? "Generating..." : "Generate Image"}
      </button>
    </div>
  );
}
