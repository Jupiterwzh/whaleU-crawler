# NJU Browser — OpenCode Skill

> 南京大学统一身份认证 + 智能搜索爬虫工具集
> 基于 Puppeteer + HTTP API 的持久化浏览器代理

## 架构

```
nju-browser-start.js    启动服务器 → 立即退出（后台独立进程）
        │
        ▼
nju-browser-server.js   HTTP 服务器 + Chrome for Testing 浏览器（持久运行）
        │
        ▼
nju-query.js            查询工具（秒回）
```

## 浏览器说明

- Puppeteer 默认下载的 Chrome/Chromium 150 在当前 Windows build 10.0.26200.8875 上启动失败，错误码为 2147483651
- 已安装并验证可用 Chrome for Testing 148.0.7778.97
- 服务器不再硬编码路径：优先 `CHROME_PATH` 环境变量，未设置则交给 puppeteer 自动查找（`npm install` 下载的 Chrome）；若需指定某个 Chrome 可执行文件，设 `CHROME_PATH=<chrome可执行文件的完整路径>`（例如 Chrome for Testing 的 chrome.exe）
- Microsoft Edge 也可用，但当前优先使用已修复的 Chromium/Chrome for Testing 方案

## 使用方法

### 1. 启动服务器

```bash
node nju-browser-start.js
```

- 启动 Chrome for Testing 浏览器窗口
- 显示 NJU 统一身份认证页面（二维码、账号密码登录均可）
- **脚本立即退出**，服务器在后台继续运行

### 2. 登录

服务器启动后，浏览器窗口会打开 `search.nju.edu.cn` 并跳转到统一身份认证页面。登录方式：

- **扫码登录（推荐）**：使用南京大学 App / 微信扫码
- **账号密码登录**：在浏览器窗口中手动输入学号和密码（当前采用）

登录后服务器自动检测到登录状态，搜索功能即可使用。

### 3. 查询搜索

```bash
# 检查状态
node nju-query.js

# 搜索关键词
node nju-query.js "机器学习"
node nju-query.js "南京大学 AI 成果" zh
node nju-query.js "新闻" xwzx
node nju-query.js "讲座" xsbg
```

参数: `关键词 [类型] [页码] [每页条数]`

| 类型 | 说明 |
|------|------|
| `zh` | 综合（默认） |
| `xwzx` | 新闻资讯 |
| `xmt` | 公众号 |
| `xsbg` | 学术讲座 |
| `jszy` | 教师主页 |
| `image` | 图片 |
| `video` | 视频 |

### 4. 关服务器

```bash
curl -X POST http://127.0.0.1:4100/shutdown
```

## API 参考

服务器运行后暴露 HTTP API：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/status` | 服务器状态、登录态 |
| POST | `/search` | `{"keyword":"...","type":"zh","page":1,"size":10}` |
| POST | `/navigate` | `{"url":"..."}` 导航到指定页面 |
| GET | `/screenshot` | 截图 PNG |
| POST | `/evaluate` | `{"js":"document.title"}` 执行 JS |
| POST | `/shutdown` | 关闭服务器和浏览器 |

## Cookie 持久化

- 登录后 session 有效期为浏览器窗口开启期间
- 关服务器后 session 丢失，需重新登录
- 后台异步检测登录完成，不阻塞 HTTP 服务

## 文件说明

| 文件 | 说明 |
|------|------|
| `nju-browser-start.js` | 启动器：启动服务器后立即退出 |
| `nju-browser-server.js` | HTTP 服务器 + Puppeteer + Chrome for Testing 浏览器管理 |
| `nju-query.js` | 查询 CLI：快速搜索 |
| `nju-search.js` | 旧版 HTTP 搜索工具 |
| `nju-aisearch.js` | 旧版 API 探索工具 |