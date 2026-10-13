import type { SVGProps } from 'react';

export type ChessPieceType = 'pawn' | 'knight' | 'bishop' | 'rook' | 'queen';

interface ChessPieceProps extends SVGProps<SVGSVGElement> {
  type: ChessPieceType;
  size?: number | string;
  className?: string;
  glow?: boolean;
}

export const ChessPiece = ({
  type,
  size = 48,
  className = '',
  glow = false,
  ...props
}: ChessPieceProps) => {
  const glowFilter = glow ? 'drop-shadow(0 0 14px rgba(118, 150, 86, 0.55))' : undefined;

  switch (type) {
    case 'pawn':
      return (
        <svg
          width={size}
          height={size}
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className={`litmus-chess-piece litmus-chess-piece--pawn ${className}`}
          style={{ filter: glowFilter }}
          aria-label="Pawn piece"
          role="img"
          {...props}
        >
          {/* Head sphere */}
          <circle cx="32" cy="18" r="9" fill="currentColor" />
          <circle cx="29" cy="15" r="3" fill="#ffffff" fillOpacity="0.3" />
          {/* Neck collar */}
          <path
            d="M24 28C24 26.5 40 26.5 40 28C40 29.5 24 29.5 24 28Z"
            fill="currentColor"
          />
          {/* Stem / Torso */}
          <path
            d="M26 29C25.5 36 21 43 18 47H46C43 43 38.5 36 38 29H26Z"
            fill="currentColor"
          />
          {/* Pedestal rim */}
          <rect x="14" y="48" width="36" height="5" rx="2.5" fill="currentColor" />
          {/* Pedestal base */}
          <rect x="10" y="54" width="44" height="6" rx="3" fill="currentColor" />
        </svg>
      );

    case 'knight':
      return (
        <svg
          width={size}
          height={size}
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className={`litmus-chess-piece litmus-chess-piece--knight ${className}`}
          style={{ filter: glowFilter }}
          aria-label="Knight piece"
          role="img"
          {...props}
        >
          {/* Horse Head and Mane */}
          <path
            d="M32 9C29 10 27 13 26 15C25 14 23 13 21 14C20 15 20 17 21 19C19 21 17 25 15 29C13 33 13 37 16 39C18 40.5 22 39 25 36C26 38 29 40 31 41C29 44 26 46 22 47H46C46 45 45 42 45 38C45 30 46 24 43 17C40 12 36 9 32 9Z"
            fill="currentColor"
          />
          {/* Mane ridges */}
          <path
            d="M34 11C37 14 41 20 42 27M36 25C40 29 42 34 43 41"
            stroke="#ffffff"
            strokeOpacity="0.35"
            strokeWidth="2"
            strokeLinecap="round"
          />
          {/* Eye */}
          <circle cx="23" cy="24" r="2.2" fill="#ffffff" fillOpacity="0.9" />
          <circle cx="23.5" cy="24" r="1.1" fill="#1b3720" />
          {/* Snout nostril */}
          <circle cx="16" cy="35" r="1.5" fill="#ffffff" fillOpacity="0.4" />
          {/* Pedestal rim */}
          <rect x="14" y="48" width="36" height="5" rx="2.5" fill="currentColor" />
          {/* Pedestal base */}
          <rect x="10" y="54" width="44" height="6" rx="3" fill="currentColor" />
        </svg>
      );

    case 'bishop':
      return (
        <svg
          width={size}
          height={size}
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className={`litmus-chess-piece litmus-chess-piece--bishop ${className}`}
          style={{ filter: glowFilter }}
          aria-label="Bishop piece"
          role="img"
          {...props}
        >
          {/* Finial sphere at top */}
          <circle cx="32" cy="9" r="3.2" fill="currentColor" />
          {/* Mitre head with cleft slash */}
          <path
            d="M32 14C23 15 21 24 23 30C24 33 26 35 32 35C38 35 40 33 41 30C43 24 41 15 32 14Z"
            fill="currentColor"
          />
          {/* Cleft cut */}
          <path
            d="M28 20L36 28"
            stroke="#1b3720"
            strokeWidth="2.4"
            strokeLinecap="round"
          />
          {/* Mitre collar */}
          <path
            d="M23 35C23 33.5 41 33.5 41 35C41 36.5 23 36.5 23 35Z"
            fill="currentColor"
          />
          {/* Stem */}
          <path
            d="M26 36C25.5 41 21 44 18 47H46C43 44 38.5 41 38 36H26Z"
            fill="currentColor"
          />
          {/* Pedestal rim */}
          <rect x="14" y="48" width="36" height="5" rx="2.5" fill="currentColor" />
          {/* Pedestal base */}
          <rect x="10" y="54" width="44" height="6" rx="3" fill="currentColor" />
        </svg>
      );

    case 'rook':
      return (
        <svg
          width={size}
          height={size}
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className={`litmus-chess-piece litmus-chess-piece--rook ${className}`}
          style={{ filter: glowFilter }}
          aria-label="Rook piece"
          role="img"
          {...props}
        >
          {/* Crenellations / Battlement */}
          <path
            d="M19 14H25V19H29V14H35V19H39V14H45V24C45 25.5 43 26.5 41 27H23C21 26.5 19 25.5 19 24V14Z"
            fill="currentColor"
          />
          {/* Corbel trim */}
          <rect x="21" y="27" width="22" height="3" rx="1" fill="currentColor" />
          {/* Tower column */}
          <path
            d="M23 30H41V47H23V30Z"
            fill="currentColor"
          />
          {/* Arrow slit window */}
          <rect x="30" y="34" width="4" height="8" rx="2" fill="#1b3720" fillOpacity="0.75" />
          {/* Pedestal rim */}
          <rect x="14" y="48" width="36" height="5" rx="2.5" fill="currentColor" />
          {/* Pedestal base */}
          <rect x="10" y="54" width="44" height="6" rx="3" fill="currentColor" />
        </svg>
      );

    case 'queen':
      return (
        <svg
          width={size}
          height={size}
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className={`litmus-chess-piece litmus-chess-piece--queen ${className}`}
          style={{ filter: glowFilter }}
          aria-label="Queen piece"
          role="img"
          {...props}
        >
          {/* 5 Crown Pearls */}
          <circle cx="16" cy="18" r="2.5" fill="currentColor" />
          <circle cx="24" cy="14" r="2.5" fill="currentColor" />
          <circle cx="32" cy="11" r="3" fill="currentColor" />
          <circle cx="40" cy="14" r="2.5" fill="currentColor" />
          <circle cx="48" cy="18" r="2.5" fill="currentColor" />
          {/* Coronet crown spikes & body */}
          <path
            d="M16 20L21 31H43L48 20L40 28L32 15L24 28L16 20Z"
            fill="currentColor"
          />
          <path
            d="M21 31C21 33 43 33 43 31V34C43 36 21 36 21 34V31Z"
            fill="currentColor"
          />
          {/* Gown / Fluted stem */}
          <path
            d="M24 35C24.5 40 21 44 18 47H46C43 44 39.5 40 40 35H24Z"
            fill="currentColor"
          />
          {/* Decorative crown highlight */}
          <circle cx="32" cy="25" r="2" fill="#ffffff" fillOpacity="0.4" />
          {/* Pedestal rim */}
          <rect x="14" y="48" width="36" height="5" rx="2.5" fill="currentColor" />
          {/* Pedestal base */}
          <rect x="10" y="54" width="44" height="6" rx="3" fill="currentColor" />
        </svg>
      );
  }
};
