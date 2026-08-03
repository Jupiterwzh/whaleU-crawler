/**
 * nju-browser-start.js
 *
 * 启动浏览器服务器 → 退出。
 * 服务器在后台独立运行。
 *
 * 用法: node nju-browser-start.js
 */
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

const PORT = 4100;
const SCRIPT = path.join(__dirname, 'nju-browser-server.js');
const LOG = path.join(__dirname, '.nju-server.log');

function isAlive() {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${PORT}/status`, (res) => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => {
        try { resolve(JSON.parse(d)?.alive === true); }
        catch { resolve(false); }
      });
    });
    req.setTimeout(3000, () => {
      req.destroy();
      resolve(false);
    });
    req.on('error', () => resolve(false));
    req.end();
  });
}

(async () => {
  if (await isAlive()) {
    console.log('[start] 服务器已在运行');
    process.exit(0);
  }

  const out = fs.openSync(LOG, 'a');
  const child = spawn(process.execPath, [SCRIPT, `--port=${PORT}`], {
    cwd: __dirname,
    detached: true,
    stdio: ['ignore', out, out],
    windowsHide: false,
  });
  child.unref();

  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 1000));
    if (await isAlive()) {
      console.log('[start] 服务器已启动');
      console.log('[start] 脚本退出（进程保留在后台）');
      console.log(`[start] 日志: ${LOG}`);
      process.exit(0);
    }
  }

  console.log('[start] 启动超时');
  console.log(`[start] 请查看日志: ${LOG}`);
  process.exit(1);
})();
