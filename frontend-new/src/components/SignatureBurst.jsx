import React, { useMemo } from 'react';

/**
 * Signature graphic: a half-circle burst of thin radiating white-lavender lines
 * with small dots at the tips, low opacity, slow subtle animation.
 * Exactly matched to the reference screenshot.
 */
export default function SignatureBurst({ 
  className = "", 
  variant = "dark", // "dark" (for hero/gradient) or "light" (for empty states)
  density = 96,
  height = 360,
}) {
  const lines = useMemo(() => {
    const list = [];
    // Radiate upwards from bottom-center: angle from ~ -78 deg to +78 deg relative to vertical (90 deg)
    // In standard polar coords where 0 deg is right, vertical up is 90 deg (or Math.PI/2)
    const baseAngle = -Math.PI / 2; // -90 deg (straight up)
    const angleSpread = (82 * Math.PI) / 180; // +/- 82 degrees

    for (let i = 0; i < density; i++) {
      const t = i / (density - 1); // 0 to 1
      // Angle offset from center
      const angleOffset = (t - 0.5) * 2 * angleSpread;
      // Add slight jitter so it looks organic like the reference
      const jitter = (Math.sin(i * 12.9898) * 0.015);
      const angle = baseAngle + angleOffset + jitter;

      // Length variation: higher in the middle, varied tips
      const centerFactor = 1 - Math.pow((t - 0.5) * 1.5, 2);
      const noise = ((Math.sin(i * 78.233) + 1) / 2) * 0.45;
      const lengthRatio = Math.max(0.38, Math.min(0.96, (0.55 + 0.35 * centerFactor + noise * 0.3)));

      const length = lengthRatio * height;
      const xEnd = Math.cos(angle) * length;
      const yEnd = Math.sin(angle) * length;

      // Dot size
      const dotRadius = 1.0 + ((i % 4) * 0.45);
      const dotOpacity = 0.5 + ((i % 5) * 0.1);
      const lineOpacity = 0.22 + ((i % 7) * 0.09);

      list.push({
        id: i,
        xEnd,
        yEnd,
        length,
        dotRadius,
        dotOpacity,
        lineOpacity,
        delay: (i % 8) * 0.6,
      });
    }
    return list;
  }, [density, height]);

  const isLight = variant === "light";
  const strokeColor = isLight ? "rgba(95, 77, 203, 0.45)" : "rgba(225, 221, 250, 0.65)";
  const dotColor = isLight ? "#5F4DCB" : "#FFFFFF";
  const glowCenterColor = isLight ? "rgba(197, 196, 242, 0.5)" : "rgba(197, 196, 242, 0.7)";

  return (
    <div 
      className={`pointer-events-none select-none relative w-full overflow-hidden flex items-end justify-center ${className}`}
      style={{ height: `${height}px` }}
      aria-hidden="true"
    >
      <svg
        viewBox={`-${height} -${height} ${height * 2} ${height}`}
        className="w-full h-full burst-animation overflow-visible"
        style={{ maxHeight: `${height}px` }}
      >
        <defs>
          {/* Radial soft glow at the origin */}
          <radialGradient id={`burst-core-glow-${variant}`} cx="50%" cy="100%" r="60%">
            <stop offset="0%" stopColor={glowCenterColor} stopOpacity={isLight ? "0.6" : "0.85"} />
            <stop offset="45%" stopColor={glowCenterColor} stopOpacity={isLight ? "0.2" : "0.3"} />
            <stop offset="100%" stopColor={glowCenterColor} stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Ambient glow hemisphere at the base */}
        <circle
          cx="0"
          cy="0"
          r={height * 0.55}
          fill={`url(#burst-core-glow-${variant})`}
        />

        {/* Radiating lines and tip dots */}
        <g strokeLinecap="round">
          {lines.map((line) => (
            <g key={line.id}>
              {/* Radiating line */}
              <line
                x1="0"
                y1="0"
                x2={line.xEnd}
                y2={line.yEnd}
                stroke={strokeColor}
                strokeWidth={line.length > height * 0.75 ? "1.15" : "0.85"}
                strokeOpacity={line.lineOpacity}
              />
              {/* Dot at tip */}
              <circle
                cx={line.xEnd}
                cy={line.yEnd}
                r={line.dotRadius}
                fill={dotColor}
                fillOpacity={line.dotOpacity}
              />
            </g>
          ))}
        </g>

        {/* Dense glowing core at origin */}
        <ellipse
          cx="0"
          cy="0"
          rx={height * 0.25}
          ry={height * 0.1}
          fill={dotColor}
          fillOpacity={isLight ? "0.25" : "0.45"}
        />
      </svg>
    </div>
  );
}
