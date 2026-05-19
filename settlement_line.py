<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
  <defs>
    <!-- Document shadow -->
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="4" dy="6" stdDeviation="8" flood-color="#b8a0d0" flood-opacity="0.35"/>
    </filter>
    <filter id="coinShadow" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="2" dy="3" stdDeviation="4" flood-color="#7ec8c8" flood-opacity="0.4"/>
    </filter>
    <!-- Document gradient (pastel purple/lavender) -->
    <linearGradient id="docGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#e8d5f5"/>
      <stop offset="100%" stop-color="#c8b4e8"/>
    </linearGradient>
    <!-- Document face (lighter) -->
    <linearGradient id="docFace" x1="0" y1="0" x2="0.3" y2="1">
      <stop offset="0%" stop-color="#f5eeff"/>
      <stop offset="100%" stop-color="#ddc8f8"/>
    </linearGradient>
    <!-- Coin gradient (pastel teal/green) -->
    <linearGradient id="coinGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#a8e6d4"/>
      <stop offset="100%" stop-color="#6dcfb8"/>
    </linearGradient>
    <linearGradient id="coinTop" x1="0" y1="0" x2="0.5" y2="1">
      <stop offset="0%" stop-color="#d4f5ec"/>
      <stop offset="100%" stop-color="#9ae0cc"/>
    </linearGradient>
    <!-- Check gradient -->
    <linearGradient id="checkGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#7ed9a0"/>
      <stop offset="100%" stop-color="#4dc98a"/>
    </linearGradient>
  </defs>

  <!-- Document 3D side (darker) -->
  <path d="M48 42 L144 42 L152 52 L152 165 L48 165 Z" fill="url(#docGrad)" filter="url(#shadow)"/>
  <!-- Document fold corner -->
  <path d="M120 42 L144 42 L152 52 L120 52 Z" fill="#c4a8e0"/>
  <path d="M120 42 L152 52 L120 52 Z" fill="#b090d0"/>
  <!-- Document face -->
  <rect x="40" y="38" width="80" height="124" rx="6" ry="6" fill="url(#docFace)"/>

  <!-- Lines on document (pastel teal) -->
  <rect x="52" y="62" width="44" height="5" rx="2.5" fill="#b8dff0"/>
  <rect x="52" y="74" width="56" height="4" rx="2" fill="#d0e8f8"/>
  <rect x="52" y="84" width="50" height="4" rx="2" fill="#d0e8f8"/>
  <rect x="52" y="96" width="56" height="4" rx="2" fill="#d0e8f8"/>
  <rect x="52" y="106" width="40" height="4" rx="2" fill="#d0e8f8"/>

  <!-- Separator line -->
  <line x1="52" y1="116" x2="108" y2="116" stroke="#c8b4e8" stroke-width="1.5"/>

  <!-- Total amount area -->
  <rect x="52" y="122" width="56" height="8" rx="3" fill="#e8d5f5"/>
  <rect x="72" y="123.5" width="30" height="5" rx="2" fill="#c0a0e0"/>

  <!-- Coin (3D ellipse) — bottom face -->
  <ellipse cx="108" cy="147" rx="28" ry="9" fill="url(#coinGrad)" filter="url(#coinShadow)"/>
  <!-- Coin cylinder body -->
  <rect x="80" y="126" width="56" height="21" rx="0" fill="url(#coinGrad)"/>
  <rect x="80" y="126" width="56" height="21" fill="url(#coinGrad)"/>
  <!-- Coin top face -->
  <ellipse cx="108" cy="126" rx="28" ry="9" fill="url(#coinTop)"/>
  <!-- Dollar sign on coin -->
  <text x="108" y="131" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#4a9e88">Q</text>

  <!-- Checkmark circle (top-right, pastel green) -->
  <circle cx="140" cy="58" r="20" fill="#e8f8ef" filter="url(#shadow)"/>
  <circle cx="140" cy="58" r="17" fill="url(#checkGrad)"/>
  <!-- Checkmark -->
  <polyline points="131,58 138,65 150,50" stroke="white" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>
