import { useEffect, useState } from "react";

export interface SpinnerProps {
  label?: string;
  color?: string;
  speed?: number;
  variant?: "dots" | "line" | "braille" | "bounce";
}

const SPINNER_FRAMES: Record<string, string[]> = {
  dots: ["\u28F7", "\u28EF", "\u28DF", "\u28BF", "\u287F", "\u28FE", "\u28FD", "\u28FB"],
  line: ["|", "/", "-", "\\"],
  braille: ["\u2801", "\u2802", "\u2804", "\u2840", "\u2880", "\u2820", "\u2810", "\u2808"],
  bounce: ["\u2581", "\u2582", "\u2583", "\u2584", "\u2585", "\u2586", "\u2587", "\u2588", "\u2587", "\u2586", "\u2585", "\u2584", "\u2583", "\u2582"],
};

export function Spinner({
  label,
  color = "#0EA5E9",
  speed = 80,
  variant = "dots",
}: SpinnerProps) {
  const [frameIndex, setFrameIndex] = useState(0);
  const frames = SPINNER_FRAMES[variant] ?? SPINNER_FRAMES.dots;

  useEffect(() => {
    const interval = setInterval(() => {
      setFrameIndex((prev) => (prev + 1) % frames.length);
    }, speed);

    return () => clearInterval(interval);
  }, [frames.length, speed]);

  const currentFrame = frames[frameIndex];

  return (
    <box style={{ flexDirection: "row", gap: 1 }}>
      <text fg={color}>{currentFrame}</text>
      {label && <text fg="#94A3B8">{label}</text>}
    </box>
  );
}

export function LoadingPlaceholder({
  message = "Loading...",
  color = "#0EA5E9",
}: {
  message?: string;
  color?: string;
}) {
  return (
    <box
      style={{
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 2,
      }}
    >
      <Spinner label={message} color={color} />
    </box>
  );
}

export function ProgressSpinner({
  progress,
  label,
  color = "#0EA5E9",
}: {
  progress: number;
  label?: string;
  color?: string;
}) {
  const percentage = Math.round(Math.min(100, Math.max(0, progress)));

  return (
    <box style={{ flexDirection: "row", gap: 1 }}>
      <Spinner color={color} variant="dots" />
      <text fg="#FFFFFF">{percentage}%</text>
      {label && <text fg="#94A3B8">{label}</text>}
    </box>
  );
}
