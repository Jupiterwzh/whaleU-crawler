/**
 * browser-start.js — 启动浏览器服务（后台运行）
 *
 * 用法：
 *   node browser-start.js
 *
 * 启动后保持此窗口打开，浏览器服务在后台运行。
 * 新开一个终端窗口运行爬虫命令。
 */

const { spawn, execSync } = require('child_process');
const http = require('http');
const path = require('path');
const fs = require('fs');
const { cwd } = require('process');

const PORT = 4100;
const HOST = '127.0.0.1';
const BROWSER_DIR = path.join(__dirname, '..', 'browser');
const SERVER_SCRIPT = path.join(BROWSER_DIR, 'nju-browser-server.js');

const CHROME_PATHS = [
  path.join(BROWSER_DIR, 'chrome', 'chrome-win64', 'chrome.exe'),
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  path.join(process.env.LOCALAPPDATA || '', 'Google', 'Chrome', 'Application', 'chrome.exe'),
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
];

function findBrowser() {
  for (const p of CHROME_PATHS) {
    if (fs.existsSync(p)) {
      console.log(`[browser] Found: ${p}`);
      return p;
    }
  }
  return null;
}

function checkServer() {
  return new Promise((resolve) => {
    const req = http.request({ hostname: HOST, port: PORT, path: '/status', method: 'GET' }, (res) => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch { resolve(null); } });
    });
    req.on('error', () => resolve(null));
    req.setTimeout(3000, () => { req.destroy(); resolve(null); });
    req.end();
  });
}

async function main() {
  console.log('\n============================================');
  console.log('  Auto Info Retrieval - Browser Launcher');
  console.log('============================================\n');

  // Check existing server
  const existing = await checkServer();
  if (existing && existing.alive) {
    console.log('[browser] Server already running on port', PORT);
    if (existing.loggedIn) {
      console.log('[browser] Already logged in\n');
    } else {
      console.log('[browser] Server started, waiting for login...\n');
    }
    return;
  }

  // Find browser
  const browserPath = findBrowser();
  if (!browserPath) {
    console.error('[browser] Chrome or Edge not found!');
    process.exit(1);
  }

  // Check server script
  if (!fs.existsSync(SERVER_SCRIPT)) {
    console.error('[browser] Not found:', SERVER_SCRIPT);
    process.exit(1);
  }

  // Start server in new window using 'start' command
  console.log('[browser] Starting browser server...\n');
  const envArgs = `PORT=${PORT} HOST=${HOST} CHROME_PATH=${browserPath}`;
  try {
    execSync(
      `start "NJU Browser Server" cmd /c "title NJU Browser Server && cd /d "${BROWSER_DIR}" && set ${envArgs} && node nju-browser-server.js"`,
      { stdio: 'ignore', cwd: BROWSER_DIR }
    );
  } catch (e) {
    // start may not throw even on failure, check below
  }

  // Wait for server to be ready
  console.log('[browser] Waiting for server (max 60s)...\n');
  let ready = false;
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 2000));
    const s = await checkServer();
    if (s && s.alive) {
      ready = true;
      break;
    }
    process.stdout.write('.');
  }

  console.log('\n');
  if (ready) {
    console.log('[browser] Server ready!');
    console.log('[browser] Open a new terminal and run:');
    console.log('       node collector.js --notices <URL>');
    console.log('[browser] Or double-click "Crawler HTTP.bat" for HTTP mode.\n');
  } else {
    console.error('[browser] Server start timed out.\n');
    process.exit(1);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
