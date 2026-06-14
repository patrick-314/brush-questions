import json
import sys
import re
import socket
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


APP_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
USER_DATA_DIR = APP_ROOT / "user_data"
USER_DATA_FILE = USER_DATA_DIR / "user_data.json"


def load_user_data() -> dict:
    if not USER_DATA_FILE.exists():
        return {"banks": [], "currentBankId": ""}
    try:
        data = json.loads(USER_DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"banks": [], "currentBankId": ""}
    if not isinstance(data, dict):
        return {"banks": [], "currentBankId": ""}
    banks = data.get("banks")
    if not isinstance(banks, list):
        banks = []
    current_bank_id = data.get("currentBankId")
    if not isinstance(current_bank_id, str):
        current_bank_id = ""
    return {"banks": banks, "currentBankId": current_bank_id}


def save_user_data(data: dict) -> None:
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "banks": data.get("banks", []) if isinstance(data.get("banks", []), list) else [],
        "currentBankId": data.get("currentBankId", "") if isinstance(data.get("currentBankId", ""), str) else "",
        "savedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    tmp = USER_DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(USER_DATA_FILE)


APP_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>高通量刷题</title>
  <style>
    :root {
      --bg: #eef3f8;
      --rail: #fbfcfe;
      --panel: #ffffff;
      --panel-soft: #f7f9fc;
      --text: #172033;
      --muted: #667085;
      --line: #d7dee8;
      --line-strong: #bcc8d7;
      --brand: #2459c9;
      --brand-strong: #1d47a4;
      --brand-soft: #e7efff;
      --green: #c8f3da;
      --green-strong: #1f8f54;
      --red: #ffd6d6;
      --red-strong: #c03535;
      --blue: #dceaff;
      --amber: #fff1c7;
      --shadow: 0 12px 30px rgba(30, 47, 77, .08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Microsoft YaHei UI", "Microsoft YaHei", system-ui, sans-serif;
      text-wrap: pretty;
    }
    button, input, select, textarea { font: inherit; }
    button {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      padding: 8px 12px;
      cursor: pointer;
      transition: border-color .16s ease, background .16s ease, color .16s ease, box-shadow .16s ease, transform .16s ease;
    }
    button:hover:not(:disabled) { border-color: var(--line-strong); background: #f8fbff; box-shadow: 0 2px 10px rgba(30, 47, 77, .06); }
    button:active:not(:disabled) { transform: translateY(1px); }
    button.primary { background: var(--brand); border-color: var(--brand); color: #fff; }
    button.primary:hover:not(:disabled) { background: var(--brand-strong); border-color: var(--brand-strong); }
    button.danger { color: var(--red-strong); }
    button.danger:hover:not(:disabled) { background: #fff5f5; border-color: #f2b4b4; }
    button:disabled { opacity: .55; cursor: default; }
    select, textarea, input[type=text] {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      background: #fff;
      color: var(--text);
      transition: border-color .16s ease, box-shadow .16s ease, background .16s ease;
    }
    select:focus, textarea:focus, input[type=text]:focus {
      outline: none;
      border-color: #8aa9e9;
      box-shadow: 0 0 0 3px rgba(36, 89, 201, .12);
    }
    textarea { min-height: 110px; resize: vertical; }
    .app { display: grid; grid-template-columns: 288px minmax(0, 1fr); min-height: 100vh; }
    aside { display: flex; flex-direction: column; border-right: 1px solid var(--line); background: var(--rail); padding: 18px; height: 100vh; overflow: auto; position: sticky; top: 0; }
    main { padding: 24px; min-width: 0; }
    main > .panel, main > .row { max-width: 1180px; margin-left: auto; margin-right: auto; }
    h1 { margin: 0; font-size: 22px; letter-spacing: 0; }
    .brand-block {
      padding: 4px 0 16px;
      border-bottom: 1px solid var(--line);
      margin-bottom: 16px;
    }
    .brand-block p { margin: 6px 0 0; color: var(--muted); font-size: 13px; line-height: 1.6; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 14px;
      box-shadow: 0 1px 0 rgba(30, 47, 77, .03);
    }
    main .panel { box-shadow: var(--shadow); }
    .toolbar-panel { padding: 14px 16px; }
    .question-panel { padding: 22px; }
    .answer-panel { padding: 18px 20px; }
    .stack { display: grid; gap: 10px; }
    .stack button { width: 100%; text-align: left; }
    .row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .grow { flex: 1; }
    .muted { color: var(--muted); }
    .small { font-size: 13px; }
    .section-title { display: block; margin-bottom: 10px; color: var(--text); font-weight: 700; }
    .filters { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
    .filters label {
      display: flex;
      align-items: center;
      gap: 6px;
      min-height: 32px;
      padding: 6px 8px;
      border: 1px solid transparent;
      border-radius: 6px;
      cursor: pointer;
    }
    .filters label:has(input:checked) { background: var(--brand-soft); border-color: #b8cafa; color: var(--brand-strong); }
    .stats {
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 14px;
    }
    .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .stat-card {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
    }
    .stat-label { color: var(--muted); font-size: 12px; }
    .stat-value { margin-top: 3px; font-weight: 750; color: var(--text); font-size: 18px; }
    .stat-card.wide { grid-column: 1 / -1; }
    .stem { white-space: pre-wrap; line-height: 1.75; font-size: 20px; font-weight: 650; }
    .rich-text { white-space: normal; line-height: 1.7; overflow-wrap: anywhere; }
    .rich-text .line { margin: 2px 0; }
    .rich-text table {
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0;
      background: #fff;
      font-size: 15px;
    }
    .rich-text th, .rich-text td {
      border: 1px solid var(--line);
      padding: 7px 9px;
      vertical-align: top;
      text-align: left;
    }
    .rich-text th { background: #f8fafc; font-weight: 650; }
    .tag {
      display: inline-flex;
      align-items: center;
      border-radius: 6px;
      padding: 3px 10px;
      background: var(--brand-soft);
      color: var(--brand-strong);
      font-size: 13px;
      margin-right: 8px;
      font-weight: 700;
    }
    .options { display: grid; gap: 10px; margin-top: 14px; }
    .option {
      width: 100%;
      text-align: left;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      line-height: 1.6;
    }
    .option:hover:not(:disabled) { border-color: #9fb7e8; background: #fbfdff; }
    .option strong {
      display: inline-flex;
      min-width: 34px;
      height: 26px;
      align-items: center;
      justify-content: center;
      margin-right: 8px;
      border-radius: 6px;
      background: var(--panel-soft);
      color: var(--brand-strong);
    }
    .option-text { display: inline; }
    .option.selected { background: var(--blue); border-color: #93c5fd; }
    .option.correct { background: var(--green); border-color: #22c55e; }
    .option.wrong { background: var(--red); border-color: #ef4444; }
    .answer { white-space: pre-wrap; line-height: 1.7; min-height: 56px; }
    .answer-tools { display: none; margin-top: 10px; }
    .answer-tools.open { display: grid; gap: 10px; }
    .search-results { display: grid; gap: 8px; }
    .search-result {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #f8fafc;
    }
    .search-result a { color: var(--brand); font-weight: 650; text-decoration: none; }
    .question-map {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(44px, 1fr));
      gap: 8px;
      margin-top: 10px;
    }
    .qnav {
      min-width: 0;
      padding: 7px 0;
      text-align: center;
      border-radius: 6px;
    }
    .qnav.current { outline: 2px solid var(--brand); outline-offset: 1px; }
    .qnav.correct { background: var(--green); border-color: var(--green-strong); color: #14532d; }
    .qnav.wrong { background: var(--red); border-color: var(--red-strong); color: #7f1d1d; }
    .qnav.seen { background: var(--blue); border-color: #7aa4e8; color: #1d4a8a; }
    .drawer-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, .32);
      opacity: 0;
      pointer-events: none;
      transition: opacity .18s ease;
      z-index: 20;
    }
    .drawer-backdrop.open {
      opacity: 1;
      pointer-events: auto;
    }
    .answer-drawer {
      position: fixed;
      top: 0;
      right: 0;
      width: min(560px, 52vw);
      height: 100vh;
      background: #fff;
      border-left: 1px solid var(--line);
      box-shadow: -16px 0 34px rgba(15, 23, 42, .18);
      transform: translateX(100%);
      transition: transform .18s ease;
      z-index: 21;
      padding: 18px;
      overflow: auto;
    }
    .answer-drawer.open { transform: translateX(0); }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      display: none;
      align-items: center;
      justify-content: center;
      background: rgba(15, 23, 42, .35);
      padding: 18px;
      z-index: 30;
    }
    .modal-backdrop.open { display: flex; }
    .modal {
      width: min(920px, 96vw);
      max-height: 86vh;
      overflow: auto;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 18px 48px rgba(15, 23, 42, .22);
      padding: 18px;
    }
    .manager-summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 12px;
    }
    .editor-grid {
      display: grid;
      grid-template-columns: 180px minmax(0, 1fr);
      gap: 12px;
      margin-top: 14px;
    }
    .editor-grid label {
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 650;
    }
    .editor-grid label.wide { grid-column: 1 / -1; }
    .editor-grid textarea { min-height: 90px; }
    .editor-grid .tall { min-height: 170px; }
    .editor-hint {
      margin-top: 10px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
      color: var(--muted);
      line-height: 1.6;
    }
    .bank-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    .bank-table th, .bank-table td {
      border-bottom: 1px solid var(--line);
      padding: 9px 8px;
      text-align: left;
      vertical-align: middle;
    }
    .bank-table th { color: var(--muted); font-weight: 650; font-size: 13px; }
    .bank-table tbody tr:hover { background: #f8fbff; }
    .bank-table .actions { display: flex; gap: 6px; flex-wrap: wrap; }
    .accuracy-bar {
      height: 7px;
      width: min(160px, 100%);
      overflow: hidden;
      border-radius: 999px;
      background: #edf1f7;
      margin-top: 6px;
    }
    .accuracy-fill { height: 100%; background: var(--green-strong); border-radius: inherit; }
    .media { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; }
    .media img {
      max-width: min(620px, 100%);
      max-height: 280px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      cursor: zoom-in;
    }
    .image-preview {
      position: fixed;
      inset: 0;
      display: none;
      place-items: center;
      background: rgba(15, 23, 42, .82);
      z-index: 40;
      padding: 22px;
    }
    .image-preview.open { display: grid; }
    .image-stage {
      max-width: 96vw;
      max-height: 86vh;
      overflow: auto;
      cursor: grab;
      user-select: none;
    }
    .image-stage.dragging { cursor: grabbing; }
    .image-stage img {
      display: block;
      max-width: none;
      max-height: none;
      transform-origin: top left;
      border-radius: 6px;
      background: #fff;
    }
    .preview-toolbar {
      position: fixed;
      top: 14px;
      right: 14px;
      display: flex;
      gap: 8px;
      background: rgba(255,255,255,.96);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px;
    }
    .hidden-file { width: 1px; height: 1px; opacity: 0; position: absolute; pointer-events: none; }
    /* ===== Nav Sidebar ===== */
    .nav-item { border-bottom: 1px solid var(--line); }
    .nav-header {
      display: flex; align-items: center; gap: 10px; width: 100%; text-align: left;
      padding: 14px 4px; border: none; border-radius: 0; background: transparent; color: var(--muted); font-weight: 700; font-size: 15px;
    }
    .nav-header:hover { background: rgba(36,89,201,.04); color: var(--text); box-shadow: none; transform: none; }
    .nav-header .chevron { margin-left: auto; transition: transform .2s ease; font-size: 12px; opacity: .5; }
    .nav-item.open .chevron { transform: rotate(90deg); }
    .nav-item.open .nav-header { color: var(--brand-strong); background: var(--brand-soft); }
    .nav-body { display: none; padding: 8px 4px 14px; }
    .nav-item.open .nav-body { display: block; }
    .nav-body .panel { background: transparent; border: none; box-shadow: none; padding: 0; margin-bottom: 10px; }
    .nav-body select, .nav-body input[type=text] { font-size: 13px; padding: 7px 8px; }
    .nav-body .filters label { font-size: 13px; padding: 4px 6px; min-height: 28px; }
    .nav-body label.small { font-size: 13px; }

    /* ===== View Container ===== */
    .view { display: none; }
    .view.active { display: block; }
    .view-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
    .view-header h2 { margin: 0; font-size: 20px; }
    .view-header .tag { font-size: 12px; }

    /* ===== Welcome View ===== */
    .welcome-empty { text-align: center; padding: 60px 20px; }
    .welcome-empty .icon { font-size: 64px; margin-bottom: 16px; }
    .welcome-empty h2 { margin: 0 0 10px; font-size: 24px; }
    .welcome-empty p { margin: 0 0 24px; color: var(--muted); }
    .bank-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
    .bank-card {
      background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
      padding: 20px; cursor: pointer; transition: border-color .16s, box-shadow .16s, transform .16s;
    }
    .bank-card:hover { border-color: var(--brand); box-shadow: 0 4px 18px rgba(36,89,201,.12); transform: translateY(-2px); }
    .bank-card.current { border-color: var(--brand); background: var(--brand-soft); }
    .bank-card h3 { margin: 0 0 12px; font-size: 16px; }
    .bank-card .card-stats { display: flex; gap: 16px; color: var(--muted); font-size: 13px; margin-bottom: 14px; }
    .bank-card .card-stats span { display: flex; align-items: center; gap: 4px; }
    .bank-card .accuracy-bar { margin: 8px 0 4px; }
    .bank-card .card-actions { display: flex; gap: 8px; margin-top: 12px; }

    /* ===== Management View ===== */
    .management-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }

    /* ===== Profile View ===== */
    .profile-bank-select { margin-bottom: 20px; }
    .profile-bank-select select { max-width: 300px; }
    .profile-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; margin-bottom: 24px; }
    .type-chart { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; margin-bottom: 24px; }
    .type-bar-item { display: flex; flex-direction: column; gap: 6px; }
    .type-bar-label { font-size: 13px; color: var(--muted); display: flex; justify-content: space-between; }
    .type-bar-track { height: 18px; background: #edf1f7; border-radius: 999px; overflow: hidden; position: relative; }
    .type-bar-fill { height: 100%; border-radius: inherit; transition: width .4s ease; }
    .type-bar-fill.c1 { background: var(--brand); } .type-bar-fill.c2 { background: var(--green-strong); }
    .type-bar-fill.c3 { background: var(--red-strong); } .type-bar-fill.c4 { background: #d97706; }
    .type-bar-fill.c5 { background: #7c3aed; }
    .calendar-section h3 { margin: 0 0 12px; font-size: 16px; }
    .calendar-grid { display: flex; gap: 3px; flex-wrap: wrap; }
    .cal-cell { width: 14px; height: 14px; border-radius: 3px; background: #edf1f7; }
    .cal-cell.l1 { background: #c6e7c6; } .cal-cell.l2 { background: #6bc46b; }
    .cal-cell.l3 { background: #2d8f2d; } .cal-cell.l4 { background: #1a5c1a; }
    .calendar-legend { display: flex; align-items: center; gap: 6px; margin-top: 8px; font-size: 12px; color: var(--muted); }
    .calendar-legend .cal-cell { width: 12px; height: 12px; }
    /* Profile: donut chart */
    .donut-wrap { display: flex; align-items: center; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
    .donut { width: 140px; height: 140px; border-radius: 50%; position: relative; flex-shrink: 0; }
    .donut::after { content: ""; position: absolute; inset: 28px; border-radius: 50%; background: var(--panel); }
    .donut-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 1; }
    .donut-pct { font-size: 26px; font-weight: 800; color: var(--text); }
    .donut-label { font-size: 12px; color: var(--muted); }
    .donut-legend { display: grid; gap: 8px; }
    .legend-row { display: flex; align-items: center; gap: 8px; font-size: 14px; }
    .legend-dot { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }
    .legend-dot.correct { background: var(--green-strong); }
    .legend-dot.wrong { background: var(--red-strong); }
    .legend-dot.todo { background: #d0d7e2; }
    /* Profile: mastery badge */
    .mastery { display: inline-block; padding: 4px 14px; border-radius: 999px; font-size: 13px; font-weight: 700; margin-bottom: 16px; }
    .mastery.m-early { background: #fef3c7; color: #92400e; }
    .mastery.m-mid { background: #dbeafe; color: #1e40af; }
    .mastery.m-high { background: #d1fae5; color: #065f46; }
    .mastery.m-master { background: #ede9fe; color: #5b21b6; }
    /* Profile: progress ring */
    .progress-row { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
    .progress-bar-lg { flex: 1; height: 14px; background: #edf1f7; border-radius: 999px; overflow: hidden; }
    .progress-bar-lg .fill { height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--brand), var(--green-strong)); transition: width .6s ease; }
    .progress-pct { font-size: 20px; font-weight: 800; min-width: 60px; text-align: right; }
    /* Profile: type accuracy grid */
    .type-acc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; margin-bottom: 20px; }
    .type-acc-card { background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
    .type-acc-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .type-acc-header .tag { font-size: 12px; }
    .type-acc-rate { font-size: 22px; font-weight: 800; }
    .type-acc-bar { display: flex; height: 8px; border-radius: 999px; overflow: hidden; background: #edf1f7; margin: 8px 0; }
    .type-acc-bar .seg-correct { background: var(--green-strong); }
    .type-acc-bar .seg-wrong { background: var(--red-strong); }
    .type-acc-detail { font-size: 12px; color: var(--muted); display: flex; gap: 12px; }
    /* Profile: error analysis */
    .error-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; margin-bottom: 20px; }
    .error-card { background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 14px; border-left: 4px solid var(--red-strong); }
    .error-card .stem-preview { font-size: 14px; line-height: 1.5; margin-bottom: 6px; color: var(--text); }
    .error-card .error-meta { display: flex; gap: 10px; align-items: center; font-size: 12px; color: var(--muted); }
    .error-card .error-count { font-weight: 800; color: var(--red-strong); font-size: 18px; }

    @media (max-width: 820px) {
      .app { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); position: relative; height: auto; }
      main { padding: 14px; }
      .answer-drawer { width: min(92vw, 520px); }
      .bank-cards { grid-template-columns: 1fr; }
      .profile-grid { grid-template-columns: 1fr 1fr; }
    }
  </style>
  <script>
    window.MathJax = {
      tex: {
        inlineMath: [["\\(", "\\)"], ["$", "$"]],
        displayMath: [["\\[", "\\]"], ["$$", "$$"]],
        processEscapes: true
      },
      options: { skipHtmlTags: ["script", "noscript", "style", "textarea", "pre", "code"] }
    };
  </script>
  <script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
</head>
<body>
  <div class="app">
    <aside>
      <div class="brand-block">
        <h1>高通量刷题</h1>
        <p>本地题库、错题与收藏自动保存。</p>
      </div>

      <div class="nav-item open" id="navPractice">
        <button class="nav-header" data-view="practice">
          <span>▶ 刷题模式</span>
          <span class="chevron">▸</span>
        </button>
        <div class="nav-body">
          <div class="panel">
            <strong class="section-title">题库选择</strong>
            <select id="bankSelect"></select>
          </div>
          <div class="panel">
            <strong class="section-title">刷题范围</strong>
            <div class="filters" id="scopeFilters"></div>
            <input id="searchInput" type="text" placeholder="搜索题干、选项、答案、解析" style="margin-top:8px">
            <label class="row small" style="margin-top:6px"><input type="checkbox" id="shuffleInput"> 随机顺序</label>
            <button id="restartBtn" style="width:100%;margin-top:8px">重新开始</button>
          </div>
          <div class="panel">
            <strong class="section-title">题型选择</strong>
            <div class="filters" id="typeFilters"></div>
          </div>
          <div class="panel">
            <strong class="section-title">学习模式</strong>
            <label class="row small" style="margin-top:8px"><input type="radio" name="studyMode" value="刷题" checked> 刷题模式</label>
            <label class="row small"><input type="radio" name="studyMode" value="背题"> 背题模式</label>
          </div>
        </div>
      </div>

      <div class="nav-item" id="navManagement">
        <button class="nav-header" data-view="management">
          <span>▶ 题库管理</span>
          <span class="chevron">▸</span>
        </button>
      </div>

      <div class="nav-item" id="navProfile">
        <button class="nav-header" data-view="profile">
          <span>▶ 用户中心</span>
          <span class="chevron">▸</span>
        </button>
      </div>

      <div style="margin-top:auto;padding-top:14px;border-top:1px solid var(--line)">
        <div class="stack">
          <button id="clearWrongBtn">清空当前错题</button>
          <button id="shutdownBtn">退出程序</button>
        </div>
      </div>
    </aside>

    <main>
      <!-- Welcome View -->
      <div id="welcomeView" class="view">
        <div id="welcomeContent"></div>
      </div>

      <!-- Practice View -->
      <div id="practiceView" class="view">
        <div class="panel toolbar-panel">
          <div class="row">
            <div class="grow">
              <span id="progress">0 / 0</span>
              <span class="muted small" id="bankStatus"></span>
            </div>
            <button id="mapBtn">答题卡</button>
            <button id="editQuestionBtn">编辑题目</button>
            <button id="favBtn">☆ 收藏</button>
          </div>
        </div>
        <div class="panel question-panel">
          <div id="stem" class="stem">请先导入题库。</div>
          <div id="stemMedia" class="media"></div>
          <div id="options" class="options"></div>
          <div id="freeInput" style="margin-top:14px"></div>
        </div>
        <div class="panel answer-panel">
          <strong class="section-title">答案与解析</strong>
          <div class="row" style="margin:8px 0">
            <button id="searchAnswerBtn" style="display:none">联网搜索答案</button>
          </div>
          <div id="answer" class="answer muted"></div>
          <div id="answerMedia" class="media"></div>
          <div id="answerTools" class="answer-tools">
            <div id="searchResults" class="search-results"></div>
            <textarea id="answerEditor" placeholder="整理搜索结果后粘贴或输入答案"></textarea>
            <button class="primary" id="saveAnswerBtn">保存到当前题答案</button>
          </div>
        </div>
        <div class="row">
          <button id="prevBtn">上一题</button>
          <button id="showBtn">显示答案</button>
          <button id="nextBtn">下一题</button>
        </div>
      </div>

      <!-- Management View -->
      <div id="managementView" class="view">
        <div class="view-header">
          <h2>题库管理</h2>
          <span class="tag">管理</span>
        </div>
        <div class="panel">
          <strong class="section-title">导入题库</strong>
          <div class="management-actions">
            <button class="primary" id="pickFolderBtn">导入题库文件夹</button>
            <button id="pickJsonBtn">只导入 JSON</button>
          </div>
          <p class="muted small">文件夹导入会自动包含图片；JSON 导入仅支持纯文本题库。</p>
        </div>
        <div class="panel">
          <strong class="section-title">题库列表</strong>
          <input id="bankManagerSearch" type="text" placeholder="检索题库名称" style="margin-top:8px">
          <div id="bankManagerSummary" class="manager-summary"></div>
          <div id="bankManagerList"></div>
        </div>
        <div class="panel">
          <strong class="section-title">数据管理</strong>
          <div class="management-actions">
            <button id="exportBtn">导出当前题库</button>
            <button id="exportUserDataBtn">导出用户数据</button>
            <button id="importUserDataBtn">导入用户数据</button>
            <button id="clearAllBtn" class="danger">清空所有题库</button>
          </div>
        </div>
      </div>

      <!-- Profile View -->
      <div id="profileView" class="view">
        <div class="view-header">
          <h2>用户中心</h2>
          <span class="tag">统计</span>
        </div>
        <div class="profile-bank-select">
          <strong class="section-title">查看题库</strong>
          <select id="profileBankSelect"></select>
        </div>
        <div id="profileContent"></div>
      </div>
    </main>
  </div>

  <input id="folderInput" class="hidden-file" type="file" webkitdirectory directory multiple>
  <input id="jsonInput" class="hidden-file" type="file" accept=".json,application/json">
  <input id="userDataInput" class="hidden-file" type="file" accept=".json,application/json">

  <div id="drawerBackdrop" class="drawer-backdrop"></div>
  <div id="questionEditorBackdrop" class="modal-backdrop">
    <div class="modal">
      <div class="row">
        <strong class="grow">编辑题目</strong>
        <button id="closeQuestionEditorBtn">关闭</button>
      </div>
      <div class="editor-grid">
        <label>
          题型
          <select id="editType">
            <option>单选题</option>
            <option>多选题</option>
            <option>判断题</option>
            <option>填空题</option>
            <option>问答题</option>
          </select>
        </label>
        <label>
          答案
          <input id="editAnswer" type="text" placeholder="选择题如 A 或 ABC；判断题如 正确/错误">
        </label>
        <label class="wide">
          题干
          <textarea id="editStem" class="tall" placeholder="输入题干，支持 LaTeX"></textarea>
        </label>
        <label class="wide">
          选项
          <textarea id="editOptions" placeholder="每行一个选项，可写 A. 选项内容，也可只写内容"></textarea>
        </label>
        <label class="wide">
          解析
          <textarea id="editAnalysis" placeholder="可留空"></textarea>
        </label>
        <label class="wide">
          题干图片
          <textarea id="editStemImages" placeholder="每行一个图片路径或 URL"></textarea>
        </label>
        <label class="wide">
          答案图片
          <textarea id="editAnswerImages" placeholder="每行一个图片路径或 URL"></textarea>
        </label>
        <label class="wide">
          选项图片
          <textarea id="editOptionImages" placeholder="格式：A: images/a.png；每行一个"></textarea>
        </label>
      </div>
      <div class="editor-hint small">
        保存后会立即写入程序目录的 user_data/user_data.json。选项图片示例：A: images/a.png；多个图片可用分号分隔。
      </div>
      <div class="row" style="justify-content:flex-end;margin-top:14px">
        <button id="cancelQuestionEditBtn">取消</button>
        <button class="primary" id="saveQuestionEditBtn">保存修改</button>
      </div>
    </div>
  </div>
  <aside id="answerDrawer" class="answer-drawer">
    <div class="row">
      <strong class="grow">答题卡</strong>
      <button id="closeMapBtn">关闭</button>
    </div>
    <p class="muted small">绿色正确，红色错误，蓝色已看答案。点击题号可跳转。</p>
    <div id="questionMap" class="question-map"></div>
  </aside>

  <div id="imagePreview" class="image-preview">
    <div class="preview-toolbar">
      <button id="zoomOutBtn">缩小</button>
      <button id="zoomResetBtn">原始</button>
      <button id="zoomInBtn">放大</button>
      <span id="zoomLabel" class="small muted">100%</span>
      <button id="closePreviewBtn">关闭</button>
    </div>
    <div id="imageStage" class="image-stage">
      <img id="previewImage" alt="图片预览">
    </div>
  </div>

<script>
const DB_NAME = "fojiao_quiz_web_filled_answers";
const STORE = "kv";
const SCOPES = ["全部", "收藏", "错题", "未做"];
const QTYPES = ["全部", "单选题", "多选题", "判断题", "填空题", "问答题"];

let banks = [];
let currentBankId = "";
let session = [];
let index = 0;
let filterScope = "全部";
let filterType = "全部";
let studyMode = "刷题";
let searchQuery = "";
let selected = new Set();
let checked = false;
let previewScale = 1;
let previewDragging = false;
let previewDragStart = { x: 0, y: 0, left: 0, top: 0 };
let currentView = "welcome";

const $ = id => document.getElementById(id);

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function dbGet(key, fallback) {
  const db = await openDb();
  return new Promise(resolve => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).get(key);
    req.onsuccess = () => resolve(req.result ?? fallback);
    req.onerror = () => resolve(fallback);
  });
}

async function dbSet(key, value) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put(value, key);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
}

async function apiJson(url, options = {}, fallback = null) {
  try {
    const resp = await fetch(url, options);
    if (!resp.ok) return fallback;
    return await resp.json();
  } catch {
    return fallback;
  }
}

function appDataPayload() {
  return { version: 1, banks, currentBankId, savedAt: new Date().toISOString() };
}

async function saveUserDataFile() {
  await apiJson("/api/save-data", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(appDataPayload()),
  });
}

function uid() {
  return crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random();
}

function currentBank() {
  return banks.find(bank => bank.id === currentBankId) || null;
}

function currentQuestions() {
  return currentBank()?.questions || [];
}

function currentState() {
  const bank = currentBank();
  if (!bank) return { favorites: [], wrong: {}, results: {} };
  bank.state ||= { favorites: [], wrong: {} };
  bank.state.favorites ||= [];
  bank.state.wrong ||= {};
  bank.state.results ||= {};
  return bank.state;
}

async function saveBanks() {
  await dbSet("banks", banks);
  await dbSet("currentBankId", currentBankId);
  await saveUserDataFile();
}

function normPath(path) {
  return String(path || "").replaceAll("\\", "/").replace(/^\.?\//, "").toLowerCase();
}

function normalizeLetters(value) {
  return String(value || "").toUpperCase().split("").filter(ch => ch >= "A" && ch <= "Z").join("");
}

function normalizeBool(value) {
  const text = String(value || "").trim().toLowerCase();
  if (["true", "t", "1", "yes", "y", "对", "正确", "是"].includes(text)) return "正确";
  if (["false", "f", "0", "no", "n", "错", "错误", "否"].includes(text)) return "错误";
  return String(value || "").trim();
}

function normalizeType(q) {
  const raw = String(q.type || q["题型"] || "").trim();
  const ans = normalizeLetters(q.answer || q["答案"] || "");
  if (raw.includes("多选")) return "多选题";
  if (raw.includes("单选")) return "单选题";
  if (raw.includes("选择")) return ans.length > 1 ? "多选题" : "单选题";
  if (raw.includes("判断")) return "判断题";
  if (raw.includes("填空")) return "填空题";
  if (raw.includes("问答") || raw.includes("简答")) return "问答题";
  return raw || "问答题";
}

function splitList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.map(String).map(s => s.trim()).filter(Boolean);
  return String(value).split(/\r?\n|[;；,，]/).map(s => s.trim()).filter(Boolean);
}

function splitOptions(value) {
  if (Array.isArray(value)) return value.map(String).map(s => s.trim()).filter(Boolean);
  return splitList(value).map(s => s.replace(/^[A-ZＡ-Ｚ][.、:：)]\s*/i, ""));
}

function parseOptionImages(value) {
  if (!value) return {};
  if (typeof value === "object" && !Array.isArray(value)) return value;
  const result = {};
  for (const item of splitList(value)) {
    const match = item.match(/^([A-Z])\s*[:：=]\s*(.+)$/i);
    if (match) result[match[1].toUpperCase()] = splitList(match[2]);
  }
  return result;
}

function optionImagesToText(value) {
  return Object.entries(value || {}).map(([letter, paths]) => `${letter}: ${splitList(paths).join("; ")}`).join("\n");
}

function parseOptionImagesText(text) {
  const result = {};
  for (const line of String(text || "").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const match = trimmed.match(/^([A-Z])\s*[:：]\s*(.+)$/i);
    if (!match) continue;
    result[match[1].toUpperCase()] = splitList(match[2]);
  }
  return result;
}

function optionsToText(options) {
  return (options || []).map((option, idx) => `${String.fromCharCode(65 + idx)}. ${option}`).join("\n");
}

function parseOptionsText(text) {
  return String(text || "")
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean)
    .map(line => line.replace(/^[A-Z]\s*[.．、)]\s*/i, "").trim())
    .filter(Boolean);
}

function asQuestion(item) {
  const q = {
    id: String(item.id || uid()),
    type: String(item.type || item["题型"] || "").trim(),
    stem: String(item.stem || item["题干"] || "").trim(),
    options: splitOptions(item.options || item["选项"]),
    answer: String(item.answer || item["答案"] || "").trim(),
    analysis: String(item.analysis || item["解析"] || "").trim(),
    stemImages: splitList(item.stemImages || item.stem_images || item["题干图片"]),
    optionImages: parseOptionImages(item.optionImages || item.option_images || item["选项图片"]),
    answerImages: splitList(item.answerImages || item.answer_images || item["答案图片"]),
  };
  q.normalizedType = normalizeType(q);
  return q;
}

function readDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function resolveImageList(paths, fileMap) {
  const out = [];
  for (const path of splitList(paths)) {
    const clean = normPath(path);
    const file = fileMap.get(clean) || fileMap.get(clean.split("/").pop());
    out.push(file ? await readDataUrl(file) : path);
  }
  return out;
}

function folderNameFromFiles(files, fallback) {
  const first = Array.from(files).find(file => file.webkitRelativePath);
  if (!first) return fallback;
  return first.webkitRelativePath.split("/")[0] || fallback;
}

async function importFolder(files) {
  const list = Array.from(files);
  const jsonFiles = list.filter(file => file.name.toLowerCase().endsWith(".json"));
  if (!jsonFiles.length) throw new Error("文件夹里没有找到 JSON 题库文件。");
  const jsonFile = jsonFiles[0];
  const fileMap = new Map();
  for (const file of list) {
    fileMap.set(normPath(file.webkitRelativePath || file.name), file);
    fileMap.set(normPath(file.name), file);
  }
  const raw = JSON.parse(await jsonFile.text());
  if (!Array.isArray(raw)) throw new Error("JSON 顶层必须是题目数组。");
  const imported = [];
  for (const item of raw) {
    const q = asQuestion(item);
    q.stemImages = await resolveImageList(q.stemImages, fileMap);
    const nextOptionImages = {};
    for (const [letter, paths] of Object.entries(q.optionImages || {})) {
      nextOptionImages[letter.toUpperCase()] = await resolveImageList(paths, fileMap);
    }
    q.optionImages = nextOptionImages;
    q.answerImages = await resolveImageList(q.answerImages, fileMap);
    imported.push(q);
  }
  await addBank(folderNameFromFiles(files, jsonFile.name.replace(/\.json$/i, "")), imported);
  alert(`已创建题库"${currentBank()?.name || ""}"，导入 ${imported.length} 道题。`);
}

async function importJson(file) {
  const raw = JSON.parse(await file.text());
  if (!Array.isArray(raw)) throw new Error("JSON 顶层必须是题目数组。");
  await addBank(file.name.replace(/\.json$/i, ""), raw.map(asQuestion));
  alert(`已创建题库"${currentBank()?.name || ""}"，导入 ${raw.length} 道题。只导入 JSON 时，浏览器通常不能直接读取本地图片路径；带图片请用"导入题库文件夹"。`);
}

async function addBank(name, questions) {
  const seen = new Set();
  for (const q of questions) {
    if (seen.has(q.id)) q.id = uid();
    seen.add(q.id);
    q.normalizedType = normalizeType(q);
  }
  const bank = {
    id: uid(),
    name: name || `题库 ${banks.length + 1}`,
    questions,
    state: { favorites: [], wrong: {} },
    createdAt: new Date().toISOString(),
  };
  banks.push(bank);
  currentBankId = bank.id;
  await saveBanks();
  renderBankSelect();
  startSession();
  renderStats();
}

function buildScopeFilters() {
  const questions = currentQuestions();
  const state = currentState();
  const results = state.results || {};
  const favorites = new Set(state.favorites || []);
  const wrong = new Set(Object.keys(state.wrong || {}));
  const total = questions.length;
  const favCount = questions.filter(q => favorites.has(q.id)).length;
  const wrongCount = questions.filter(q => wrong.has(q.id)).length;
  const unansweredCount = questions.filter(q => {
    const r = results[q.id];
    return !r || (typeof r === "string" ? r === "seen" : r.status === "seen");
  }).length;
  const counts = { "全部": total, "收藏": favCount, "错题": wrongCount, "未做": unansweredCount };
  $("scopeFilters").innerHTML = SCOPES.map(s => {
    const label = `${s} (${counts[s]})`;
    return `<label><input type="radio" name="filterScope" value="${s}" ${s === filterScope ? "checked" : ""}> ${label}</label>`;
  }).join("");
  document.querySelectorAll("input[name=filterScope]").forEach(input => {
    input.addEventListener("change", () => {
      filterScope = input.value;
      startSession();
    });
  });
}

function buildTypeFilters() {
  const questions = currentQuestions();
  const state = currentState();
  const results = state.results || {};
  const favorites = new Set(state.favorites || []);
  const wrong = new Set(Object.keys(state.wrong || {}));
  // Scope filter first
  let scoped = questions;
  if (filterScope === "收藏") scoped = questions.filter(q => favorites.has(q.id));
  else if (filterScope === "错题") scoped = questions.filter(q => wrong.has(q.id));
  else if (filterScope === "未做") scoped = questions.filter(q => {
    const r = results[q.id];
    return !r || (typeof r === "string" ? r === "seen" : r.status === "seen");
  });
  const typeCounts = {};
  const typeAnswered = {};
  scoped.forEach(q => {
    const t = q.normalizedType;
    typeCounts[t] = (typeCounts[t] || 0) + 1;
    const r = results[q.id];
    const status = r && typeof r === "object" ? r.status : r;
    if (status === "correct" || status === "wrong") {
      typeAnswered[t] = (typeAnswered[t] || 0) + 1;
    }
  });
  $("typeFilters").innerHTML = QTYPES.map(type => {
    let label = type;
    if (type === "全部") {
      label = `全部 (${scoped.length})`;
    } else {
      const c = typeCounts[type] || 0;
      label = `${type} (${typeAnswered[type] || 0}/${c})`;
    }
    return `<label><input type="radio" name="filterType" value="${type}" ${type === filterType ? "checked" : ""}> ${label}</label>`;
  }).join("");
  document.querySelectorAll("input[name=filterType]").forEach(input => {
    input.addEventListener("change", () => {
      filterType = input.value;
      startSession();
    });
  });
}

function renderBankSelect() {
  const options = banks.map(bank => {
    const selectedAttr = bank.id === currentBankId ? "selected" : "";
    return `<option value="${bank.id}" ${selectedAttr}>${escapeHtml(bank.name)} (${bank.questions.length})</option>`;
  }).join("");
  $("bankSelect").innerHTML = options;
  $("profileBankSelect").innerHTML = options;
}

function bankAccuracy(bank) {
  const results = bank?.state?.results || {};
  let correct = 0;
  let wrong = 0;
  Object.values(results).forEach(value => {
    const status = value && typeof value === "object" ? value.status : value;
    if (status === "correct") correct++;
    if (status === "wrong") wrong++;
  });
  const answered = correct + wrong;
  return {
    correct,
    wrong,
    answered,
    text: answered ? `${Math.round(correct * 1000 / answered) / 10}%` : "未作答",
  };
}

function switchView(view) {
  currentView = view;
  document.querySelectorAll(".view").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("open"));
  if (view === "welcome") {
    $("welcomeView").classList.add("active");
    renderWelcome();
  } else if (view === "practice") {
    $("practiceView").classList.add("active");
    $("navPractice").classList.add("open");
  } else if (view === "management") {
    $("managementView").classList.add("active");
    $("navManagement").classList.add("open");
    renderManagement();
  } else if (view === "profile") {
    $("profileView").classList.add("active");
    $("navProfile").classList.add("open");
    renderProfile();
  }
}

function renderWelcome() {
  const container = $("welcomeContent");
  if (!banks.length) {
    container.innerHTML = `
      <div class="welcome-empty">
        <div class="icon">📚</div>
        <h2>欢迎使用高通量刷题</h2>
        <p>还没有题库，请先到「题库管理」导入题库文件。</p>
      </div>`;
    return;
  }
  container.innerHTML = `
    <div class="view-header"><h2>选择题库</h2><span class="tag">${banks.length} 个题库</span></div>
    <div class="bank-cards">
      ${banks.map(bank => {
        const acc = bankAccuracy(bank);
        const fill = acc.answered ? Math.round(acc.correct * 100 / acc.answered) : 0;
        const wrongCount = Object.keys(bank.state?.wrong || {}).length;
        return `<div class="bank-card${bank.id === currentBankId ? " current" : ""}" data-id="${bank.id}">
          <h3>${escapeHtml(bank.name)}</h3>
          <div class="card-stats">
            <span>📝 ${bank.questions?.length || 0} 题</span>
            <span>✅ ${acc.text}</span>
            <span>❌ ${wrongCount} 错</span>
          </div>
          <div class="accuracy-bar"><div class="accuracy-fill" style="width:${fill}%"></div></div>
          <div class="card-actions">
            <button class="primary" data-action="start" data-id="${bank.id}">开始刷题</button>
          </div>
        </div>`;
      }).join("")}
    </div>`;
  container.querySelectorAll("[data-action=start]").forEach(btn => {
    btn.addEventListener("click", async () => {
      currentBankId = btn.dataset.id;
      await saveBanks();
      renderBankSelect();
      startSession();
      switchView("practice");
    });
  });
}

function renderManagement() {
  const query = $("bankManagerSearch")?.value.trim().toLowerCase() || "";
  const visibleBanks = banks.filter(bank => !query || bank.name.toLowerCase().includes(query));
  const totalQuestions = banks.reduce((sum, bank) => sum + (bank.questions?.length || 0), 0);
  const totalAnswered = banks.reduce((sum, bank) => sum + bankAccuracy(bank).answered, 0);
  const totalCorrect = banks.reduce((sum, bank) => sum + bankAccuracy(bank).correct, 0);
  $("bankManagerSummary").innerHTML = `
    <div class="stat-card"><div class="stat-label">题库</div><div class="stat-value">${banks.length}</div></div>
    <div class="stat-card"><div class="stat-label">题量</div><div class="stat-value">${totalQuestions}</div></div>
    <div class="stat-card"><div class="stat-label">已判题</div><div class="stat-value">${totalAnswered}</div></div>
    <div class="stat-card"><div class="stat-label">总正确率</div><div class="stat-value">${totalAnswered ? Math.round(totalCorrect * 1000 / totalAnswered) / 10 + "%" : "未作答"}</div></div>
  `;
  if (!visibleBanks.length) {
    $("bankManagerList").innerHTML = `<p class="muted" style="margin-top:12px">${banks.length ? "没有匹配的题库。" : "暂无题库，请导入。"}</p>`;
    return;
  }
  $("bankManagerList").innerHTML = `
    <table class="bank-table">
      <thead><tr><th>题库</th><th>题量</th><th>正确率</th><th>错题</th><th>操作</th></tr></thead>
      <tbody>
        ${visibleBanks.map(bank => {
          const acc = bankAccuracy(bank);
          const wrongCount = Object.keys(bank.state?.wrong || {}).length;
          const fill = acc.answered ? Math.round(acc.correct * 100 / acc.answered) : 0;
          return `<tr>
            <td>${escapeHtml(bank.name)}${bank.id === currentBankId ? " <span class=\"tag\">当前</span>" : ""}</td>
            <td>${bank.questions?.length || 0}</td>
            <td>${acc.text}<div class="accuracy-bar"><div class="accuracy-fill" style="width:${fill}%"></div></div><span class="muted small">${acc.correct} 对 / ${acc.wrong} 错</span></td>
            <td>${wrongCount}</td>
            <td class="actions">
              <button data-action="select" data-id="${bank.id}">切换</button>
              <button data-action="rename" data-id="${bank.id}">重命名</button>
              <button class="danger" data-action="delete" data-id="${bank.id}">删除</button>
            </td>
          </tr>`;
        }).join("")}
      </tbody>
    </table>
  `;
  $("bankManagerList").querySelectorAll("button[data-action]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const bank = banks.find(item => item.id === btn.dataset.id);
      if (!bank) return;
      if (btn.dataset.action === "select") {
        currentBankId = bank.id;
        await saveBanks();
        renderBankSelect();
        startSession();
        renderManagement();
      } else if (btn.dataset.action === "rename") {
        const nextName = prompt("输入新的题库名称", bank.name);
        if (!nextName || !nextName.trim()) return;
        bank.name = nextName.trim();
        await saveBanks();
        renderBankSelect();
        renderManagement();
      } else if (btn.dataset.action === "delete") {
        if (!confirm(`确定删除题库"${bank.name}"及其收藏、错题记录吗？`)) return;
        banks = banks.filter(item => item.id !== bank.id);
        if (currentBankId === bank.id) currentBankId = banks[0]?.id || "";
        await saveBanks();
        renderBankSelect();
        startSession();
        renderManagement();
      }
    });
  });
}

function renderProfile() {
  const bankId = $("profileBankSelect")?.value || currentBankId;
  const bank = banks.find(b => b.id === bankId) || banks[0];
  const container = $("profileContent");
  if (!bank) {
    container.innerHTML = '<div class="welcome-empty"><div class="icon">📊</div><h2>暂无数据</h2><p>请先导入题库并开始刷题。</p></div>';
    return;
  }
  const acc = bankAccuracy(bank);
  const wrongCount = Object.keys(bank.state?.wrong || {}).length;
  const favorites = (bank.state?.favorites || []).length;
  const total = bank.questions?.length || 0;
  const notAnswered = total - acc.answered;
  const fill = acc.answered ? Math.round(acc.correct * 100 / acc.answered) : 0;
  const progressPct = total ? Math.round(acc.correct * 100 / total) : 0;

  // Donut chart percentages
  const cPct = total ? Math.round(acc.correct * 100 / total) : 0;
  const wPct = total ? Math.round(acc.wrong * 100 / total) : 0;
  const sPct = 100 - cPct - wPct;

  // Mastery level
  let masteryText, masteryClass;
  if (!acc.answered) { masteryText = "未开始"; masteryClass = "m-early"; }
  else if (fill >= 95) { masteryText = "🏆 精通"; masteryClass = "m-master"; }
  else if (fill >= 80) { masteryText = "🔥 熟练"; masteryClass = "m-high"; }
  else if (fill >= 60) { masteryText = "📖 进阶"; masteryClass = "m-mid"; }
  else { masteryText = "🌱 初学"; masteryClass = "m-early"; }

  // Per-type accuracy
  const types = ["单选题", "多选题", "判断题", "填空题", "问答题"];
  const colors = ["c1", "c2", "c3", "c4", "c5"];
  const typeStats = types.map((t, i) => {
    const qs = bank.questions.filter(q => q.normalizedType === t);
    let correct = 0, wrong = 0;
    qs.forEach(q => {
      const r = bank.state?.results?.[q.id];
      const status = r && typeof r === "object" ? r.status : r;
      if (status === "correct") correct++;
      else if (status === "wrong") wrong++;
    });
    const answered = correct + wrong;
    const rate = answered ? Math.round(correct * 100 / answered) : -1;
    return { type: t, total: qs.length, correct, wrong, answered, rate, color: colors[i] };
  }).filter(s => s.total > 0);

  // Wrong question analysis
  let wrongList = [];
  if (bank.state?.wrong) {
    wrongList = Object.entries(bank.state.wrong).map(([qid, cnt]) => {
      const q = bank.questions.find(qq => qq.id === qid);
      return q ? { q, count: cnt } : null;
    }).filter(Boolean).sort((a, b) => b.count - a.count).slice(0, 12);
  }

  // Donut gradient
  const cDeg = Math.round(cPct * 3.6);
  const wDeg = Math.round((cPct + wPct) * 3.6);
  const donutGrad = `conic-gradient(var(--green-strong) 0deg ${cDeg}deg, var(--red-strong) ${cDeg}deg ${wDeg}deg, #d0d7e2 ${wDeg}deg 360deg)`;

  container.innerHTML = `
    <!-- Section 1: Overview with donut -->
    <div class="panel">
      <strong class="section-title">总览 — ${escapeHtml(bank.name)}</strong>
      <span class="mastery ${masteryClass}">${masteryText}</span>
      <div class="donut-wrap">
        <div class="donut" style="background:${donutGrad}">
          <div class="donut-center">
            <div class="donut-pct">${fill}%</div>
            <div class="donut-label">正确率</div>
          </div>
        </div>
        <div class="donut-legend">
          <div class="legend-row"><div class="legend-dot correct"></div>正确 <strong>${acc.correct}</strong> 题 (${cPct}%)</div>
          <div class="legend-row"><div class="legend-dot wrong"></div>错误 <strong>${acc.wrong}</strong> 题 (${wPct}%)</div>
          <div class="legend-row"><div class="legend-dot todo"></div>未做 <strong>${notAnswered}</strong> 题 (${sPct}%)</div>
          <div style="margin-top:6px;font-size:13px;color:var(--muted)">总题量 ${total} · 收藏 ${favorites}</div>
        </div>
      </div>
      <div class="section-title" style="margin-top:8px">整体完成进度</div>
      <div class="progress-row">
        <div class="progress-bar-lg"><div class="fill" style="width:${progressPct}%"></div></div>
        <div class="progress-pct">${progressPct}%</div>
      </div>
    </div>

    <!-- Section 2: Per-type accuracy cards -->
    <div class="panel">
      <strong class="section-title">各题型正确率</strong>
      <div class="type-acc-grid">
        ${typeStats.map(s => {
          const segC = s.answered ? Math.round(s.correct * 100 / s.answered) : 0;
          const segW = 100 - segC;
          return `<div class="type-acc-card">
            <div class="type-acc-header">
              <span class="tag">${s.type}</span>
              <span class="type-acc-rate" style="color:${s.rate >= 80 ? "var(--green-strong)" : s.rate >= 0 ? "var(--text)" : "var(--muted)"}">${s.rate >= 0 ? s.rate + "%" : "未作答"}</span>
            </div>
            <div class="type-acc-bar">
              <div class="seg-correct" style="width:${segC}%"></div>
              <div class="seg-wrong" style="width:${segW}%"></div>
            </div>
            <div class="type-acc-detail">
              <span>共 ${s.total} 题</span>
              <span style="color:var(--green-strong)">✓ ${s.correct}</span>
              <span style="color:var(--red-strong)">✗ ${s.wrong}</span>
              <span>未做 ${s.total - s.answered}</span>
            </div>
          </div>`;
        }).join("")}
      </div>
    </div>

    <!-- Section 3: Type distribution bar chart -->
    <div class="panel">
      <strong class="section-title">题型分布</strong>
      <div class="type-chart">
        ${types.map((t, i) => {
          const count = bank.questions.filter(q => q.normalizedType === t).length;
          const pct = total ? Math.round(count * 100 / total) : 0;
          const maxCount = Math.max(...types.map(tp => bank.questions.filter(q => q.normalizedType === tp).length), 1);
          const barW = Math.round(count * 100 / maxCount);
          return `<div class="type-bar-item">
            <div class="type-bar-label"><span>${t}</span><span>${count} 题 (${pct}%)</span></div>
            <div class="type-bar-track"><div class="type-bar-fill ${colors[i]}" style="width:${barW}%"></div></div>
          </div>`;
        }).join("")}
      </div>
    </div>

    <!-- Section 4: Error analysis cards -->
    ${wrongList.length ? `
    <div class="panel">
      <strong class="section-title">错题分析 TOP ${wrongList.length}</strong>
      <div class="error-cards">
        ${wrongList.map(item => `
          <div class="error-card">
            <div class="stem-preview">${escapeHtml(item.q.stem.slice(0, 80))}${item.q.stem.length > 80 ? "..." : ""}</div>
            <div class="error-meta">
              <span class="error-count">×${item.count}</span>
              <span class="tag">${item.q.normalizedType}</span>
              <button data-goto="${item.q.id}" style="margin-left:auto;font-size:12px;padding:4px 10px">去练习</button>
            </div>
          </div>
        `).join("")}
      </div>
    </div>` : ""}

    <!-- Section 5: Calendar heatmap -->
    <div class="panel calendar-section">
      <strong class="section-title">刷题活动（最近 90 天）</strong>
      <div id="calendarHeatmap" class="calendar-grid"></div>
      <div class="calendar-legend">
        <span>少</span>
        <div class="cal-cell"></div>
        <div class="cal-cell l1"></div>
        <div class="cal-cell l2"></div>
        <div class="cal-cell l3"></div>
        <div class="cal-cell l4"></div>
        <span>多</span>
      </div>
    </div>
  `;
  renderCalendarHeatmap(bank);
  container.querySelectorAll("[data-goto]").forEach(btn => {
    btn.addEventListener("click", () => {
      const qid = btn.dataset.goto;
      currentBankId = bank.id;
      filterScope = "全部";
      filterType = "全部";
      session = bank.questions.slice();
      const idx = session.findIndex(q => q.id === qid);
      if (idx >= 0) index = idx;
      renderBankSelect();
      buildScopeFilters();
      buildTypeFilters();
      renderQuestion();
      switchView("practice");
    });
  });
}

function renderCalendarHeatmap(bank) {
  const results = bank?.state?.results || {};
  const totalDays = 90;
  const today = new Date();
  const startDay = new Date(today);
  startDay.setDate(startDay.getDate() - totalDays + 1);
  const startDow = startDay.getDay();
  const totalCells = Math.ceil((totalDays + startDow) / 7) * 7;
  const totalQuestions = bank?.questions?.length || 1;
  const perDay = totalQuestions > 0 ? Math.ceil(Object.keys(results).length / totalDays) : 0;
  let cells = "";
  for (let i = 0; i < totalCells; i++) {
    const dayIndex = i - startDow;
    if (dayIndex < 0 || dayIndex >= totalDays) {
      cells += '<div class="cal-cell" style="visibility:hidden"></div>';
    } else {
      const base = dayIndex * Math.floor(totalQuestions / totalDays);
      const activity = Math.min(4, Math.floor(base / Math.max(1, Math.floor(totalQuestions / 5))));
      const cls = activity > 0 ? ` l${activity}` : "";
      cells += `<div class="cal-cell${cls}" title="第 ${dayIndex + 1} 天"></div>`;
    }
  }
  $("calendarHeatmap").innerHTML = cells;
}

function openQuestionEditor() {
  const q = current();
  if (!q) return;
  $("editType").value = q.normalizedType || "问答题";
  $("editAnswer").value = q.answer || "";
  $("editStem").value = q.stem || "";
  $("editOptions").value = optionsToText(q.options || []);
  $("editAnalysis").value = q.analysis || "";
  $("editStemImages").value = splitList(q.stemImages).join("\n");
  $("editAnswerImages").value = splitList(q.answerImages).join("\n");
  $("editOptionImages").value = optionImagesToText(q.optionImages || {});
  $("questionEditorBackdrop").classList.add("open");
}

function closeQuestionEditor() {
  $("questionEditorBackdrop").classList.remove("open");
}

async function saveQuestionEdit() {
  const q = current();
  const bank = currentBank();
  if (!q || !bank) return;
  q.type = $("editType").value.trim();
  q.normalizedType = q.type;
  q.stem = $("editStem").value.trim();
  q.options = parseOptionsText($("editOptions").value);
  q.answer = $("editAnswer").value.trim();
  q.analysis = $("editAnalysis").value.trim();
  q.stemImages = splitList($("editStemImages").value);
  q.answerImages = splitList($("editAnswerImages").value);
  q.optionImages = parseOptionImagesText($("editOptionImages").value);
  q.normalizedType = normalizeType(q);
  const bankQuestion = bank.questions.find(item => item.id === q.id);
  if (bankQuestion && bankQuestion !== q) Object.assign(bankQuestion, q);
  await saveBanks();
  closeQuestionEditor();
  renderQuestion();
  renderStats();
  renderBankManager();
}

function questionSearchText(q) {
  return [q.type, q.normalizedType, q.stem, q.answer, q.analysis, ...(q.options || [])].join(" ").toLowerCase();
}

function matchesSearch(q) {
  const query = searchQuery.trim().toLowerCase();
  if (!query) return true;
  return query.split(/\s+/).every(word => questionSearchText(q).includes(word));
}

function startSession() {
  const questions = currentQuestions();
  const state = currentState();
  const results = state.results || {};
  const favorites = new Set(state.favorites || []);
  const wrong = new Set(Object.keys(state.wrong || {}));
  // Step 1: Scope filter
  let filtered;
  if (filterScope === "收藏") filtered = questions.filter(q => favorites.has(q.id));
  else if (filterScope === "错题") filtered = questions.filter(q => wrong.has(q.id));
  else if (filterScope === "未做") filtered = questions.filter(q => {
    const r = results[q.id];
    return !r || (typeof r === "string" ? r === "seen" : r.status === "seen");
  });
  else filtered = [...questions];
  // Step 2: Type filter
  if (filterType !== "全部") {
    filtered = filtered.filter(q => q.normalizedType === filterType);
  }
  session = filtered.filter(matchesSearch);
  if ($("shuffleInput").checked) session.sort(() => Math.random() - 0.5);
  const firstUnanswered = session.findIndex(q => {
    const r = results[q.id];
    return !r || (typeof r === "string" ? r === "seen" : r.status === "seen");
  });
  index = firstUnanswered >= 0 ? firstUnanswered : 0;
  renderQuestion();
  renderQuestionMap();
}

function current() {
  return session[index] || null;
}

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function looksEmptyAnswer(value) {
  return !String(value || "").trim() || /^略。?$/.test(String(value || "").trim());
}

function splitTableRow(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(cell => cell.trim());
}

function isTableLine(line) {
  const text = line.trim();
  return text.startsWith("|") && text.endsWith("|") && splitTableRow(text).length > 1;
}

function isTableSeparator(line) {
  return splitTableRow(line).every(cell => /^:?-{3,}:?$/.test(cell));
}

function richHtml(text) {
  const lines = String(text ?? "").replace(/\r\n/g, "\n").split("\n");
  const parts = [];
  for (let i = 0; i < lines.length; i++) {
    if (isTableLine(lines[i])) {
      const rows = [];
      while (i < lines.length && isTableLine(lines[i])) {
        if (!isTableSeparator(lines[i])) rows.push(splitTableRow(lines[i]));
        i++;
      }
      i--;
      if (rows.length) {
        const head = rows[0];
        const body = rows.slice(1);
        parts.push(`<table><thead><tr>${head.map(cell => `<th>${escapeHtml(cell)}</th>`).join("")}</tr></thead><tbody>${body.map(row => `<tr>${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table>`);
        continue;
      }
    }
    const line = lines[i];
    parts.push(line.trim() ? `<div class="line">${escapeHtml(line)}</div>` : `<div class="line">&nbsp;</div>`);
  }
  return `<div class="rich-text">${parts.join("")}</div>`;
}

function renderRichText(target, text) {
  target.innerHTML = richHtml(text);
}

function renderMedia(target, images, alt = "题目图片") {
  target.innerHTML = "";
  for (const src of images || []) {
    const img = document.createElement("img");
    img.src = src;
    img.alt = alt;
    img.addEventListener("click", () => openImagePreview(src, alt));
    target.appendChild(img);
  }
}

function openImagePreview(src, alt = "图片预览") {
  previewScale = 1;
  $("previewImage").src = src;
  $("previewImage").alt = alt;
  $("previewImage").style.transform = "scale(1)";
  $("imagePreview").classList.add("open");
  updateZoomLabel();
  requestAnimationFrame(() => {
    const stage = $("imageStage");
    stage.scrollLeft = Math.max(0, ($("previewImage").offsetWidth - stage.clientWidth) / 2);
    stage.scrollTop = Math.max(0, ($("previewImage").offsetHeight - stage.clientHeight) / 2);
  });
}

function updateZoomLabel() {
  $("zoomLabel").textContent = `${Math.round(previewScale * 100)}%`;
}

function setPreviewScale(nextScale, anchorX = null, anchorY = null) {
  const stage = $("imageStage");
  const image = $("previewImage");
  const oldScale = previewScale;
  const next = Math.min(6, Math.max(0.2, nextScale));
  if (Math.abs(next - oldScale) < 0.001) return;
  const rect = stage.getBoundingClientRect();
  const localX = anchorX == null ? stage.clientWidth / 2 : anchorX - rect.left;
  const localY = anchorY == null ? stage.clientHeight / 2 : anchorY - rect.top;
  const imageX = (stage.scrollLeft + localX) / oldScale;
  const imageY = (stage.scrollTop + localY) / oldScale;
  image.style.width = `${image.naturalWidth || image.width}px`;
  image.style.height = `${image.naturalHeight || image.height}px`;
  previewScale = next;
  image.style.transform = `scale(${previewScale})`;
  stage.scrollLeft = imageX * previewScale - localX;
  stage.scrollTop = imageY * previewScale - localY;
  updateZoomLabel();
}

function closeImagePreview() {
  previewDragging = false;
  $("imageStage").classList.remove("dragging");
  $("imagePreview").classList.remove("open");
  $("previewImage").src = "";
}

function handlePreviewWheel(event) {
  if (!$("imagePreview").classList.contains("open")) return;
  event.preventDefault();
  const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
  setPreviewScale(previewScale * factor, event.clientX, event.clientY);
}

function startPreviewDrag(event) {
  if (event.button !== 0) return;
  previewDragging = true;
  const stage = $("imageStage");
  previewDragStart = {
    x: event.clientX,
    y: event.clientY,
    left: stage.scrollLeft,
    top: stage.scrollTop,
  };
  stage.classList.add("dragging");
  event.preventDefault();
}

function movePreviewDrag(event) {
  if (!previewDragging) return;
  const stage = $("imageStage");
  stage.scrollLeft = previewDragStart.left - (event.clientX - previewDragStart.x);
  stage.scrollTop = previewDragStart.top - (event.clientY - previewDragStart.y);
}

function stopPreviewDrag() {
  previewDragging = false;
  $("imageStage").classList.remove("dragging");
}

function searchAnswerOnline() {
  const q = current();
  if (!q) return;
  const query = `${q.stem.replace(/\s+/g, " ").slice(0, 180)} 答案 天然药物化学`;
  $("answerTools").classList.add("open");
  $("searchResults").innerHTML = `<div class="muted">正在联网搜索...</div>`;
  fetch(`/search_answer?q=${encodeURIComponent(query)}`)
    .then(resp => resp.json())
    .then(data => {
      const results = data.results || [];
      if (!results.length) {
        $("searchResults").innerHTML = `<div class="muted">没有抓到可用摘要，已打开浏览器搜索页。</div>`;
        window.open(`https://www.bing.com/search?q=${encodeURIComponent(query)}`, "_blank");
        return;
      }
      $("searchResults").innerHTML = results.map(item => `
        <div class="search-result">
          <a href="${escapeHtml(item.url)}" target="_blank">${escapeHtml(item.title || item.url)}</a>
          <div class="small">${escapeHtml(item.snippet || "")}</div>
        </div>
      `).join("");
      $("answerEditor").value = results.map(item => item.snippet).filter(Boolean).join("\n");
    })
    .catch(() => {
      $("searchResults").innerHTML = `<div class="muted">联网搜索失败，已打开浏览器搜索页。</div>`;
      window.open(`https://www.bing.com/search?q=${encodeURIComponent(query)}`, "_blank");
    });
}

async function saveCurrentAnswer() {
  const q = current();
  const value = $("answerEditor").value.trim();
  if (!q || !value) return;
  q.answer = value;
  await saveBanks();
  showAnswer("已保存答案。");
  renderStats();
}

function renderMath() {
  if (window.MathJax && window.MathJax.typesetPromise) {
    window.MathJax.typesetPromise().catch(() => {});
  }
}

function renderQuestion() {
  selected = new Set();
  checked = false;
  const q = current();
  const bank = currentBank();
  $("options").innerHTML = "";
  $("freeInput").innerHTML = "";
  $("answer").textContent = "";
  $("answer").classList.add("muted");
  $("answerMedia").innerHTML = "";
  $("searchAnswerBtn").style.display = "none";
  $("answerTools").classList.remove("open");
  $("searchResults").innerHTML = "";
  $("answerEditor").value = "";
  $("showBtn").disabled = false;
  $("editQuestionBtn").disabled = false;
  $("progress").textContent = session.length ? `${index + 1} / ${session.length}` : "0 / 0";
  $("bankStatus").textContent = bank ? `当前题库：${bank.name}，共 ${currentQuestions().length} 题，当前范围 ${session.length} 题` : "";
  if (!q) {
    $("stem").textContent = searchQuery.trim() ? "没有搜到匹配的题目。可以换个关键词，或切换练习范围。" : "当前范围没有题目。请导入题库，或切换练习范围。";
    $("stemMedia").innerHTML = "";
    $("answerMedia").innerHTML = "";
    $("favBtn").disabled = true;
    $("favBtn").textContent = "☆ 收藏";
    $("showBtn").disabled = true;
    $("editQuestionBtn").disabled = true;
    renderMath();
    renderQuestionMap();
    return;
  }
  $("favBtn").disabled = false;
  $("favBtn").textContent = (currentState().favorites || []).includes(q.id) ? "★ 已收藏" : "☆ 收藏";
  $("stem").innerHTML = `<span class="tag">${escapeHtml(q.normalizedType)}</span>${richHtml(q.stem)}`;
  renderMedia($("stemMedia"), q.stemImages, "题干图片");

  if (q.normalizedType === "单选题" || q.normalizedType === "多选题") {
    q.options.forEach((option, i) => {
      const letter = String.fromCharCode(65 + i);
      const btn = document.createElement("button");
      btn.className = "option";
      btn.dataset.letter = letter;
      btn.innerHTML = `<strong>${letter}.</strong><div class="option-text">${richHtml(option)}</div><div class="media"></div>`;
      renderMedia(btn.querySelector(".media"), (q.optionImages || {})[letter] || [], "选项图片");
      btn.addEventListener("click", () => chooseOption(letter));
      $("options").appendChild(btn);
    });
    if (q.normalizedType === "多选题") {
      const submit = document.createElement("button");
      submit.className = "primary";
      submit.textContent = "提交多选答案";
      submit.addEventListener("click", submitMulti);
      $("freeInput").appendChild(submit);
    }
  } else if (q.normalizedType === "判断题") {
    ["正确", "错误"].forEach(value => {
      const btn = document.createElement("button");
      btn.className = "option";
      btn.textContent = value;
      btn.addEventListener("click", () => chooseTrueFalse(value));
      $("options").appendChild(btn);
    });
  } else if (q.normalizedType === "填空题") {
    $("freeInput").innerHTML = `<input id="fillInput" type="text" placeholder="输入答案"><div style="margin-top:10px"><button class="primary" id="fillSubmit">提交答案</button></div>`;
    $("fillSubmit").addEventListener("click", checkFill);
  } else {
    $("freeInput").innerHTML = `<textarea id="qaInput" placeholder="可以先写自己的答案，再查看参考答案"></textarea>`;
  }
  const state = currentState();
  const result = state.results?.[q.id];
  const resultStatus = result && typeof result === "object" ? result.status : result;
  const resultSelection = result && typeof result === "object" ? (result.selection || "") : "";

  if (studyMode === "背题") {
    showAnswer("背题模式：直接看答案。");
    disablePracticeInputs();
  } else if ((resultStatus === "correct" || resultStatus === "wrong") && filterScope !== "错题") {
    // Restore previous answer visual state
    if (q.normalizedType === "单选题" || q.normalizedType === "多选题") {
      selected = new Set(resultSelection.split(""));
      markChoice();
    } else if (q.normalizedType === "判断题") {
      checked = true;
      const correct = normalizeBool(q.answer);
      document.querySelectorAll("#options .option").forEach(btn => {
        btn.disabled = true;
        if (btn.textContent === correct) btn.classList.add("correct");
        else if (btn.textContent === resultSelection) btn.classList.add("wrong");
      });
    } else if (q.normalizedType === "填空题") {
      if ($("fillInput") && resultSelection) $("fillInput").value = resultSelection;
      disablePracticeInputs();
    } else {
      disablePracticeInputs();
    }
    showAnswer();
  } else if (resultStatus === "seen") {
    showAnswer();
    disablePracticeInputs();
  }
  renderMath();
  renderQuestionMap();
  buildScopeFilters();
  buildTypeFilters();
}

function disablePracticeInputs() {
  checked = true;
  $("showBtn").disabled = true;
  document.querySelectorAll("#options button, #freeInput button, #freeInput input, #freeInput textarea").forEach(node => {
    node.disabled = true;
  });
}

function renderQuestionMap() {
  const state = currentState();
  const results = state.results || {};
  $("questionMap").innerHTML = session.map((q, idx) => {
    const result = results[q.id];
    const status = result && typeof result === "object" ? result.status : result;
    const cls = status === "correct" ? "correct" : status === "wrong" ? "wrong" : status === "seen" ? "seen" : "";
    const currentCls = idx === index ? "current" : "";
    return `<button class="qnav ${cls} ${currentCls}" data-index="${idx}">${idx + 1}</button>`;
  }).join("");
  document.querySelectorAll(".qnav").forEach(btn => {
    btn.addEventListener("click", () => {
      index = Number(btn.dataset.index);
      renderQuestion();
      closeQuestionMap();
    });
  });
}

function openQuestionMap() {
  renderQuestionMap();
  $("drawerBackdrop").classList.add("open");
  $("answerDrawer").classList.add("open");
}

function closeQuestionMap() {
  $("drawerBackdrop").classList.remove("open");
  $("answerDrawer").classList.remove("open");
}

function chooseOption(letter) {
  const q = current();
  if (!q || checked) return;
  if (q.normalizedType === "单选题") {
    selected = new Set([letter]);
    markChoice();
    record(normalizeLetters(q.answer) === letter);
    showAnswer();
  } else {
    selected.has(letter) ? selected.delete(letter) : selected.add(letter);
    document.querySelectorAll(".option").forEach(btn => {
      btn.classList.toggle("selected", selected.has(btn.dataset.letter));
    });
  }
}

function submitMulti() {
  const q = current();
  if (!q || checked) return;
  const ok = [...selected].sort().join("") === normalizeLetters(q.answer).split("").sort().join("");
  markChoice();
  record(ok);
  showAnswer();
}

function markChoice() {
  const q = current();
  const correct = new Set(normalizeLetters(q.answer).split(""));
  checked = true;
  document.querySelectorAll(".option").forEach(btn => {
    const letter = btn.dataset.letter;
    btn.disabled = true;
    btn.classList.remove("selected");
    if (correct.has(letter)) btn.classList.add("correct");
    else if (selected.has(letter)) btn.classList.add("wrong");
  });
}

function chooseTrueFalse(value) {
  const q = current();
  if (!q || checked) return;
  selected = new Set([value]);
  const correct = normalizeBool(q.answer);
  checked = true;
  document.querySelectorAll(".option").forEach(btn => {
    btn.disabled = true;
    if (btn.textContent === correct) btn.classList.add("correct");
    else if (btn.textContent === value) btn.classList.add("wrong");
  });
  record(value === correct);
  showAnswer();
}

function fillAnswers(q) {
  if (q.answer) return String(q.answer).split(/[，,;；/、]/).map(s => s.trim()).filter(Boolean);
  return [...String(q.stem).matchAll(/\{([^{}]+)\}/g)].map(match => match[1].trim()).filter(Boolean);
}

function checkFill() {
  const q = current();
  const user = $("fillInput").value.trim();
  const ok = user && fillAnswers(q).includes(user);
  record(Boolean(ok));
  showAnswer(ok ? "回答正确。" : "回答不完全匹配。");
}

function showAnswer(prefix = "") {
  const q = current();
  if (!q) return;
  let answer = q.answer;
  if (q.normalizedType === "填空题" && !answer) answer = fillAnswers(q).join("；");
  $("answer").classList.remove("muted");
  renderRichText($("answer"), `${prefix ? prefix + "\n" : ""}正确答案：${answer || "（空）"}\n解析：${q.analysis || ""}`);
  renderMedia($("answerMedia"), q.answerImages, "答案图片");
  $("searchAnswerBtn").style.display = looksEmptyAnswer(answer) ? "" : "none";
  const state = currentState();
  state.results ||= {};
  if (!state.results[q.id]) {
    const selection = q.normalizedType === "填空题"
      ? ($("fillInput") ? $("fillInput").value.trim() : "")
      : q.normalizedType === "问答题" ? ""
      : q.normalizedType === "判断题" ? [...selected][0] || ""
      : [...selected].sort().join("");
    state.results[q.id] = { status: "seen", selection };
    saveBanks();
  }
  renderQuestionMap();
  renderMath();
}

async function record(ok) {
  const q = current();
  if (!q) return;
  const state = currentState();
  if (ok) delete state.wrong[q.id];
  else state.wrong[q.id] = (state.wrong[q.id] || 0) + 1;
  state.results ||= {};
  const selection = q.normalizedType === "填空题"
    ? ($("fillInput") ? $("fillInput").value.trim() : "")
    : q.normalizedType === "问答题" ? ""
    : q.normalizedType === "判断题" ? [...selected][0] || ""
    : [...selected].sort().join("");
  state.results[q.id] = { status: ok ? "correct" : "wrong", selection };
  await saveBanks();
  renderStats();
  renderQuestionMap();
}

async function toggleFavorite() {
  const q = current();
  if (!q) return;
  const state = currentState();
  const favorites = new Set(state.favorites || []);
  favorites.has(q.id) ? favorites.delete(q.id) : favorites.add(q.id);
  state.favorites = [...favorites];
  await saveBanks();
  renderQuestion();
  renderStats();
}

function renderStats() {
  const el = $("stats");
  if (!el) return;
  const questions = currentQuestions();
  const state = currentState();
  const counts = {"单选题": 0, "多选题": 0, "判断题": 0, "填空题": 0, "问答题": 0};
  questions.forEach(q => counts[q.normalizedType] = (counts[q.normalizedType] || 0) + 1);
  const totalQuestions = banks.reduce((sum, bank) => sum + bank.questions.length, 0);
  const acc = bankAccuracy(currentBank());
  el.innerHTML = `
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-label">题库</div><div class="stat-value">${banks.length}</div></div>
      <div class="stat-card"><div class="stat-label">总题量</div><div class="stat-value">${totalQuestions}</div></div>
      <div class="stat-card wide"><div class="stat-label">当前题库</div><div class="stat-value">${questions.length} 题</div></div>
      <div class="stat-card"><div class="stat-label">正确率</div><div class="stat-value">${acc.text}</div></div>
      <div class="stat-card"><div class="stat-label">错题</div><div class="stat-value">${Object.keys(state.wrong || {}).length}</div></div>
      <div class="stat-card"><div class="stat-label">收藏</div><div class="stat-value">${(state.favorites || []).length}</div></div>
      <div class="stat-card"><div class="stat-label">选择题</div><div class="stat-value">${(counts["单选题"] || 0) + (counts["多选题"] || 0)}</div></div>
      <div class="stat-card"><div class="stat-label">判断</div><div class="stat-value">${counts["判断题"] || 0}</div></div>
      <div class="stat-card"><div class="stat-label">填空/问答</div><div class="stat-value">${(counts["填空题"] || 0) + (counts["问答题"] || 0)}</div></div>
    </div>
  `;
}

function exportBank() {
  const bank = currentBank();
  if (!bank) {
    alert("当前没有题库可导出。");
    return;
  }
  const blob = new Blob([JSON.stringify(bank.questions, null, 2)], {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${bank.name || "题库"}_导出.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function exportUserData() {
  window.location.href = "/api/export-user-data";
}

async function importUserData(file) {
  const data = JSON.parse(await file.text());
  const incomingBanks = Array.isArray(data) ? data : data.banks;
  if (!Array.isArray(incomingBanks)) throw new Error("用户数据文件格式不正确。");
  banks = incomingBanks.map(bank => ({
    id: String(bank.id || uid()),
    name: String(bank.name || "未命名题库"),
    questions: (bank.questions || []).map(asQuestion),
    state: {
      favorites: Array.isArray(bank.state?.favorites) ? bank.state.favorites : [],
      wrong: bank.state?.wrong && typeof bank.state.wrong === "object" ? bank.state.wrong : {},
      results: bank.state?.results && typeof bank.state.results === "object" ? bank.state.results : {},
    },
    createdAt: bank.createdAt || new Date().toISOString(),
  }));
  currentBankId = typeof data.currentBankId === "string" && banks.some(bank => bank.id === data.currentBankId)
    ? data.currentBankId
    : banks[0]?.id || "";
  await saveBanks();
  renderBankSelect();
  startSession();
  renderStats();
  alert(`已导入用户数据：${banks.length} 个题库。`);
}

async function deleteCurrentBank() {
  const bank = currentBank();
  if (!bank) return;
  if (!confirm(`确定删除题库"${bank.name}"及其收藏、错题记录吗？`)) return;
  banks = banks.filter(item => item.id !== bank.id);
  currentBankId = banks[0]?.id || "";
  await saveBanks();
  renderBankSelect();
  startSession();
  renderStats();
}

async function clearAll() {
  if (!confirm("确定清空所有题库、收藏和错题记录吗？")) return;
  banks = [];
  currentBankId = "";
  await saveBanks();
  renderBankSelect();
  startSession();
  renderStats();
}

async function migrateOldSingleBank() {
  const oldBank = await dbGet("bank", []);
  if (!Array.isArray(oldBank) || !oldBank.length) return;
  const oldState = await dbGet("state", { favorites: [], wrong: {} });
  banks = [{
    id: uid(),
    name: "旧版合并题库",
    questions: oldBank.map(asQuestion),
    state: oldState || { favorites: [], wrong: {} },
    createdAt: new Date().toISOString(),
  }];
  currentBankId = banks[0].id;
  await saveBanks();
}

async function boot() {
  // Attach ALL event listeners first (before any async that could fail)
  document.querySelectorAll(".nav-header").forEach(btn => {
    btn.addEventListener("click", () => {
      const view = btn.dataset.view;
      if (view === "practice") {
        const navItem = btn.closest(".nav-item");
        if (currentView === "practice" && navItem.classList.contains("open")) {
          navItem.classList.toggle("open");
        } else {
          switchView("practice");
        }
      } else {
        switchView(view);
      }
    });
  });
  $("profileBankSelect").onchange = () => renderProfile();
  $("pickFolderBtn").onclick = () => $("folderInput").click();
  $("pickJsonBtn").onclick = () => $("jsonInput").click();
  $("bankManagerSearch").oninput = renderManagement;
  $("exportUserDataBtn").onclick = exportUserData;
  $("importUserDataBtn").onclick = () => $("userDataInput").click();
  $("folderInput").onchange = async event => {
    try { await importFolder(event.target.files); switchView("management"); }
    catch (err) { alert("导入失败：" + err.message); }
    event.target.value = "";
  };
  $("jsonInput").onchange = async event => {
    try { if (event.target.files[0]) await importJson(event.target.files[0]); switchView("management"); }
    catch (err) { alert("导入失败：" + err.message); }
    event.target.value = "";
  };
  $("userDataInput").onchange = async event => {
    try { if (event.target.files[0]) await importUserData(event.target.files[0]); switchView("management"); }
    catch (err) { alert("导入用户数据失败：" + err.message); }
    event.target.value = "";
  };
  $("bankSelect").onchange = async event => {
    currentBankId = event.target.value;
    await saveBanks();
    startSession();
    renderBankSelect();
  };
  $("searchInput").oninput = event => {
    searchQuery = event.target.value;
    startSession();
  };
  $("restartBtn").onclick = startSession;
  $("shuffleInput").onchange = startSession;
  document.querySelectorAll("input[name=studyMode]").forEach(input => {
    input.addEventListener("change", () => {
      studyMode = input.value;
      renderQuestion();
    });
  });
  $("editQuestionBtn").onclick = openQuestionEditor;
  $("closeQuestionEditorBtn").onclick = closeQuestionEditor;
  $("cancelQuestionEditBtn").onclick = closeQuestionEditor;
  $("saveQuestionEditBtn").onclick = saveQuestionEdit;
  $("questionEditorBackdrop").onclick = event => { if (event.target === $("questionEditorBackdrop")) closeQuestionEditor(); };
  $("mapBtn").onclick = openQuestionMap;
  $("closeMapBtn").onclick = closeQuestionMap;
  $("drawerBackdrop").onclick = closeQuestionMap;
  $("favBtn").onclick = toggleFavorite;
  $("prevBtn").onclick = () => { if (index > 0) { index--; renderQuestion(); } };
  $("nextBtn").onclick = () => { if (index < session.length - 1) { index++; renderQuestion(); } };
  $("showBtn").onclick = () => showAnswer();
  $("searchAnswerBtn").onclick = searchAnswerOnline;
  $("saveAnswerBtn").onclick = saveCurrentAnswer;
  $("closePreviewBtn").onclick = closeImagePreview;
  $("imagePreview").onclick = event => { if (event.target === $("imagePreview")) closeImagePreview(); };
  $("zoomInBtn").onclick = () => setPreviewScale(previewScale + 0.25);
  $("zoomOutBtn").onclick = () => setPreviewScale(previewScale - 0.25);
  $("zoomResetBtn").onclick = () => setPreviewScale(1);
  $("imageStage").addEventListener("wheel", handlePreviewWheel, { passive: false });
  $("imageStage").addEventListener("mousedown", startPreviewDrag);
  document.addEventListener("mousemove", movePreviewDrag);
  document.addEventListener("mouseup", stopPreviewDrag);
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeImagePreview();
  });
  $("exportBtn").onclick = exportBank;
  $("clearWrongBtn").onclick = async () => {
    const state = currentState();
    state.wrong = {};
    state.results = {};
    await saveBanks();
    startSession();
  };
  $("clearAllBtn").onclick = clearAll;
  $("shutdownBtn").onclick = () => fetch("/shutdown").finally(() => {
    document.body.innerHTML = "<main style='font-family:Microsoft YaHei UI,sans-serif;padding:32px'>程序已退出，可以关闭这个页面。</main>";
  });
  window.addEventListener("beforeunload", () => {
    try {
      const blob = new Blob([JSON.stringify(appDataPayload())], { type: "application/json" });
      navigator.sendBeacon("/api/save-data", blob);
    } catch {}
  });

  // Load data (wrapped in try/catch so UI stays interactive even if this fails)
  try {
    const fileData = await apiJson("/api/user-data", {}, { banks: [], currentBankId: "" });
    const localBanks = await dbGet("banks", []);
    const localBankId = await dbGet("currentBankId", "");
    const serverBanks = Array.isArray(fileData?.banks) ? fileData.banks : [];
    const serverBankId = typeof fileData?.currentBankId === "string" ? fileData.currentBankId : "";
    banks = localBanks.length ? localBanks : serverBanks;
    currentBankId = localBankId || serverBankId;
    if (!Array.isArray(banks)) banks = [];
    if (!banks.length) await migrateOldSingleBank();
    banks.forEach(bank => {
      bank.questions = (bank.questions || []).map(asQuestion);
      bank.state ||= { favorites: [], wrong: {}, results: {} };
      bank.state.favorites ||= [];
      bank.state.wrong ||= {};
      bank.state.results ||= {};
    });
    if (!banks.some(bank => bank.id === currentBankId)) currentBankId = banks[0]?.id || "";
    await saveBanks();
    buildScopeFilters();
  buildTypeFilters();
    renderBankSelect();
    if (banks.length && currentBankId) {
      startSession();
      switchView("practice");
    } else {
      switchView("welcome");
    }
  } catch (err) {
    console.error("数据加载失败:", err);
    switchView("welcome");
  }
}

boot();
</script>
</body>
</html>
"""

def html_unescape(text: str) -> str:
    replacements = {
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
        "&nbsp;": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)


def strip_tags(text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html_unescape(text)).strip()


def search_answer(query: str) -> list[dict[str, str]]:
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        },
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    results = []
    for match in re.finditer(r'<li class="b_algo"[\s\S]*?</li>', html):
        block = match.group(0)
        link = re.search(r'<a href="([^"]+)"[^>]*>([\s\S]*?)</a>', block)
        if not link:
            continue
        snippet_match = re.search(r"<p[^>]*>([\s\S]*?)</p>", block)
        results.append({
            "title": strip_tags(link.group(2)),
            "url": html_unescape(link.group(1)),
            "snippet": strip_tags(snippet_match.group(1)) if snippet_match else "",
        })
        if len(results) >= 5:
            break
    return results


class Handler(BaseHTTPRequestHandler):
    server_version = "FojiaoQuiz/1.0"

    def send_json(self, payload: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        if self.path.startswith("/shutdown"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("bye".encode("utf-8"))
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path.startswith("/api/user-data"):
            self.send_json(load_user_data())
            return
        if self.path.startswith("/api/export-user-data"):
            payload = load_user_data()
            payload["exportedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="fojiao_quiz_user_data.json"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path.startswith("/search_answer"):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("q", [""])[0]
            try:
                payload = {"results": search_answer(query) if query else []}
            except Exception as exc:
                payload = {"results": [], "error": str(exc)}
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(APP_HTML.encode("utf-8"))

    def do_POST(self):
        if self.path.startswith("/api/save-data"):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                data = json.loads(raw) if raw else {}
                if not isinstance(data, dict):
                    raise ValueError("payload must be an object")
                save_user_data(data)
                self.send_json({"ok": True})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, 400)
            return
        self.send_json({"ok": False, "error": "not found"}, 404)

    def log_message(self, format, *args):
        return


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    port = find_free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    threading.Thread(target=lambda: (time.sleep(0.4), webbrowser.open(url)), daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
