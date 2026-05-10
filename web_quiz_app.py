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
  <title>佛脚刷题</title>
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
    aside { border-right: 1px solid var(--line); background: var(--rail); padding: 18px; height: 100vh; overflow: auto; position: sticky; top: 0; }
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
    @media (max-width: 820px) {
      .app { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      main { padding: 14px; }
      .answer-drawer { width: min(92vw, 520px); }
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
        <h1>佛脚刷题</h1>
        <p>本地题库、错题与收藏自动保存。</p>
      </div>
      <div class="stack">
        <button class="primary" id="pickFolderBtn">导入题库文件夹</button>
        <button id="pickJsonBtn">只导入 JSON</button>
        <button id="manageBanksBtn">题库管理</button>
        <button id="exportBtn">导出当前题库</button>
        <button id="exportUserDataBtn">导出用户数据</button>
        <button id="importUserDataBtn">导入用户数据</button>
      </div>
      <input id="folderInput" class="hidden-file" type="file" webkitdirectory directory multiple>
      <input id="jsonInput" class="hidden-file" type="file" accept=".json,application/json">
      <input id="userDataInput" class="hidden-file" type="file" accept=".json,application/json">

      <div class="panel" style="margin-top:16px">
        <strong class="section-title">当前题库</strong>
        <select id="bankSelect" style="margin-top:8px"></select>
        <div class="row" style="margin-top:10px">
          <button id="deleteBankBtn" class="danger">删除当前题库</button>
        </div>
      </div>

      <div class="panel">
        <strong class="section-title">练习范围</strong>
        <div class="filters" id="filters"></div>
        <input id="searchInput" type="text" placeholder="搜索题干、选项、答案、解析" style="margin-top:8px">
        <label class="row small"><input type="checkbox" id="shuffleInput"> 随机顺序</label>
        <button id="restartBtn" style="width:100%;margin-top:8px">重新开始</button>
      </div>

      <div class="panel">
        <strong class="section-title">学习模式</strong>
        <label class="row small" style="margin-top:8px"><input type="radio" name="studyMode" value="刷题" checked> 刷题模式</label>
        <label class="row small"><input type="radio" name="studyMode" value="背题"> 背题模式</label>
      </div>

      <div class="stats" id="stats"></div>
      <div class="stack" style="margin-top:14px">
        <button id="clearWrongBtn">清空当前错题</button>
        <button id="clearAllBtn" class="danger">清空所有题库</button>
        <button id="shutdownBtn">退出程序</button>
      </div>
    </aside>

    <main>
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

      <div class="panel small muted" style="margin-top:14px">
        每次导入都会创建一个独立题库，并自动保存到程序目录的 user_data 文件夹。文件夹导入建议：一个文件夹里放一个 JSON 文件和一个 images 文件夹。
        JSON 中写相对路径，例如 <code>"题干图片":["images/mol.png"]</code>，
        <code>"选项图片":{"A":["images/a.png"]}</code>，<code>"答案图片":["images/answer.png"]</code>。
      </div>
    </main>
  </div>

  <div id="drawerBackdrop" class="drawer-backdrop"></div>
  <div id="bankManagerBackdrop" class="modal-backdrop">
    <div class="modal">
      <div class="row">
        <strong class="grow">题库管理</strong>
        <button id="closeBankManagerBtn">关闭</button>
      </div>
      <input id="bankManagerSearch" type="text" placeholder="检索题库名称" style="margin-top:12px">
      <div id="bankManagerSummary" class="manager-summary"></div>
      <div id="bankManagerList"></div>
    </div>
  </div>
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
const TYPES = ["全部", "单选题", "多选题", "判断题", "填空题", "问答题", "收藏", "错题"];

let banks = [];
let currentBankId = "";
let session = [];
let index = 0;
let mode = "全部";
let studyMode = "刷题";
let searchQuery = "";
let selected = new Set();
let checked = false;
let previewScale = 1;
let previewDragging = false;
let previewDragStart = { x: 0, y: 0, left: 0, top: 0 };

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
  alert(`已创建题库“${currentBank()?.name || ""}”，导入 ${imported.length} 道题。`);
}

async function importJson(file) {
  const raw = JSON.parse(await file.text());
  if (!Array.isArray(raw)) throw new Error("JSON 顶层必须是题目数组。");
  await addBank(file.name.replace(/\.json$/i, ""), raw.map(asQuestion));
  alert(`已创建题库“${currentBank()?.name || ""}”，导入 ${raw.length} 道题。只导入 JSON 时，浏览器通常不能直接读取本地图片路径；带图片请用“导入题库文件夹”。`);
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

function buildFilters() {
  $("filters").innerHTML = TYPES.map(type => `
    <label><input type="radio" name="mode" value="${type}" ${type === mode ? "checked" : ""}> ${type}</label>
  `).join("");
  document.querySelectorAll("input[name=mode]").forEach(input => {
    input.addEventListener("change", () => {
      mode = input.value;
      startSession();
    });
  });
}

function renderBankSelect() {
  $("bankSelect").innerHTML = banks.map(bank => {
    const selectedAttr = bank.id === currentBankId ? "selected" : "";
    return `<option value="${bank.id}" ${selectedAttr}>${escapeHtml(bank.name)} (${bank.questions.length})</option>`;
  }).join("");
}

function bankAccuracy(bank) {
  const results = bank?.state?.results || {};
  let correct = 0;
  let wrong = 0;
  Object.values(results).forEach(value => {
    if (value === "correct") correct++;
    if (value === "wrong") wrong++;
  });
  const answered = correct + wrong;
  return {
    correct,
    wrong,
    answered,
    text: answered ? `${Math.round(correct * 1000 / answered) / 10}%` : "未作答",
  };
}

function renderBankManager() {
  const query = $("bankManagerSearch")?.value.trim().toLowerCase() || "";
  const visibleBanks = banks.filter(bank => !query || bank.name.toLowerCase().includes(query));
  const totalQuestions = banks.reduce((sum, bank) => sum + (bank.questions?.length || 0), 0);
  const totalAnswered = banks.reduce((sum, bank) => sum + bankAccuracy(bank).answered, 0);
  const totalCorrect = banks.reduce((sum, bank) => sum + bankAccuracy(bank).correct, 0);
  const totalWrong = banks.reduce((sum, bank) => sum + Object.keys(bank.state?.wrong || {}).length, 0);
  $("bankManagerSummary").innerHTML = `
    <div class="stat-card"><div class="stat-label">题库</div><div class="stat-value">${banks.length}</div></div>
    <div class="stat-card"><div class="stat-label">题量</div><div class="stat-value">${totalQuestions}</div></div>
    <div class="stat-card"><div class="stat-label">已判题</div><div class="stat-value">${totalAnswered}</div></div>
    <div class="stat-card"><div class="stat-label">总正确率</div><div class="stat-value">${totalAnswered ? Math.round(totalCorrect * 1000 / totalAnswered) / 10 + "%" : "未作答"}</div></div>
  `;
  if (!visibleBanks.length) {
    $("bankManagerList").innerHTML = `<p class="muted">没有匹配的题库。</p>`;
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
        renderStats();
        renderBankManager();
      } else if (btn.dataset.action === "rename") {
        const nextName = prompt("输入新的题库名称", bank.name);
        if (!nextName || !nextName.trim()) return;
        bank.name = nextName.trim();
        await saveBanks();
        renderBankSelect();
        renderStats();
        renderBankManager();
      } else if (btn.dataset.action === "delete") {
        if (!confirm(`确定删除题库“${bank.name}”及其收藏、错题记录吗？`)) return;
        banks = banks.filter(item => item.id !== bank.id);
        if (currentBankId === bank.id) currentBankId = banks[0]?.id || "";
        await saveBanks();
        renderBankSelect();
        startSession();
        renderStats();
        renderBankManager();
      }
    });
  });
}

function openBankManager() {
  renderBankManager();
  $("bankManagerBackdrop").classList.add("open");
}

function closeBankManager() {
  $("bankManagerBackdrop").classList.remove("open");
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
  const favorites = new Set(state.favorites || []);
  const wrong = new Set(Object.keys(state.wrong || {}));
  if (mode === "全部") session = [...questions];
  else if (mode === "收藏") session = questions.filter(q => favorites.has(q.id));
  else if (mode === "错题") session = questions.filter(q => wrong.has(q.id));
  else session = questions.filter(q => q.normalizedType === mode);
  session = session.filter(matchesSearch);
  if ($("shuffleInput").checked) session.sort(() => Math.random() - 0.5);
  index = 0;
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
  if (studyMode === "背题") {
    showAnswer("背题模式：直接看答案。");
    disablePracticeInputs();
  }
  renderMath();
  renderQuestionMap();
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
    const cls = result === "correct" ? "correct" : result === "wrong" ? "wrong" : result === "seen" ? "seen" : "";
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
    state.results[q.id] = "seen";
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
  state.results[q.id] = ok ? "correct" : "wrong";
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
  const questions = currentQuestions();
  const state = currentState();
  const counts = {"单选题": 0, "多选题": 0, "判断题": 0, "填空题": 0, "问答题": 0};
  questions.forEach(q => counts[q.normalizedType] = (counts[q.normalizedType] || 0) + 1);
  const totalQuestions = banks.reduce((sum, bank) => sum + bank.questions.length, 0);
  const acc = bankAccuracy(currentBank());
  $("stats").innerHTML = `
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
  renderBankManager();
  alert(`已导入用户数据：${banks.length} 个题库。`);
}

async function deleteCurrentBank() {
  const bank = currentBank();
  if (!bank) return;
  if (!confirm(`确定删除题库“${bank.name}”及其收藏、错题记录吗？`)) return;
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
  const fileData = await apiJson("/api/user-data", {}, { banks: [], currentBankId: "" });
  banks = Array.isArray(fileData?.banks) && fileData.banks.length ? fileData.banks : await dbGet("banks", []);
  currentBankId = typeof fileData?.currentBankId === "string" && fileData.currentBankId ? fileData.currentBankId : await dbGet("currentBankId", "");
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

  buildFilters();
  renderBankSelect();
  renderStats();
  startSession();

  $("pickFolderBtn").onclick = () => $("folderInput").click();
  $("pickJsonBtn").onclick = () => $("jsonInput").click();
  $("manageBanksBtn").onclick = openBankManager;
  $("closeBankManagerBtn").onclick = closeBankManager;
  $("bankManagerBackdrop").onclick = event => { if (event.target === $("bankManagerBackdrop")) closeBankManager(); };
  $("bankManagerSearch").oninput = renderBankManager;
  $("editQuestionBtn").onclick = openQuestionEditor;
  $("closeQuestionEditorBtn").onclick = closeQuestionEditor;
  $("cancelQuestionEditBtn").onclick = closeQuestionEditor;
  $("saveQuestionEditBtn").onclick = saveQuestionEdit;
  $("questionEditorBackdrop").onclick = event => { if (event.target === $("questionEditorBackdrop")) closeQuestionEditor(); };
  $("exportUserDataBtn").onclick = exportUserData;
  $("importUserDataBtn").onclick = () => $("userDataInput").click();
  $("folderInput").onchange = async event => {
    try { await importFolder(event.target.files); }
    catch (err) { alert("导入失败：" + err.message); }
    event.target.value = "";
  };
  $("jsonInput").onchange = async event => {
    try { if (event.target.files[0]) await importJson(event.target.files[0]); }
    catch (err) { alert("导入失败：" + err.message); }
    event.target.value = "";
  };
  $("userDataInput").onchange = async event => {
    try { if (event.target.files[0]) await importUserData(event.target.files[0]); }
    catch (err) { alert("导入用户数据失败：" + err.message); }
    event.target.value = "";
  };
  $("bankSelect").onchange = async event => {
    currentBankId = event.target.value;
    await saveBanks();
    startSession();
    renderStats();
  };
  $("deleteBankBtn").onclick = deleteCurrentBank;
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
    renderStats();
  };
  $("clearAllBtn").onclick = clearAll;
  $("shutdownBtn").onclick = () => fetch("/shutdown").finally(() => {
    document.body.innerHTML = "<main style='font-family:Microsoft YaHei UI,sans-serif;padding:32px'>程序已退出，可以关闭这个页面。</main>";
  });
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
