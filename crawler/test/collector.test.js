// 爬虫核心逻辑测试（node:test，Node 18+）
// 运行: node --test test/
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { isNotificationListPage } = require('../src/collectors/collector');

// 苏迪 CMS 列表页特征：news_title + news_meta 数量匹配
const listHtml = `
<html><body>
  <ul class="news_list">
    <li class="news"><span class="news_title"><a href="/a">通知一</a></span><span class="news_meta">2026-01-01</span></li>
    <li class="news"><span class="news_title"><a href="/b">通知二</a></span><span class="news_meta">2026-01-02</span></li>
    <li class="news"><span class="news_title"><a href="/c">通知三</a></span><span class="news_meta">2026-01-03</span></li>
    <li class="news"><span class="news_title"><a href="/d">通知四</a></span><span class="news_meta">2026-01-04</span></li>
  </ul>
</body></html>`;

test('news_title 列表页识别', () => {
  assert.equal(isNotificationListPage(listHtml, 'news_title'), true);
});

test('文章详情页不识别为列表页', () => {
  const articleHtml = '<html><body><div class="article"><h1>标题</h1><p>正文</p></div></body></html>';
  assert.equal(isNotificationListPage(articleHtml, 'news_title'), false);
});

test('维护页/占位页不识别为列表页', () => {
  const maintenanceHtml = '<html><body><div id="app"><h1>网络维护</h1></div></body></html>';
  assert.equal(isNotificationListPage(maintenanceHtml, 'news_title'), false);
});

test('无策略时启发式识别', () => {
  assert.equal(isNotificationListPage(listHtml, null), true);
  assert.equal(isNotificationListPage('<html><body>空</body></html>', null), false);
});

test('link-title 列表页识别', () => {
  const linkHtml = `
  <ul>
    <li><a class="link-title" href="/a">公告一</a><span class="time">2026-01-01</span></li>
    <li><a class="link-title" href="/b">公告二</a><span class="time">2026-01-02</span></li>
    <li><a class="link-title" href="/c">公告三</a><span class="time">2026-01-03</span></li>
    <li><a class="link-title" href="/d">公告四</a><span class="time">2026-01-04</span></li>
    <li><a class="link-title" href="/e">公告五</a><span class="time">2026-01-05</span></li>
    <li><a class="link-title" href="/f">公告六</a><span class="time">2026-01-06</span></li>
  </ul>`;
  assert.equal(isNotificationListPage(linkHtml, 'link-title'), true);
});

test('微信外链不作为通知提取', () => {
  const { extractNotices } = require('../src/collectors/collector');
  // 含一个微信外链 + 一个站内通知
  const html = `
  <ul>
    <li class="news"><span class="news_title"><a href="https://cs.nju.edu.cn/a/page.htm">站内通知一</a></span><span class="news_meta">2026-01-01</span></li>
    <li class="news"><span class="news_title"><a href="https://mp.weixin.qq.com/s/abc">微信公众号文章</a></span><span class="news_meta">2026-01-02</span></li>
  </ul>`;
  const notices = extractNotices(html, 'https://cs.nju.edu.cn/');
  assert.equal(notices.length, 1);
  assert.equal(notices[0].href, 'https://cs.nju.edu.cn/a/page.htm');
  assert.ok(!notices.some(n => /weixin/.test(n.href)));
});
