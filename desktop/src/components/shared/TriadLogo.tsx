interface Props {
  size?: number;
  className?: string;
}

/**
 * Triad logo — three rounded petals arranged as a trefoil bloom.
 * Inspired by ChatGPT's flower logo with 3 petals instead of 5.
 * Each petal is a filled rounded shape. The petals share the same
 * center point and rotate at 120° intervals. Simple, clean, iconic.
 */
export function TriadLogo({ size = 40, className = "" }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      className={className}
    >
      {/* Petal 1: top — rounded teardrop shape */}
      <path
        d="M50 50 C44 44, 40 30, 40 22 C40 12, 50 6, 50 6 C50 6, 60 12, 60 22 C60 30, 56 44, 50 50Z"
        fill="currentColor"
        opacity="0.85"
      />

      {/* Petal 2: bottom-right */}
      <path
        d="M50 50 C56 44, 68 38, 76 42 C84 46, 86 58, 86 58 C86 58, 80 64, 72 62 C64 60, 54 52, 50 50Z"
        fill="currentColor"
        opacity="0.85"
      />

      {/* Petal 3: bottom-left */}
      <path
        d="M50 50 C46 56, 36 64, 28 62 C20 60, 14 50, 14 50 C14 50, 18 40, 26 40 C34 40, 46 48, 50 50Z"
        fill="currentColor"
        opacity="0.85"
      />

      {/* Subtle outlines for definition */}
      <path
        d="M50 50 C44 44, 40 30, 40 22 C40 12, 50 6, 50 6 C50 6, 60 12, 60 22 C60 30, 56 44, 50 50Z"
        stroke="currentColor"
        strokeWidth="1"
        opacity="0.3"
      />
      <path
        d="M50 50 C56 44, 68 38, 76 42 C84 46, 86 58, 86 58 C86 58, 80 64, 72 62 C64 60, 54 52, 50 50Z"
        stroke="currentColor"
        strokeWidth="1"
        opacity="0.3"
      />
      <path
        d="M50 50 C46 56, 36 64, 28 62 C20 60, 14 50, 14 50 C14 50, 18 40, 26 40 C34 40, 46 48, 50 50Z"
        stroke="currentColor"
        strokeWidth="1"
        opacity="0.3"
      />
    </svg>
  );
}
