<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>KTX Liquidaciones — Gestión Avanzada de Gastos</title>
  <style>
    /* ════════════════════════════════════════ RESET */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { scroll-behavior: smooth; }
    body {
      font-family: system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif;
      background: #f8f5ff;
      color: #3d2d5c;
      line-height: 1.6;
      overflow-x: hidden;
    }
    .container { max-width: 980px; margin: 0 auto; padding: 0 20px; }

    /* ════════════════════════════════════════ KEYFRAMES */
    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(28px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
      from { opacity: 0; }
      to   { opacity: 1; }
    }
    @keyframes slideRight {
      from { opacity: 0; transform: translateX(-30px); }
      to   { opacity: 1; transform: translateX(0); }
    }
    @keyframes pulse {
      0%, 100% { transform: scale(1); }
      50%      { transform: scale(1.08); }
    }
    @keyframes floatY {
      0%, 100% { transform: translateY(0); }
      50%      { transform: translateY(-8px); }
    }
    @keyframes shimmer {
      0%   { background-position: -200% center; }
      100% { background-position: 200% center; }
    }
    @keyframes barGrow {
      from { width: 0; }
      to   { width: var(--bar-w); }
    }
    @keyframes flowDot {
      0%   { offset-distance: 0%; opacity: 0; }
      10%  { opacity: 1; }
      90%  { opacity: 1; }
      100% { offset-distance: 100%; opacity: 0; }
    }
    @keyframes popIn {
      from { opacity: 0; transform: scale(0.5); }
      60%  { opacity: 1; transform: scale(1.1); }
      to   { opacity: 1; transform: scale(1); }
    }
    @keyframes rotate {
      from { transform: rotate(0deg); }
      to   { transform: rotate(360deg); }
    }
    @keyframes dash {
      from { stroke-dashoffset: 1000; }
      to   { stroke-dashoffset: 0; }
    }

    /* Scroll-triggered classes use plain @keyframes (App Store description disables JS) */
    .anim-up   { animation: fadeUp 0.8s ease forwards; }
    .anim-in   { animation: fadeIn 0.8s ease forwards; }

    /* ════════════════════════════════════════ HERO */
    .hero {
      position: relative;
      background:
        radial-gradient(circle at 15% 30%, #f0e4ff 0%, transparent 50%),
        radial-gradient(circle at 85% 70%, #d4f4e7 0%, transparent 50%),
        linear-gradient(135deg, #f5eeff 0%, #eaf8ff 100%);
      border-bottom: 2px solid #e8d5f5;
      padding: 64px 20px 56px;
      text-align: center;
      overflow: hidden;
    }
    .hero::before, .hero::after {
      content: '';
      position: absolute;
      border-radius: 50%;
      opacity: 0.18;
      animation: floatY 7s ease-in-out infinite;
    }
    .hero::before {
      width: 180px; height: 180px;
      top: -40px; right: -40px;
      background: linear-gradient(135deg, #c8b4e8, #a090d0);
    }
    .hero::after {
      width: 140px; height: 140px;
      bottom: -30px; left: -30px;
      background: linear-gradient(135deg, #a8e6d4, #6dcfb8);
      animation-delay: -3s;
    }
    .hero-content { position: relative; z-index: 1; animation: fadeUp 0.9s ease; }
    .hero-badge {
      display: inline-block;
      background: linear-gradient(90deg, #c8b4e8, #a8e6d4, #b8d8f0);
      background-size: 200% 100%;
      animation: shimmer 4s linear infinite;
      color: #fff;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      padding: 5px 20px;
      border-radius: 99px;
      margin-bottom: 20px;
      box-shadow: 0 4px 12px rgba(168,140,210,0.3);
    }
    .hero h1 {
      font-size: 2.6rem;
      font-weight: 800;
      color: #4a2d8a;
      margin-bottom: 14px;
      line-height: 1.15;
      letter-spacing: -0.5px;
    }
    .hero h1 span {
      background: linear-gradient(90deg, #5cc8a8, #4a9ec8);
      -webkit-background-clip: text;
      background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .hero p.tagline {
      font-size: 1.15rem;
      color: #6b5490;
      max-width: 680px;
      margin: 0 auto 28px;
    }
    .hero-meta {
      display: flex;
      justify-content: center;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 30px;
    }
    .hero-chip {
      background: rgba(255,255,255,0.85);
      backdrop-filter: blur(8px);
      border: 1.5px solid #e0d0f8;
      border-radius: 99px;
      padding: 7px 18px;
      font-size: 13px;
      color: #6b5490;
      font-weight: 600;
      transition: all 0.25s ease;
    }
    .hero-chip:hover {
      transform: translateY(-2px);
      background: #fff;
      box-shadow: 0 6px 18px rgba(168,140,210,0.25);
      color: #4a2d8a;
    }
    .hero-banner {
      margin-top: 24px;
      border-radius: 18px;
      overflow: hidden;
      box-shadow: 0 12px 40px rgba(74,45,138,0.18);
      max-width: 940px;
      margin-left: auto;
      margin-right: auto;
      transition: transform 0.3s ease;
    }
    .hero-banner:hover { transform: translateY(-4px); box-shadow: 0 18px 48px rgba(74,45,138,0.25); }
    .hero-banner img { width: 100%; display: block; }

    /* ════════════════════════════════════════ SECTIONS */
    section { padding: 60px 0; animation: fadeUp 0.9s ease backwards; }
    section + section { border-top: 1.5px solid #ede4fa; }
    .section-label {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: #a88cd0;
      margin-bottom: 6px;
    }
    .section-title {
      font-size: 1.8rem;
      font-weight: 800;
      color: #4a2d8a;
      margin-bottom: 10px;
      letter-spacing: -0.5px;
    }
    .section-sub {
      color: #7b6aaa;
      font-size: 1rem;
      margin-bottom: 36px;
      max-width: 640px;
    }

    /* ════════════════════════════════════════ OVERVIEW */
    .overview-card {
      background: #fff;
      border-radius: 20px;
      box-shadow: 0 6px 28px rgba(168,140,210,0.13);
      padding: 36px 40px;
      display: flex;
      gap: 32px;
      align-items: flex-start;
      position: relative;
      overflow: hidden;
    }
    .overview-card::before {
      content: '';
      position: absolute;
      top: 0; left: 0;
      width: 6px;
      height: 100%;
      background: linear-gradient(180deg, #c8b4e8, #a8e6d4);
    }
    .overview-icon {
      flex-shrink: 0;
      width: 76px;
      height: 76px;
      animation: floatY 5s ease-in-out infinite;
    }
    .overview-card p {
      color: #5a4880;
      font-size: 1.02rem;
      line-height: 1.75;
    }
    .overview-card p strong { color: #4a2d8a; }

    /* ════════════════════════════════════════ INTERACTIVE WORKFLOW */
    .workflow {
      background: linear-gradient(135deg, #faf6ff, #f0fbf7);
      border-radius: 24px;
      padding: 40px 28px 32px;
      box-shadow: 0 6px 32px rgba(168,140,210,0.12);
      position: relative;
      overflow: hidden;
    }
    .workflow-svg {
      width: 100%;
      max-width: 920px;
      height: auto;
      display: block;
      margin: 0 auto 20px;
    }
    .workflow-detail-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
      margin-top: 24px;
    }
    .wf-detail {
      background: #fff;
      border-radius: 12px;
      padding: 16px 14px;
      border-top: 4px solid;
      transition: all 0.28s ease;
      cursor: default;
      animation: fadeUp 0.5s ease backwards;
    }
    .wf-detail:nth-child(1) { animation-delay: 0.05s; border-color: #7ec8e8; }
    .wf-detail:nth-child(2) { animation-delay: 0.15s; border-color: #a090d0; }
    .wf-detail:nth-child(3) { animation-delay: 0.25s; border-color: #6dcfb8; }
    .wf-detail:nth-child(4) { animation-delay: 0.35s; border-color: #e8a070; }
    .wf-detail:nth-child(5) { animation-delay: 0.45s; border-color: #9acd70; }
    .wf-detail:nth-child(6) { animation-delay: 0.55s; border-color: #4dc98a; }
    .wf-detail:nth-child(7) { animation-delay: 0.65s; border-color: #60a8e8; }
    .wf-detail:hover {
      transform: translateY(-4px) scale(1.02);
      box-shadow: 0 8px 22px rgba(168,140,210,0.2);
    }
    .wf-detail .wf-num {
      display: inline-block;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      color: #fff;
      font-size: 11px;
      font-weight: 800;
      text-align: center;
      line-height: 22px;
      margin-right: 6px;
    }
    .wf-detail:nth-child(1) .wf-num { background: #7ec8e8; }
    .wf-detail:nth-child(2) .wf-num { background: #a090d0; }
    .wf-detail:nth-child(3) .wf-num { background: #6dcfb8; }
    .wf-detail:nth-child(4) .wf-num { background: #e8a070; }
    .wf-detail:nth-child(5) .wf-num { background: #9acd70; }
    .wf-detail:nth-child(6) .wf-num { background: #4dc98a; }
    .wf-detail:nth-child(7) .wf-num { background: #60a8e8; }
    .wf-detail h5 {
      font-size: 13px;
      font-weight: 700;
      color: #4a2d8a;
      margin-bottom: 6px;
    }
    .wf-detail p { font-size: 12px; color: #7b6aaa; line-height: 1.5; }

    /* ════════════════════════════════════════ FEATURE CARDS */
    .features-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
      gap: 20px;
    }
    .feature-card {
      background: #fff;
      border-radius: 18px;
      padding: 26px 22px;
      box-shadow: 0 3px 18px rgba(168,140,210,0.10);
      border: 1.5px solid #f0e8ff;
      transition: all 0.3s cubic-bezier(0.2,0.8,0.2,1);
      position: relative;
      overflow: hidden;
      animation: fadeUp 0.6s ease backwards;
    }
    .feature-card:nth-child(1)  { animation-delay: 0.05s; }
    .feature-card:nth-child(2)  { animation-delay: 0.10s; }
    .feature-card:nth-child(3)  { animation-delay: 0.15s; }
    .feature-card:nth-child(4)  { animation-delay: 0.20s; }
    .feature-card:nth-child(5)  { animation-delay: 0.25s; }
    .feature-card:nth-child(6)  { animation-delay: 0.30s; }
    .feature-card:nth-child(7)  { animation-delay: 0.35s; }
    .feature-card:nth-child(8)  { animation-delay: 0.40s; }
    .feature-card:nth-child(9)  { animation-delay: 0.45s; }
    .feature-card:nth-child(10) { animation-delay: 0.50s; }
    .feature-card::after {
      content: '';
      position: absolute;
      top: 0; left: 0;
      width: 0;
      height: 4px;
      background: linear-gradient(90deg, #c8b4e8, #a8e6d4);
      transition: width 0.4s ease;
    }
    .feature-card:hover {
      transform: translateY(-6px);
      box-shadow: 0 14px 36px rgba(168,140,210,0.22);
      border-color: #d8c4f0;
    }
    .feature-card:hover::after { width: 100%; }
    .feature-icon {
      width: 50px;
      height: 50px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 16px;
      transition: transform 0.3s ease;
    }
    .feature-card:hover .feature-icon { transform: scale(1.08) rotate(-3deg); }
    .feature-card h3 {
      font-size: 15.5px;
      font-weight: 700;
      color: #4a2d8a;
      margin-bottom: 8px;
    }
    .feature-card p {
      font-size: 13px;
      color: #7b6aaa;
      line-height: 1.6;
    }

    /* ════════════════════════════════════════ DASHBOARD PREVIEW */
    .dashboard-preview {
      background: #fff;
      border-radius: 20px;
      padding: 32px;
      box-shadow: 0 8px 32px rgba(168,140,210,0.15);
      position: relative;
      overflow: hidden;
    }
    .dash-kpis {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 14px;
      margin-bottom: 24px;
    }
    .dash-kpi {
      padding: 18px 16px;
      border-radius: 14px;
      color: #fff;
      position: relative;
      overflow: hidden;
      animation: popIn 0.6s ease backwards;
    }
    .dash-kpi:nth-child(1) { background: linear-gradient(135deg, #c8b4e8, #a090d0); animation-delay: 0.1s; }
    .dash-kpi:nth-child(2) { background: linear-gradient(135deg, #f5c6a0, #e8a070); animation-delay: 0.2s; }
    .dash-kpi:nth-child(3) { background: linear-gradient(135deg, #a8e6d4, #6dcfb8); animation-delay: 0.3s; }
    .dash-kpi:nth-child(4) { background: linear-gradient(135deg, #b8d8f0, #7ab0e0); animation-delay: 0.4s; }
    .dash-kpi-num {
      font-size: 1.9rem;
      font-weight: 800;
      line-height: 1;
      margin-bottom: 4px;
    }
    .dash-kpi-lbl {
      font-size: 11px;
      opacity: 0.9;
      font-weight: 600;
      letter-spacing: 0.5px;
      text-transform: uppercase;
    }
    .dash-kpi::after {
      content: '';
      position: absolute;
      bottom: -20px; right: -20px;
      width: 80px; height: 80px;
      background: rgba(255,255,255,0.12);
      border-radius: 50%;
    }

    /* Chart inside dashboard preview */
    .dash-chart {
      display: flex;
      align-items: flex-end;
      gap: 12px;
      height: 160px;
      padding: 14px 0 0;
      border-top: 1px dashed #e8dffa;
    }
    .dash-bar {
      flex: 1;
      background: linear-gradient(180deg, #c8b4e8, #a090d0);
      border-radius: 6px 6px 0 0;
      position: relative;
      animation: barGrow 1.4s cubic-bezier(0.2,0.8,0.2,1) backwards;
      transform-origin: bottom;
      min-height: 12px;
    }
    .dash-bar::after {
      content: attr(data-label);
      position: absolute;
      bottom: -22px;
      left: 0; right: 0;
      text-align: center;
      font-size: 10px;
      font-weight: 600;
      color: #9080b0;
    }

    /* ════════════════════════════════════════ CONFIG */
    .config-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    @media (max-width: 600px) { .config-grid { grid-template-columns: 1fr; } }
    .config-card {
      background: linear-gradient(135deg, #f8f4ff, #f0fbf7);
      border: 1.5px solid #e4d8f8;
      border-radius: 16px;
      padding: 24px 22px;
      transition: all 0.3s ease;
    }
    .config-card:hover {
      transform: translateY(-3px);
      box-shadow: 0 10px 28px rgba(168,140,210,0.18);
    }
    .config-card h4 {
      font-size: 15px;
      font-weight: 700;
      color: #4a2d8a;
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .config-card p {
      font-size: 13.5px;
      color: #7b6aaa;
      line-height: 1.6;
    }

    /* ════════════════════════════════════════ TIME-SAVINGS CHART */
    .savings-list { display: flex; flex-direction: column; gap: 18px; }
    .savings-row {
      background: #fff;
      border-radius: 14px;
      padding: 18px 20px;
      box-shadow: 0 3px 14px rgba(168,140,210,0.10);
      animation: slideRight 0.7s ease backwards;
    }
    .savings-row:nth-child(1) { animation-delay: 0.05s; }
    .savings-row:nth-child(2) { animation-delay: 0.15s; }
    .savings-row:nth-child(3) { animation-delay: 0.25s; }
    .savings-row:nth-child(4) { animation-delay: 0.35s; }
    .savings-row:nth-child(5) { animation-delay: 0.45s; }
    .savings-row:nth-child(6) { animation-delay: 0.55s; }
    .savings-row.total {
      background: linear-gradient(135deg, #4a2d8a, #2d7a6a);
      color: #fff;
      animation-delay: 0.7s;
    }
    .savings-task {
      font-size: 14px;
      font-weight: 700;
      color: #4a2d8a;
      margin-bottom: 12px;
    }
    .savings-row.total .savings-task { color: #fff; font-size: 16px; }
    .savings-bars { display: flex; flex-direction: column; gap: 6px; }
    .savings-bar-row {
      display: grid;
      grid-template-columns: 92px 1fr 82px;
      align-items: center;
      gap: 12px;
    }
    .savings-bar-lbl {
      font-size: 12px;
      font-weight: 600;
      color: #9080b0;
    }
    .savings-row.total .savings-bar-lbl { color: rgba(255,255,255,0.85); }
    .savings-bar-track {
      height: 14px;
      background: #f0e8ff;
      border-radius: 7px;
      overflow: hidden;
      position: relative;
    }
    .savings-row.total .savings-bar-track { background: rgba(255,255,255,0.15); }
    .savings-bar-fill {
      height: 100%;
      border-radius: 7px;
      animation: barGrow 1.4s cubic-bezier(0.2,0.8,0.2,1) backwards;
      animation-delay: 0.4s;
    }
    .savings-bar-fill.manual { background: linear-gradient(90deg, #f5a8a8, #e07070); }
    .savings-bar-fill.ktx    { background: linear-gradient(90deg, #a8e6d4, #4dc98a); }
    .savings-bar-fill.total-manual { background: linear-gradient(90deg, #ffb6b6, #ff8a8a); }
    .savings-bar-fill.total-ktx    { background: linear-gradient(90deg, #b6f5d4, #6ee0a0); }
    .savings-bar-val {
      font-size: 12.5px;
      font-weight: 700;
      color: #5a4880;
      text-align: right;
    }
    .savings-row.total .savings-bar-val { color: #fff; }
    .savings-badge {
      display: inline-block;
      background: linear-gradient(90deg, #c8b4e8, #a8e6d4);
      color: #fff;
      font-size: 12px;
      font-weight: 700;
      padding: 4px 12px;
      border-radius: 99px;
      margin-top: 8px;
    }
    .savings-row.total .savings-badge {
      background: rgba(255,255,255,0.25);
      color: #fff;
      font-size: 14px;
      padding: 6px 16px;
    }

    /* ════════════════════════════════════════ REQUIREMENTS */
    .req-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
    }
    .req-pill {
      background: #fff;
      border: 1.5px solid #d8ccf0;
      border-radius: 99px;
      padding: 11px 22px;
      font-size: 14px;
      color: #5a4880;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 10px;
      transition: all 0.25s ease;
    }
    .req-pill:hover {
      transform: translateY(-2px);
      border-color: #c8b4e8;
      box-shadow: 0 6px 16px rgba(168,140,210,0.18);
    }
    .req-dot {
      width: 10px; height: 10px;
      border-radius: 50%;
      background: linear-gradient(135deg, #c8b4e8, #7ed9a0);
      flex-shrink: 0;
      animation: pulse 2s ease-in-out infinite;
    }

    /* ════════════════════════════════════════ FOOTER */
    footer {
      background: linear-gradient(135deg, #4a2d8a, #2d7a6a);
      color: #e8d5f5;
      text-align: center;
      padding: 42px 20px;
      margin-top: 12px;
      position: relative;
      overflow: hidden;
    }
    footer::before, footer::after {
      content: '';
      position: absolute;
      border-radius: 50%;
      opacity: 0.12;
    }
    footer::before {
      width: 200px; height: 200px;
      top: -80px; left: -50px;
      background: #fff;
    }
    footer::after {
      width: 150px; height: 150px;
      bottom: -60px; right: -40px;
      background: #fff;
    }
    footer strong { color: #fff; font-size: 18px; }
    footer p { font-size: 14px; opacity: 0.85; margin-top: 8px; position: relative; }

    /* ════════════════════════════════════════ RESPONSIVE */
    @media (max-width: 720px) {
      .hero h1 { font-size: 1.85rem; }
      .hero p.tagline { font-size: 1rem; }
      .section-title { font-size: 1.4rem; }
      .overview-card { flex-direction: column; padding: 26px; }
      .features-grid { grid-template-columns: 1fr; }
      .savings-bar-row { grid-template-columns: 80px 1fr 64px; gap: 8px; }
    }
  </style>
</head>
<body>

<!-- ═══════════════════════════════════════════ HERO -->
<div class="hero">
  <div class="hero-content">
    <div class="hero-badge">Odoo 19 · Enterprise &amp; Community</div>
    <h1>KTX <span>Liquidaciones</span><br/>Gestión Avanzada de Gastos</h1>
    <p class="tagline">Automatiza el flujo completo de liquidación de gastos de empleados — desde el registro hasta el pago, con asientos contables automáticos, multimoneda y control por aprobador.</p>
    <div class="hero-meta">
      <span class="hero-chip">Multimoneda</span>
      <span class="hero-chip">Multiempresa</span>
      <span class="hero-chip">Asientos Automáticos</span>
      <span class="hero-chip">Actividades Odoo</span>
      <span class="hero-chip">Dashboard KPIs</span>
      <span class="hero-chip">Export Excel</span>
    </div>
    <div class="hero-banner">
      <img src="banner_animated.svg" alt="Flujo de Liquidaciones" loading="eager"/>
    </div>
  </div>
</div>

<div class="container">

  <!-- ═══════════════════════════════════════ SECTION 1: Overview -->
  <section>
    <div class="section-label">Descripción</div>
    <div class="section-title">¿Qué hace este módulo?</div>
    <div class="overview-card">
      <svg class="overview-icon" viewBox="0 0 76 76" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="76" height="76" rx="20" fill="#f0e8ff"/>
        <rect x="17" y="15" width="32" height="46" rx="5" fill="#ddc8f8"/>
        <rect x="21" y="23" width="18" height="3" rx="1.5" fill="#b8dff0"/>
        <rect x="21" y="30" width="22" height="2.5" rx="1.25" fill="#d0e8f8"/>
        <rect x="21" y="36" width="20" height="2.5" rx="1.25" fill="#d0e8f8"/>
        <rect x="21" y="42" width="22" height="2.5" rx="1.25" fill="#d0e8f8"/>
        <rect x="21" y="48" width="16" height="2.5" rx="1.25" fill="#d0e8f8"/>
        <circle cx="56" cy="30" r="13" fill="#7ed9a0">
          <animate attributeName="r" values="13;15;13" dur="2.5s" repeatCount="indefinite"/>
        </circle>
        <polyline points="50,30 54,35 63,24" stroke="white" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
      </svg>
      <div>
        <p><strong>KTX Liquidaciones</strong> es un módulo para Odoo 19 que implementa un flujo completo y controlado de liquidación de gastos para empleados. Permite registrar gastos individuales, agruparlos en una liquidación, someterlos a un proceso de aprobación con múltiples niveles (Confirmar → Autorizar → Publicar), y finalmente registrar el pago mediante un wizard dedicado.</p>
        <br/>
        <p>El módulo genera <strong>asientos contables automáticos</strong> al publicar, soporta <strong>multimoneda y multiempresa</strong> (con asignación intercompañía de la empresa pagadora), envía <strong>notificaciones y actividades Odoo</strong> en cada cambio de estado, y ofrece un <strong>tablero con KPIs</strong> en tiempo real. Los datos se pueden exportar a <strong>Excel</strong> con un solo clic.</p>
      </div>
    </div>
  </section>

  <!-- ═══════════════════════════════════════ SECTION 2: Interactive Workflow -->
  <section>
    <div class="section-label">Proceso</div>
    <div class="section-title">Flujo de trabajo interactivo</div>
    <p class="section-sub">Siete etapas con trazabilidad completa, notificaciones automáticas y asientos contables generados al publicar. Pasa el cursor sobre cada nodo para ver el detalle.</p>

    <div class="workflow">
      <!-- ────────── Interactive SVG Workflow ────────── -->
      <svg class="workflow-svg" viewBox="0 0 920 220" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="path-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"   style="stop-color:#7ec8e8"/>
            <stop offset="16%"  style="stop-color:#a090d0"/>
            <stop offset="33%"  style="stop-color:#6dcfb8"/>
            <stop offset="50%"  style="stop-color:#e8a070"/>
            <stop offset="66%"  style="stop-color:#9acd70"/>
            <stop offset="83%"  style="stop-color:#4dc98a"/>
            <stop offset="100%" style="stop-color:#60a8e8"/>
          </linearGradient>
          <filter id="node-shadow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#a090d0" flood-opacity="0.35"/>
          </filter>

          <!-- 1: Receipt -->
          <symbol id="icon-receipt" viewBox="-16 -16 32 32">
            <rect x="-10" y="-12" width="20" height="24" rx="3" fill="#fff"/>
            <line x1="-6" y1="-7" x2="6" y2="-7" stroke="#5aa0c8" stroke-width="2" stroke-linecap="round"/>
            <line x1="-6" y1="-2" x2="6" y2="-2" stroke="#5aa0c8" stroke-width="2" stroke-linecap="round"/>
            <line x1="-6" y1="3"  x2="2" y2="3"  stroke="#5aa0c8" stroke-width="2" stroke-linecap="round"/>
          </symbol>
          <!-- 2: Stack -->
          <symbol id="icon-stack" viewBox="-16 -16 32 32">
            <rect x="-9" y="-9" width="18" height="14" rx="2" fill="#fff" opacity="0.7"/>
            <rect x="-9" y="-5" width="18" height="14" rx="2" fill="#fff"/>
            <line x1="-5" y1="0" x2="5" y2="0" stroke="#806ba8" stroke-width="2" stroke-linecap="round"/>
            <line x1="-5" y1="4" x2="2" y2="4" stroke="#806ba8" stroke-width="2" stroke-linecap="round"/>
          </symbol>
          <!-- 3: Check -->
          <symbol id="icon-check" viewBox="-16 -16 32 32">
            <circle r="11" fill="#fff"/>
            <polyline points="-5,1 -1,5 6,-3" stroke="#4ba590" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
          </symbol>
          <!-- 4: Shield -->
          <symbol id="icon-shield" viewBox="-16 -16 32 32">
            <path d="M0 -11 L9 -7 L9 2 Q9 10 0 13 Q-9 10 -9 2 L-9 -7 Z" fill="#fff"/>
            <polyline points="-4,1 -1,4 5,-3" stroke="#c87a40" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
          </symbol>
          <!-- 5: Document with check -->
          <symbol id="icon-publish" viewBox="-16 -16 32 32">
            <rect x="-9" y="-11" width="16" height="22" rx="2" fill="#fff"/>
            <line x1="-5" y1="-6" x2="3" y2="-6" stroke="#7aa848" stroke-width="2" stroke-linecap="round"/>
            <line x1="-5" y1="-1" x2="3" y2="-1" stroke="#7aa848" stroke-width="2" stroke-linecap="round"/>
            <circle cx="7" cy="6" r="5" fill="#7aa848"/>
            <polyline points="5,6 6.5,7.5 9.5,4.5" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
          </symbol>
          <!-- 6: Coin/Pay -->
          <symbol id="icon-coin" viewBox="-16 -16 32 32">
            <circle r="11" fill="#fff"/>
            <text x="0" y="4" text-anchor="middle" font-size="13" font-weight="900" fill="#3a9670">Q</text>
          </symbol>
          <!-- 7: Star/Done -->
          <symbol id="icon-done" viewBox="-16 -16 32 32">
            <circle r="11" fill="#fff"/>
            <path d="M0,-7 L2,-2 L7,-2 L3,1.5 L4.5,6.5 L0,3.5 L-4.5,6.5 L-3,1.5 L-7,-2 L-2,-2 Z" fill="#4090c8"/>
          </symbol>
        </defs>

        <!-- Background pill -->
        <rect x="20" y="80" width="880" height="6" rx="3" fill="#f0e8ff"/>

        <!-- Animated gradient path -->
        <path id="flow-path" d="M60,83 L860,83" stroke="url(#path-grad)" stroke-width="6" stroke-linecap="round"
              stroke-dasharray="1000" stroke-dashoffset="1000">
          <animate attributeName="stroke-dashoffset" from="1000" to="0" dur="2.2s" fill="freeze"/>
        </path>

        <!-- Three flowing dots traveling continuously -->
        <circle r="6" fill="#fff" stroke="#a090d0" stroke-width="2">
          <animateMotion dur="6s" repeatCount="indefinite" path="M60,83 L860,83" begin="2.2s"/>
        </circle>
        <circle r="6" fill="#fff" stroke="#6dcfb8" stroke-width="2">
          <animateMotion dur="6s" repeatCount="indefinite" path="M60,83 L860,83" begin="4.2s"/>
        </circle>
        <circle r="6" fill="#fff" stroke="#e8a070" stroke-width="2">
          <animateMotion dur="6s" repeatCount="indefinite" path="M60,83 L860,83" begin="6.2s"/>
        </circle>

        <!-- ─── 7 nodes positioned along the path ─── -->
        <!-- Node 1 -->
        <g transform="translate(60,83)" filter="url(#node-shadow)">
          <circle r="32" fill="#7ec8e8"/>
          <circle r="32" fill="#7ec8e8" opacity="0.4">
            <animate attributeName="r" values="32;38;32" dur="3s" repeatCount="indefinite" begin="0s"/>
            <animate attributeName="opacity" values="0.4;0;0.4" dur="3s" repeatCount="indefinite" begin="0s"/>
          </circle>
          <use href="#icon-receipt"/>
          <text y="58" text-anchor="middle" font-size="12" font-weight="800" fill="#4a2d8a">1. Gastos</text>
          <text y="74" text-anchor="middle" font-size="10" fill="#7b6aaa">Registrar</text>
        </g>

        <!-- Node 2 -->
        <g transform="translate(193,83)" filter="url(#node-shadow)">
          <circle r="32" fill="#a090d0"/>
          <circle r="32" fill="#a090d0" opacity="0.4">
            <animate attributeName="r" values="32;38;32" dur="3s" repeatCount="indefinite" begin="0.5s"/>
            <animate attributeName="opacity" values="0.4;0;0.4" dur="3s" repeatCount="indefinite" begin="0.5s"/>
          </circle>
          <use href="#icon-stack"/>
          <text y="58" text-anchor="middle" font-size="12" font-weight="800" fill="#4a2d8a">2. Staging</text>
          <text y="74" text-anchor="middle" font-size="10" fill="#7b6aaa">Agrupar</text>
        </g>

        <!-- Node 3 -->
        <g transform="translate(326,83)" filter="url(#node-shadow)">
          <circle r="32" fill="#6dcfb8"/>
          <circle r="32" fill="#6dcfb8" opacity="0.4">
            <animate attributeName="r" values="32;38;32" dur="3s" repeatCount="indefinite" begin="1.0s"/>
            <animate attributeName="opacity" values="0.4;0;0.4" dur="3s" repeatCount="indefinite" begin="1.0s"/>
          </circle>
          <use href="#icon-check"/>
          <text y="58" text-anchor="middle" font-size="12" font-weight="800" fill="#4a2d8a">3. Confirmar</text>
          <text y="74" text-anchor="middle" font-size="10" fill="#7b6aaa">Empleado</text>
        </g>

        <!-- Node 4 -->
        <g transform="translate(459,83)" filter="url(#node-shadow)">
          <circle r="32" fill="#e8a070"/>
          <circle r="32" fill="#e8a070" opacity="0.4">
            <animate attributeName="r" values="32;38;32" dur="3s" repeatCount="indefinite" begin="1.5s"/>
            <animate attributeName="opacity" values="0.4;0;0.4" dur="3s" repeatCount="indefinite" begin="1.5s"/>
          </circle>
          <use href="#icon-shield"/>
          <text y="58" text-anchor="middle" font-size="12" font-weight="800" fill="#4a2d8a">4. Autorizar</text>
          <text y="74" text-anchor="middle" font-size="10" fill="#7b6aaa">Aprobador</text>
        </g>

        <!-- Node 5 -->
        <g transform="translate(592,83)" filter="url(#node-shadow)">
          <circle r="32" fill="#9acd70"/>
          <circle r="32" fill="#9acd70" opacity="0.4">
            <animate attributeName="r" values="32;38;32" dur="3s" repeatCount="indefinite" begin="2.0s"/>
            <animate attributeName="opacity" values="0.4;0;0.4" dur="3s" repeatCount="indefinite" begin="2.0s"/>
          </circle>
          <use href="#icon-publish"/>
          <text y="58" text-anchor="middle" font-size="12" font-weight="800" fill="#4a2d8a">5. Publicar</text>
          <text y="74" text-anchor="middle" font-size="10" fill="#7b6aaa">Asiento auto</text>
        </g>

        <!-- Node 6 -->
        <g transform="translate(725,83)" filter="url(#node-shadow)">
          <circle r="32" fill="#4dc98a"/>
          <circle r="32" fill="#4dc98a" opacity="0.4">
            <animate attributeName="r" values="32;38;32" dur="3s" repeatCount="indefinite" begin="2.5s"/>
            <animate attributeName="opacity" values="0.4;0;0.4" dur="3s" repeatCount="indefinite" begin="2.5s"/>
          </circle>
          <use href="#icon-coin"/>
          <text y="58" text-anchor="middle" font-size="12" font-weight="800" fill="#4a2d8a">6. Pago</text>
          <text y="74" text-anchor="middle" font-size="10" fill="#7b6aaa">Wizard</text>
        </g>

        <!-- Node 7 -->
        <g transform="translate(858,83)" filter="url(#node-shadow)">
          <circle r="32" fill="#60a8e8"/>
          <circle r="32" fill="#60a8e8" opacity="0.4">
            <animate attributeName="r" values="32;38;32" dur="3s" repeatCount="indefinite" begin="3.0s"/>
            <animate attributeName="opacity" values="0.4;0;0.4" dur="3s" repeatCount="indefinite" begin="3.0s"/>
          </circle>
          <use href="#icon-done"/>
          <text y="58" text-anchor="middle" font-size="12" font-weight="800" fill="#4a2d8a">7. Pagada</text>
          <text y="74" text-anchor="middle" font-size="10" fill="#7b6aaa">KPIs ↑</text>
        </g>

        <!-- Top labels with sequential fade-in -->
        <g font-size="11" font-weight="700" fill="#9080b0" text-anchor="middle">
          <text x="60"  y="35" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.3s" begin="0.1s" fill="freeze"/>EMPLEADO</text>
          <text x="193" y="35" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.3s" begin="0.4s" fill="freeze"/>EMPLEADO</text>
          <text x="326" y="35" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.3s" begin="0.7s" fill="freeze"/>EMPLEADO</text>
          <text x="459" y="35" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.3s" begin="1.0s" fill="freeze"/>APROBADOR</text>
          <text x="592" y="35" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.3s" begin="1.3s" fill="freeze"/>CONTADOR</text>
          <text x="725" y="35" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.3s" begin="1.6s" fill="freeze"/>TESORERÍA</text>
          <text x="858" y="35" opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.3s" begin="1.9s" fill="freeze"/>SISTEMA</text>
        </g>
      </svg>

      <!-- ────────── Detail cards under workflow ────────── -->
      <div class="workflow-detail-grid">
        <div class="wf-detail"><h5><span class="wf-num">1</span>Agregar Gastos</h5><p>El empleado registra cada gasto con monto, moneda, fecha y comprobante adjunto.</p></div>
        <div class="wf-detail"><h5><span class="wf-num">2</span>Staging</h5><p>Los gastos quedan agrupados como pendientes de liquidar. Visibles para seleccionarlos.</p></div>
        <div class="wf-detail"><h5><span class="wf-num">3</span>Confirmar</h5><p>Empleado consolida los gastos en una liquidación y la envía para aprobación.</p></div>
        <div class="wf-detail"><h5><span class="wf-num">4</span>Autorizar</h5><p>Solo el aprobador designado puede aprobar. Recibe actividad Odoo y email.</p></div>
        <div class="wf-detail"><h5><span class="wf-num">5</span>Publicar</h5><p>Se genera el asiento contable automático con débitos a las cuentas originales.</p></div>
        <div class="wf-detail"><h5><span class="wf-num">6</span>Registrar Pago</h5><p>Wizard de pago con diario, fecha, monto y manejo de diferencia (write-off).</p></div>
        <div class="wf-detail"><h5><span class="wf-num">7</span>Pagada</h5><p>Al conciliar con extracto bancario, la liquidación cierra y el dashboard se actualiza.</p></div>
      </div>
    </div>
  </section>

  <!-- ═══════════════════════════════════════ SECTION 3: Dashboard Preview -->
  <section>
    <div class="section-label">Tablero</div>
    <div class="section-title">Dashboard de KPIs en tiempo real</div>
    <p class="section-sub">Una vista consolidada del estado de tus liquidaciones, con métricas clave, gráficos por mes, top empleados y top proveedores.</p>

    <div class="dashboard-preview">
      <div class="dash-kpis">
        <div class="dash-kpi">
          <div class="dash-kpi-num">12</div>
          <div class="dash-kpi-lbl">Por Autorizar</div>
        </div>
        <div class="dash-kpi">
          <div class="dash-kpi-num">8</div>
          <div class="dash-kpi-lbl">Aprobadas</div>
        </div>
        <div class="dash-kpi">
          <div class="dash-kpi-num">Q 145K</div>
          <div class="dash-kpi-lbl">Pendiente Pago</div>
        </div>
        <div class="dash-kpi">
          <div class="dash-kpi-num">Q 892K</div>
          <div class="dash-kpi-lbl">Pagado Año</div>
        </div>
      </div>
      <div style="font-size:13px;font-weight:700;color:#4a2d8a;margin-bottom:8px;">📈 Gasto mensual — últimos 12 meses</div>
      <div class="dash-chart">
        <div class="dash-bar" style="--bar-w:100%; height:42%; animation-delay:0.5s;" data-label="Jun"></div>
        <div class="dash-bar" style="--bar-w:100%; height:58%; animation-delay:0.55s; background:linear-gradient(180deg,#a8e6d4,#6dcfb8);" data-label="Jul"></div>
        <div class="dash-bar" style="--bar-w:100%; height:48%; animation-delay:0.60s; background:linear-gradient(180deg,#f5c6a0,#e8a070);" data-label="Ago"></div>
        <div class="dash-bar" style="--bar-w:100%; height:72%; animation-delay:0.65s; background:linear-gradient(180deg,#b8d8f0,#7ab0e0);" data-label="Sep"></div>
        <div class="dash-bar" style="--bar-w:100%; height:62%; animation-delay:0.70s;" data-label="Oct"></div>
        <div class="dash-bar" style="--bar-w:100%; height:88%; animation-delay:0.75s; background:linear-gradient(180deg,#a8e6d4,#6dcfb8);" data-label="Nov"></div>
        <div class="dash-bar" style="--bar-w:100%; height:95%; animation-delay:0.80s; background:linear-gradient(180deg,#f5c6a0,#e8a070);" data-label="Dic"></div>
        <div class="dash-bar" style="--bar-w:100%; height:55%; animation-delay:0.85s; background:linear-gradient(180deg,#b8d8f0,#7ab0e0);" data-label="Ene"></div>
        <div class="dash-bar" style="--bar-w:100%; height:68%; animation-delay:0.90s;" data-label="Feb"></div>
        <div class="dash-bar" style="--bar-w:100%; height:78%; animation-delay:0.95s; background:linear-gradient(180deg,#a8e6d4,#6dcfb8);" data-label="Mar"></div>
        <div class="dash-bar" style="--bar-w:100%; height:82%; animation-delay:1.00s; background:linear-gradient(180deg,#f5c6a0,#e8a070);" data-label="Abr"></div>
        <div class="dash-bar" style="--bar-w:100%; height:90%; animation-delay:1.05s; background:linear-gradient(180deg,#b8d8f0,#7ab0e0);" data-label="May"></div>
      </div>
    </div>
  </section>

  <!-- ═══════════════════════════════════════ SECTION 4: Funcionalidades -->
  <section>
    <div class="section-label">Características</div>
    <div class="section-title">Funcionalidades principales</div>
    <p class="section-sub">Diez funcionalidades clave que cubren cada aspecto del ciclo de gastos corporativos.</p>

    <div class="features-grid">

      <div class="feature-card">
        <div class="feature-icon" style="background:#e8f5ff;">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="11" stroke="#60a8e8" stroke-width="2.2"/>
            <text x="14" y="18" text-anchor="middle" font-size="11" font-weight="bold" fill="#60a8e8">$€</text>
          </svg>
        </div>
        <h3>Multimoneda</h3>
        <p>Registra gastos en cualquier moneda. Tipo de cambio configurable por liquidación, conversión automática al asiento contable y nota de diferencial cambiario al pagar.</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon" style="background:#f0e8ff;">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect x="3" y="6" width="11" height="18" rx="2" fill="#c8b4e8"/>
            <rect x="14" y="9" width="11" height="15" rx="2" fill="#a090d0"/>
            <line x1="14" y1="12" x2="14" y2="24" stroke="white" stroke-width="1.5"/>
          </svg>
        </div>
        <h3>Multiempresa / Intercompañía</h3>
        <p>Asigna una empresa pagadora distinta a la del empleado. Ideal para grupos donde RRHH pertenece a una subsidiaria pero los pagos los realiza la matriz.</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon" style="background:#e8fff3;">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="11" r="5.5" fill="#7ed9a0"/>
            <path d="M5 24 Q5 17 14 17 Q23 17 23 24" fill="#a8e6d4"/>
            <circle cx="22" cy="8" r="4.5" fill="#4dc98a"/>
            <polyline points="19.5,8 21,9.5 24.5,6" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
          </svg>
        </div>
        <h3>Actividades Odoo + Email</h3>
        <p>En cada cambio de estado se crea una actividad y se envía email al aprobador o creador. La actividad incluye enlace directo a la liquidación correspondiente.</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon" style="background:#fff8e8;">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <path d="M14 3 L23 7 L23 15 Q23 22 14 25 Q5 22 5 15 L5 7 Z" fill="#f5c870"/>
            <polyline points="9,14 13,17 19,10" stroke="white" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
          </svg>
        </div>
        <h3>Restricción por Aprobador</h3>
        <p>Solo el aprobador designado puede aprobar o rechazar la liquidación. Evita conflictos de interés y garantiza el respeto de la cadena de aprobación.</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon" style="background:#f0fff8;">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect x="4" y="9" width="20" height="14" rx="3" fill="#a8e6d4"/>
            <rect x="10" y="5" width="8" height="6" rx="2" fill="#6dcfb8"/>
            <line x1="8" y1="15" x2="20" y2="15" stroke="white" stroke-width="1.8"/>
            <line x1="8" y1="19" x2="16" y2="19" stroke="white" stroke-width="1.8"/>
          </svg>
        </div>
        <h3>Wizard de Pago</h3>
        <p>Asistente guiado: diario, fecha, monto, referencia y manejo de diferencias. Crea el pago y reconcilia con el asiento de la liquidación.</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon" style="background:#fdf0ff;">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect x="4" y="4" width="20" height="20" rx="3" fill="#ddc8f8"/>
            <line x1="8" y1="10" x2="20" y2="10" stroke="#9060c0" stroke-width="1.8"/>
            <line x1="8" y1="14" x2="20" y2="14" stroke="#9060c0" stroke-width="1.8"/>
            <line x1="8" y1="18" x2="15" y2="18" stroke="#9060c0" stroke-width="1.8"/>
            <circle cx="21" cy="21" r="5" fill="#7ed9a0"/>
            <text x="21" y="24" text-anchor="middle" font-size="8" font-weight="bold" fill="white">✓</text>
          </svg>
        </div>
        <h3>Asiento Contable Automático</h3>
        <p>Al publicar, débito a las cuentas por pagar originales de cada factura y crédito unificado al partner del empleado. Multimoneda y multiempresa.</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon" style="background:#f0f8e8;">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect x="3" y="6" width="22" height="17" rx="2" fill="#c8e890"/>
            <line x1="7" y1="10" x2="20" y2="10" stroke="white" stroke-width="1.8"/>
            <line x1="7" y1="14" x2="17" y2="14" stroke="white" stroke-width="1.8"/>
            <line x1="7" y1="18" x2="13" y2="18" stroke="white" stroke-width="1.8"/>
            <rect x="15" y="15" width="9" height="6" rx="1.5" fill="#7ab840"/>
            <text x="19.5" y="19.5" text-anchor="middle" font-size="6" fill="white" font-weight="bold">XLS</text>
          </svg>
        </div>
        <h3>Export Excel</h3>
        <p>Exporta liquidaciones, gastos en staging o reportes con un clic. Incluye empleado, moneda, estado, aprobador, empresa pagadora y fechas.</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon" style="background:#e8f0ff;">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect x="3" y="3" width="22" height="22" rx="4" fill="#b8d0f8"/>
            <rect x="7" y="17" width="3" height="5" rx="1" fill="#6090e0"/>
            <rect x="12" y="12" width="3" height="10" rx="1" fill="#6090e0"/>
            <rect x="17" y="8" width="3" height="14" rx="1" fill="#4070c8"/>
          </svg>
        </div>
        <h3>Dashboard con KPIs</h3>
        <p>Tablero con totales por estado, monto pendiente, pagado del mes/año, top empleados y top proveedores. Gráfico mensual de los últimos 12 meses.</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon" style="background:#fff0f0;">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="11" fill="#f8c8c8"/>
            <line x1="14" y1="7" x2="14" y2="15" stroke="#d06060" stroke-width="2.8" stroke-linecap="round"/>
            <circle cx="14" cy="19" r="1.6" fill="#d06060"/>
          </svg>
        </div>
        <h3>Límite de Gasto por Empleado</h3>
        <p>Configura un límite mensual por empleado. El sistema alerta cuando una liquidación supera el límite, según política configurable.</p>
      </div>

      <div class="feature-card">
        <div class="feature-icon" style="background:#fff5f0;">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect x="4" y="7" width="20" height="15" rx="3" fill="#f8d8b8"/>
            <line x1="8" y1="12" x2="20" y2="12" stroke="#d08040" stroke-width="1.8"/>
            <line x1="8" y1="16" x2="15" y2="16" stroke="#d08040" stroke-width="1.8"/>
            <path d="M18 17 L22 21 M18 21 L22 17" stroke="#d06060" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
        </div>
        <h3>Nota de Rechazo</h3>
        <p>Al rechazar, el aprobador indica el motivo. La nota queda en el chatter y se notifica al empleado, facilitando corrección y reenvío.</p>
      </div>

    </div>
  </section>

  <!-- ═══════════════════════════════════════ SECTION 5: Configuración -->
  <section>
    <div class="section-label">Ajustes</div>
    <div class="section-title">Configuración</div>
    <p class="section-sub">Dos parámetros clave en Ajustes → Liquidaciones que adaptan el módulo a tu empresa.</p>
    <div class="config-grid">
      <div class="config-card">
        <h4>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <rect x="2" y="2" width="16" height="16" rx="4" fill="#c8b4e8"/>
            <polyline points="6,10 9,13 14,7" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
          </svg>
          Incluir Asientos Contables
        </h4>
        <p>Activa o desactiva la generación automática de asientos al publicar. Útil cuando se quiere usar el módulo solo para flujo de aprobación sin impacto contable inmediato (durante implementaciones o pruebas).</p>
      </div>
      <div class="config-card">
        <h4>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <rect x="2" y="3" width="8" height="14" rx="2" fill="#a8e6d4"/>
            <rect x="10" y="7" width="8" height="10" rx="2" fill="#6dcfb8"/>
          </svg>
          Asignación Multiempresa
        </h4>
        <p>Permite seleccionar una empresa pagadora distinta a la del empleado. Habilita el campo "Empresa Pagadora" en la liquidación, soportando flujos intercompañía completos con cuenta por cobrar entre compañías.</p>
      </div>
    </div>
  </section>

  <!-- ═══════════════════════════════════════ SECTION 6: Time savings (animated bars) -->
  <section>
    <div class="section-label">Retorno de Inversión</div>
    <div class="section-title">Ahorro de tiempo real</div>
    <p class="section-sub">Comparativa de tiempos entre el proceso manual y KTX Liquidaciones, para un equipo de 20 empleados al mes.</p>

    <div class="savings-list">
      <div class="savings-row">
        <div class="savings-task">📝 Registrar 10 gastos</div>
        <div class="savings-bars">
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">Manual</span>
            <div class="savings-bar-track"><div class="savings-bar-fill manual" style="--bar-w:90%;"></div></div>
            <span class="savings-bar-val">~45 min</span>
          </div>
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">KTX</span>
            <div class="savings-bar-track"><div class="savings-bar-fill ktx" style="--bar-w:18%;"></div></div>
            <span class="savings-bar-val">~8 min</span>
          </div>
        </div>
        <span class="savings-badge">Ahorras 37 min</span>
      </div>

      <div class="savings-row">
        <div class="savings-task">📤 Crear y enviar liquidación</div>
        <div class="savings-bars">
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">Manual</span>
            <div class="savings-bar-track"><div class="savings-bar-fill manual" style="--bar-w:75%;"></div></div>
            <span class="savings-bar-val">~30 min</span>
          </div>
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">KTX</span>
            <div class="savings-bar-track"><div class="savings-bar-fill ktx" style="--bar-w:5%;"></div></div>
            <span class="savings-bar-val">~2 min</span>
          </div>
        </div>
        <span class="savings-badge">Ahorras 28 min</span>
      </div>

      <div class="savings-row">
        <div class="savings-task">✅ Proceso de aprobación (2 niveles)</div>
        <div class="savings-bars">
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">Manual</span>
            <div class="savings-bar-track"><div class="savings-bar-fill manual" style="--bar-w:98%;"></div></div>
            <span class="savings-bar-val">~2-3 días</span>
          </div>
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">KTX</span>
            <div class="savings-bar-track"><div class="savings-bar-fill ktx" style="--bar-w:12%;"></div></div>
            <span class="savings-bar-val">~2-4 h</span>
          </div>
        </div>
        <span class="savings-badge">Ahorras ~2 días</span>
      </div>

      <div class="savings-row">
        <div class="savings-task">📊 Contabilizar 10 liquidaciones</div>
        <div class="savings-bars">
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">Manual</span>
            <div class="savings-bar-track"><div class="savings-bar-fill manual" style="--bar-w:80%;"></div></div>
            <span class="savings-bar-val">~3 horas</span>
          </div>
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">KTX</span>
            <div class="savings-bar-track"><div class="savings-bar-fill ktx" style="--bar-w:2%;"></div></div>
            <span class="savings-bar-val">~0 min</span>
          </div>
        </div>
        <span class="savings-badge">Ahorras 3 horas</span>
      </div>

      <div class="savings-row">
        <div class="savings-task">📈 Generar reporte mensual</div>
        <div class="savings-bars">
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">Manual</span>
            <div class="savings-bar-track"><div class="savings-bar-fill manual" style="--bar-w:70%;"></div></div>
            <span class="savings-bar-val">~2 horas</span>
          </div>
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">KTX</span>
            <div class="savings-bar-track"><div class="savings-bar-fill ktx" style="--bar-w:3%;"></div></div>
            <span class="savings-bar-val">~2 min</span>
          </div>
        </div>
        <span class="savings-badge">Ahorras 118 min</span>
      </div>

      <div class="savings-row">
        <div class="savings-task">💰 Registrar pagos (20 empleados)</div>
        <div class="savings-bars">
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">Manual</span>
            <div class="savings-bar-track"><div class="savings-bar-fill manual" style="--bar-w:60%;"></div></div>
            <span class="savings-bar-val">~1.5 horas</span>
          </div>
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">KTX</span>
            <div class="savings-bar-track"><div class="savings-bar-fill ktx" style="--bar-w:10%;"></div></div>
            <span class="savings-bar-val">~15 min</span>
          </div>
        </div>
        <span class="savings-badge">Ahorras 75 min</span>
      </div>

      <div class="savings-row total">
        <div class="savings-task">⏱️ Total estimado mensual</div>
        <div class="savings-bars">
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">Manual</span>
            <div class="savings-bar-track"><div class="savings-bar-fill total-manual" style="--bar-w:95%;"></div></div>
            <span class="savings-bar-val">~18-20 h</span>
          </div>
          <div class="savings-bar-row">
            <span class="savings-bar-lbl">KTX</span>
            <div class="savings-bar-track"><div class="savings-bar-fill total-ktx" style="--bar-w:10%;"></div></div>
            <span class="savings-bar-val">~1.5-2 h</span>
          </div>
        </div>
        <span class="savings-badge">~17 horas / mes ahorradas</span>
      </div>
    </div>
  </section>

  <!-- ═══════════════════════════════════════ SECTION 7: Requisitos -->
  <section>
    <div class="section-label">Técnico</div>
    <div class="section-title">Requisitos técnicos</div>
    <p class="section-sub">Compatible con Odoo 19 Community y Enterprise. Sin dependencias externas más allá de los módulos base de Odoo.</p>
    <div class="req-grid">
      <span class="req-pill"><span class="req-dot"></span>Odoo 19 (Community o Enterprise)</span>
      <span class="req-pill"><span class="req-dot"></span>Módulo: account</span>
      <span class="req-pill"><span class="req-dot"></span>Módulo: hr</span>
      <span class="req-pill"><span class="req-dot"></span>Módulo: mail</span>
      <span class="req-pill"><span class="req-dot"></span>Python 3.10+</span>
      <span class="req-pill"><span class="req-dot"></span>PostgreSQL 14+</span>
    </div>
  </section>

</div><!-- /container -->

<footer>
  <strong>KTX Liquidaciones — Gestión Avanzada de Gastos</strong>
  <p>Desarrollado para Odoo 19 &mdash; Kontaxes &copy; 2025</p>
</footer>

</body>
</html>
