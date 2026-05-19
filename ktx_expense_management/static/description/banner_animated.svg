<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 300" width="900" height="300" font-family="'Segoe UI',Arial,sans-serif">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#f0f4ff"/>
      <stop offset="100%" style="stop-color:#e8f8f0"/>
    </linearGradient>
    <linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#a78bfa"/>
      <stop offset="100%" style="stop-color:#7c3aed"/>
    </linearGradient>
    <linearGradient id="g2" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#60a5fa"/>
      <stop offset="100%" style="stop-color:#2563eb"/>
    </linearGradient>
    <linearGradient id="g3" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#34d399"/>
      <stop offset="100%" style="stop-color:#059669"/>
    </linearGradient>
    <linearGradient id="g4" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#fbbf24"/>
      <stop offset="100%" style="stop-color:#d97706"/>
    </linearGradient>
    <linearGradient id="g5" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#f472b6"/>
      <stop offset="100%" style="stop-color:#db2777"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#00000018"/>
    </filter>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <style>
      /* Entrance animations — each card fades + slides up in sequence */
      .card1 { animation: fadeUp 0.6s ease forwards; animation-delay: 0.1s; opacity: 0; }
      .card2 { animation: fadeUp 0.6s ease forwards; animation-delay: 0.5s; opacity: 0; }
      .card3 { animation: fadeUp 0.6s ease forwards; animation-delay: 0.9s; opacity: 0; }
      .card4 { animation: fadeUp 0.6s ease forwards; animation-delay: 1.3s; opacity: 0; }
      .card5 { animation: fadeUp 0.6s ease forwards; animation-delay: 1.7s; opacity: 0; }

      /* Arrows appear after each card */
      .arr1 { animation: fadeIn 0.4s ease forwards; animation-delay: 0.7s; opacity: 0; }
      .arr2 { animation: fadeIn 0.4s ease forwards; animation-delay: 1.1s; opacity: 0; }
      .arr3 { animation: fadeIn 0.4s ease forwards; animation-delay: 1.5s; opacity: 0; }
      .arr4 { animation: fadeIn 0.4s ease forwards; animation-delay: 1.9s; opacity: 0; }

      /* Title */
      .title  { animation: fadeDown 0.7s ease forwards; animation-delay: 0s; opacity: 0; }
      .tagline{ animation: fadeDown 0.7s ease forwards; animation-delay: 0.3s; opacity: 0; }

      /* Pulse on icons */
      .pulse { animation: pulse 2.5s ease-in-out infinite; }

      /* Floating dots */
      .dot1 { animation: float1 4s ease-in-out infinite; }
      .dot2 { animation: float2 5s ease-in-out infinite; }
      .dot3 { animation: float3 3.5s ease-in-out infinite; }

      /* Badge counter */
      .badge { animation: pop 0.4s ease forwards; animation-delay: 2.2s; opacity: 0; transform-origin: 50% 50%; }

      @keyframes fadeUp {
        from { opacity: 0; transform: translateY(20px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      @keyframes fadeDown {
        from { opacity: 0; transform: translateY(-14px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      @keyframes fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
      }
      @keyframes pulse {
        0%,100% { transform: scale(1); }
        50%     { transform: scale(1.12); }
      }
      @keyframes float1 {
        0%,100% { transform: translateY(0px); }
        50%     { transform: translateY(-8px); }
      }
      @keyframes float2 {
        0%,100% { transform: translateY(0px); }
        50%     { transform: translateY(10px); }
      }
      @keyframes float3 {
        0%,100% { transform: translateY(0px); }
        50%     { transform: translateY(-6px); }
      }
      @keyframes pop {
        from { opacity: 0; transform: scale(0.4); }
        to   { opacity: 1; transform: scale(1); }
      }
    </style>
  </defs>

  <!-- Background -->
  <rect width="900" height="300" fill="url(#bg)" rx="16"/>

  <!-- Decorative floating blobs -->
  <circle class="dot1" cx="820" cy="40" r="55" fill="#a78bfa" opacity="0.08"/>
  <circle class="dot2" cx="60"  cy="260" r="70" fill="#34d399" opacity="0.07"/>
  <circle class="dot3" cx="460" cy="290" r="45" fill="#60a5fa" opacity="0.07"/>
  <circle cx="140" cy="30" r="30" fill="#fbbf24" opacity="0.07"/>

  <!-- Title block -->
  <text class="title" x="450" y="38" text-anchor="middle" font-size="22" font-weight="800" fill="#1e293b" letter-spacing="-0.5">
    Módulo de Liquidaciones de Gastos
  </text>
  <text class="tagline" x="450" y="60" text-anchor="middle" font-size="12" fill="#64748b" font-weight="500">
    Captura · Staging · Aprobación · Contabilidad · Pago
  </text>
  <!-- Divider line -->
  <line x1="100" y1="72" x2="800" y2="72" stroke="#e2e8f0" stroke-width="1.5"/>

  <!-- ── CARD 1: Gastos (Facturas) ── -->
  <g class="card1" filter="url(#shadow)">
    <rect x="28" y="90" width="130" height="170" rx="14" fill="url(#g1)"/>
    <!-- Icon bg -->
    <circle cx="93" cy="138" r="30" fill="white" opacity="0.2"/>
    <!-- Receipt icon -->
    <g class="pulse" transform="translate(93,138)">
      <rect x="-16" y="-20" width="32" height="38" rx="4" fill="white" opacity="0.95"/>
      <line x1="-10" y1="-12" x2="10" y2="-12" stroke="#7c3aed" stroke-width="2.5" stroke-linecap="round"/>
      <line x1="-10" y1="-5"  x2="10" y2="-5"  stroke="#7c3aed" stroke-width="2.5" stroke-linecap="round"/>
      <line x1="-10" y1="2"   x2="4"  y2="2"   stroke="#7c3aed" stroke-width="2.5" stroke-linecap="round"/>
      <polyline points="-2,10 3,16 12,6" stroke="#7c3aed" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    </g>
    <text x="93" y="185" text-anchor="middle" font-size="11" font-weight="700" fill="white">GASTOS</text>
    <text x="93" y="200" text-anchor="middle" font-size="9.5" fill="white" opacity="0.85">Facturas &amp; asientos</text>
    <text x="93" y="214" text-anchor="middle" font-size="9.5" fill="white" opacity="0.85">capturados</text>
    <!-- Steps -->
    <rect x="40" y="228" width="106" height="24" rx="8" fill="white" opacity="0.2"/>
    <text x="93" y="244" text-anchor="middle" font-size="9" fill="white" font-weight="600">1. Seleccionar Gasto</text>
  </g>

  <!-- ── ARROW 1 ── -->
  <g class="arr1">
    <line x1="162" y1="175" x2="188" y2="175" stroke="#94a3b8" stroke-width="2.5"/>
    <polygon points="185,170 193,175 185,180" fill="#94a3b8"/>
    <!-- Moving dot on arrow -->
    <circle r="4" fill="#a78bfa" opacity="0.8">
      <animateMotion dur="1.5s" repeatCount="indefinite" begin="0.7s">
        <mpath href="#arr1path"/>
      </animateMotion>
    </circle>
    <path id="arr1path" d="M162,175 L193,175" fill="none"/>
  </g>

  <!-- ── CARD 2: Staging ── -->
  <g class="card2" filter="url(#shadow)">
    <rect x="195" y="90" width="130" height="170" rx="14" fill="url(#g2)"/>
    <circle cx="260" cy="138" r="30" fill="white" opacity="0.2"/>
    <g class="pulse" transform="translate(260,138)" style="animation-delay:0.4s">
      <!-- Tray/inbox icon -->
      <rect x="-18" y="-10" width="36" height="24" rx="4" fill="white" opacity="0.95"/>
      <path d="M-18,4 L-12,-6 L12,-6 L18,4" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linejoin="round"/>
      <line x1="-8" y1="-2" x2="8" y2="-2" stroke="#2563eb" stroke-width="2" stroke-linecap="round"/>
      <line x1="-8" y1="4" x2="4" y2="4" stroke="#2563eb" stroke-width="2" stroke-linecap="round"/>
    </g>
    <text x="260" y="185" text-anchor="middle" font-size="11" font-weight="700" fill="white">STAGING</text>
    <text x="260" y="200" text-anchor="middle" font-size="9.5" fill="white" opacity="0.85">Gastos agrupados</text>
    <text x="260" y="214" text-anchor="middle" font-size="9.5" fill="white" opacity="0.85">para liquidar</text>
    <rect x="207" y="228" width="106" height="24" rx="8" fill="white" opacity="0.2"/>
    <text x="260" y="244" text-anchor="middle" font-size="9" fill="white" font-weight="600">2. Agrupar Gastos</text>
  </g>

  <!-- ── ARROW 2 ── -->
  <g class="arr2">
    <line x1="329" y1="175" x2="355" y2="175" stroke="#94a3b8" stroke-width="2.5"/>
    <polygon points="352,170 360,175 352,180" fill="#94a3b8"/>
    <circle r="4" fill="#60a5fa" opacity="0.8">
      <animateMotion dur="1.5s" repeatCount="indefinite" begin="1.1s">
        <mpath href="#arr2path"/>
      </animateMotion>
    </circle>
    <path id="arr2path" d="M329,175 L360,175" fill="none"/>
  </g>

  <!-- ── CARD 3: Liquidación + Aprobación ── -->
  <g class="card3" filter="url(#shadow)">
    <rect x="362" y="90" width="176" height="170" rx="14" fill="url(#g3)"/>
    <!-- Wide card badge: "FLUJO PRINCIPAL" -->
    <rect x="390" y="94" width="120" height="16" rx="8" fill="white" opacity="0.25"/>
    <text x="450" y="105" text-anchor="middle" font-size="8.5" fill="white" font-weight="700">FLUJO PRINCIPAL</text>
    <circle cx="450" cy="148" r="30" fill="white" opacity="0.2"/>
    <!-- Shield/approve icon -->
    <g class="pulse" transform="translate(450,148)" style="animation-delay:0.8s">
      <path d="M0,-22 L18,-14 L18,2 Q18,18 0,24 Q-18,18 -18,2 L-18,-14 Z" fill="white" opacity="0.95"/>
      <polyline points="-8,2 -2,10 12,-6" stroke="#059669" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    </g>
    <text x="450" y="193" text-anchor="middle" font-size="11" font-weight="700" fill="white">LIQUIDACIÓN</text>
    <text x="450" y="208" text-anchor="middle" font-size="9.5" fill="white" opacity="0.85">Confirmar → Aprobar</text>
    <text x="450" y="222" text-anchor="middle" font-size="9.5" fill="white" opacity="0.85">→ Publicar</text>
    <rect x="374" y="232" width="152" height="20" rx="8" fill="white" opacity="0.2"/>
    <text x="450" y="246" text-anchor="middle" font-size="8.5" fill="white" font-weight="600">3. Autorización por Email/Actividad</text>
  </g>

  <!-- ── ARROW 3 ── -->
  <g class="arr3">
    <line x1="542" y1="175" x2="568" y2="175" stroke="#94a3b8" stroke-width="2.5"/>
    <polygon points="565,170 573,175 565,180" fill="#94a3b8"/>
    <circle r="4" fill="#34d399" opacity="0.8">
      <animateMotion dur="1.5s" repeatCount="indefinite" begin="1.5s">
        <mpath href="#arr3path"/>
      </animateMotion>
    </circle>
    <path id="arr3path" d="M542,175 L573,175" fill="none"/>
  </g>

  <!-- ── CARD 4: Asiento Contable ── -->
  <g class="card4" filter="url(#shadow)">
    <rect x="575" y="90" width="130" height="170" rx="14" fill="url(#g4)"/>
    <circle cx="640" cy="138" r="30" fill="white" opacity="0.2"/>
    <g class="pulse" transform="translate(640,138)" style="animation-delay:1.2s">
      <!-- Ledger/book icon -->
      <rect x="-18" y="-18" width="36" height="34" rx="4" fill="white" opacity="0.95"/>
      <rect x="-18" y="-18" width="8" height="34" rx="4" fill="#d97706" opacity="0.5"/>
      <line x1="-4" y1="-10" x2="13" y2="-10" stroke="#d97706" stroke-width="2" stroke-linecap="round"/>
      <line x1="-4" y1="-3"  x2="13" y2="-3"  stroke="#d97706" stroke-width="2" stroke-linecap="round"/>
      <line x1="-4" y1="4"   x2="13" y2="4"   stroke="#d97706" stroke-width="2" stroke-linecap="round"/>
      <line x1="-4" y1="11"  x2="8"  y2="11"  stroke="#d97706" stroke-width="2" stroke-linecap="round"/>
    </g>
    <text x="640" y="185" text-anchor="middle" font-size="11" font-weight="700" fill="white">CONTABILIDAD</text>
    <text x="640" y="200" text-anchor="middle" font-size="9.5" fill="white" opacity="0.85">Asiento automático</text>
    <text x="640" y="214" text-anchor="middle" font-size="9.5" fill="white" opacity="0.85">multimoneda</text>
    <rect x="587" y="228" width="106" height="24" rx="8" fill="white" opacity="0.2"/>
    <text x="640" y="244" text-anchor="middle" font-size="9" fill="white" font-weight="600">4. Publicar Asiento</text>
  </g>

  <!-- ── ARROW 4 ── -->
  <g class="arr4">
    <line x1="709" y1="175" x2="735" y2="175" stroke="#94a3b8" stroke-width="2.5"/>
    <polygon points="732,170 740,175 732,180" fill="#94a3b8"/>
    <circle r="4" fill="#fbbf24" opacity="0.8">
      <animateMotion dur="1.5s" repeatCount="indefinite" begin="1.9s">
        <mpath href="#arr4path"/>
      </animateMotion>
    </circle>
    <path id="arr4path" d="M709,175 L740,175" fill="none"/>
  </g>

  <!-- ── CARD 5: Pago + Dashboard ── -->
  <g class="card5" filter="url(#shadow)">
    <rect x="742" y="90" width="130" height="170" rx="14" fill="url(#g5)"/>
    <circle cx="807" cy="138" r="30" fill="white" opacity="0.2"/>
    <g class="pulse" transform="translate(807,138)" style="animation-delay:1.6s">
      <!-- Coin/payment icon -->
      <circle r="20" fill="white" opacity="0.95"/>
      <text x="0" y="7" text-anchor="middle" font-size="20" fill="#db2777" font-weight="900">Q</text>
    </g>
    <text x="807" y="185" text-anchor="middle" font-size="11" font-weight="700" fill="white">PAGO</text>
    <text x="807" y="200" text-anchor="middle" font-size="9.5" fill="white" opacity="0.85">Wizard de pago</text>
    <text x="807" y="214" text-anchor="middle" font-size="9.5" fill="white" opacity="0.85">+ Dashboard KPIs</text>
    <rect x="754" y="228" width="106" height="24" rx="8" fill="white" opacity="0.2"/>
    <text x="807" y="244" text-anchor="middle" font-size="9" fill="white" font-weight="600">5. Registrar Pago</text>
  </g>

  <!-- ── Badge "✓ PAGADO" pops in last ── -->
  <g class="badge" transform="translate(807,108)">
    <circle r="14" fill="#10b981"/>
    <text x="0" y="5" text-anchor="middle" font-size="14" fill="white" font-weight="800">✓</text>
  </g>

  <!-- Footer -->
  <rect x="0" y="276" width="900" height="24" rx="0" fill="#1e293b" opacity="0.06"/>
  <text x="450" y="292" text-anchor="middle" font-size="9.5" fill="#64748b" font-weight="500">
    KONTAXES · Gestión Profesional de Gastos · Odoo 19 · Community &amp; Enterprise
  </text>
</svg>
