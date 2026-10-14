'use strict';

/**
 * scripts/smoke-renderer.js —— 用 jsdom 冒烟测试渲染端：
 *  - 精灵 SVG 注入 DOM 后关键节点存在
 *  - 初始化不抛异常（relayout / 状态机 / rAF 主循环）
 *  - 点击头部 / 点击翅膀 / 点播大招 / 说话气泡 的完整链路
 * 运行：node scripts/smoke-renderer.js
 */

const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert');

process.on('uncaughtException', (error) => {
  console.error('SMOKE-RENDERER uncaughtException:', error && error.stack ? error.stack : error);
  process.exit(2);
});

const jsdomPath = path.join(process.cwd(), 'build', 'jsdom-env', 'node_modules', 'jsdom');
const { JSDOM } = require(jsdomPath);

const html = fs.readFileSync(path.join(process.cwd(), 'src', 'renderer', 'index.html'), 'utf8');

const dom = new JSDOM(html, {
  url: 'file:///fake/index.html',
  runScripts: 'outside-only',
  pretendToBeVisual: true,
});

const { window } = dom;
window.screenX = 100;
window.screenY = 200;

// ---- 伪 desktopPet（preload 桥）----
const apiEvents = {};
const apiCalls = [];
window.desktopPet = {
  ready: () => apiCalls.push('ready'),
  pointer: (p) => apiCalls.push(`pointer:${p.phase}`),
  activity: () => apiCalls.push('activity'),
  action: (a) => apiCalls.push(`action:${a}`),
  speakDone: () => apiCalls.push('speakDone'),
  getConfig: () => Promise.resolve({ size: 220, roam: true, speech: true, clickThrough: false }),
  setConfig: () => Promise.resolve({}),
  contextMenu: () => apiCalls.push('contextMenu'),
  setIgnoreMouse: () => {},
  quit: () => {},
  on: (channel, handler) => {
    (apiEvents[channel] = apiEvents[channel] || []).push(handler);
    return () => {};
  },
};

const read = (f) => fs.readFileSync(path.join(process.cwd(), 'src', 'renderer', f), 'utf8');
window.eval(read('sprite.js'));
window.eval(read('fx.js'));
window.eval(read('renderer.js'));

const doc = window.document;

// ---- 断言 1：立绘元素存在（本体是 assets/stand.png，jsdom 不会真的加载图片）----
assert.ok(doc.getElementById('pet-img'), '立绘元素存在');
assert.strictEqual(doc.getElementById('pet-img').getAttribute('src'), '../../assets/stand.png', '立绘路径正确');
assert.ok(doc.getElementById('pet'), '#pet 容器存在');
assert.ok(doc.getElementById('sprite'), '#sprite 容器存在');
assert.ok(doc.querySelector('.pet-aura'), '柔光层存在');
console.log('[ok] 立绘与容器节点齐全');

// ---- 断言 2：初始化后 ready 类与状态类 ----
setTimeout(() => {
  assert.ok(doc.body.classList.contains('ready'), 'body.ready 已添加');
  const pet = doc.getElementById('pet');
  assert.ok(pet.classList.contains('state-idle'), '初始 state-idle');
  assert.ok(apiCalls.includes('ready'), 'api.ready 被调用');
  console.log('[ok] 初始化完成');

  // ---- 断言 3：气泡说话 ----
  apiEvents['pet:play'].forEach((h) => h({ action: 'talk' }));
  const bubble = doc.getElementById('bubble');
  assert.ok(bubble.classList.contains('show'), '气泡显示');
  assert.ok(doc.getElementById('bubble-text').textContent.length > 0, '气泡有文字');
  console.log('[ok] 说话气泡:', doc.getElementById('bubble-text').textContent);

  // ---- 断言 4：点击身体 → 从表情库里挑一个反应（粒子是 110ms 一发的延时队列）----
  const head = doc.getElementById('pet-img') || doc.getElementById('pet');
  const animClasses = () =>
    [...pet.classList].filter((c) => c.startsWith('anim-')).join(',');
  const formClasses = () =>
    [...pet.classList].filter((c) => c.startsWith('form-')).join(',');
  const clickOnce = () => {
    head.dispatchEvent(new window.MouseEvent('pointerdown', { bubbles: true, button: 0, pointerId: 1, clientX: 50, clientY: 200 }));
    window.dispatchEvent(new window.MouseEvent('pointerup', { bubbles: true, button: 0, pointerId: 1, clientX: 50, clientY: 200 }));
  };
  // 单击：可能抽到表情动作，也可能临时进入某个形态
  let reacted = false;
  for (let i = 0; i < 6 && !reacted; i += 1) {
    clickOnce();
    reacted = animClasses().length > 0 || formClasses().length > 0;
    if (!reacted) { /* 抽到的是形态且已还原，继续试 */ }
    else break;
  }
  assert.ok(reacted, '单击触发了表情动作或形态');
  console.log('[ok] 单击反应:', animClasses() || formClasses());

  // ---- 断言 4b：连点 3 次 → 生气（表情包式升级）----
  clickOnce();
  clickOnce();
  assert.ok(pet.classList.contains('anim-angry'), '连点 3 次触发生气');
  console.log('[ok] 连点升级为生气');

  // ---- 断言 4c：连点 5 次 → 晕乎乎 ----
  clickOnce();
  clickOnce();
  assert.ok(pet.classList.contains('anim-dizzy'), '连点 5 次触发晕乎乎');
  console.log('[ok] 连点升级为晕乎乎');
  clickOnce();
  setTimeout(() => {
    assert.ok(doc.querySelector('.fx-item'), '爱心粒子出现');
    console.log('[ok] 爱心粒子');

    // ---- 断言 5：点播大招 → state-ultimate + 粒子 ----
    apiEvents['pet:play'].forEach((h) => h({ action: 'ultimate' }));
    assert.ok(pet.classList.contains('state-ultimate'), '大招状态');
    console.log('[ok] 战斗形态（等粒子）');
    setTimeout(() => {
      assert.ok(doc.querySelectorAll('.fx-item').length >= 3, '大招粒子');
      console.log('[ok] 大招粒子');

      // ---- 断言 6：主进程 motion 广播 → 走路/飞行/拖拽状态切换 ----
      apiEvents['pet:motion'].forEach((h) =>
        h({ action: 'walk', facing: -1, dragged: false, airborne: false, walking: true, vx: -80, vy: 0, squash: 0, x: 30, y: 20 }),
      );
      assert.ok(pet.classList.contains('state-walk'), '走路状态');
      assert.ok(pet.classList.contains('facing-left'), '朝左镜像');
      apiEvents['pet:motion'].forEach((h) =>
        h({ action: 'drag', facing: 1, dragged: true, airborne: true, walking: false, vx: 0, vy: 0, squash: 0, x: 30, y: 20 }),
      );
      assert.ok(pet.classList.contains('state-drag'), '被抓状态');
      apiEvents['pet:motion'].forEach((h) =>
        h({ action: 'fly', facing: 1, dragged: false, airborne: true, walking: false, vx: 1200, vy: -800, squash: 0.4, x: 30, y: 20 }),
      );
      assert.ok(pet.classList.contains('state-fly'), '飞行状态');
      assert.ok(pet.classList.contains('fast'), '高速模糊');
      apiEvents['pet:motion'].forEach((h) =>
        h({ action: 'idle', facing: 1, dragged: false, airborne: false, walking: false, vx: 0, vy: 0, squash: 0.9, x: 30, y: 20 }),
      );
      assert.ok(pet.classList.contains('state-idle'), '落地回待机');
      console.log('[ok] 运动状态机');

      // ---- 断言 7：拖拽指针上报 ----
      head.dispatchEvent(new window.MouseEvent('pointerdown', { bubbles: true, button: 0, pointerId: 2 }));
      window.dispatchEvent(
        new window.MouseEvent('pointermove', { bubbles: true, button: 0, pointerId: 2, movementX: 10, movementY: 4, clientX: 50, clientY: 60 }),
      );
      window.dispatchEvent(new window.MouseEvent('pointerup', { bubbles: true, button: 0, pointerId: 2 }));
      assert.ok(apiCalls.includes('pointer:start'), '拖拽开始上报');
      assert.ok(apiCalls.includes('pointer:end'), '拖拽结束上报');
      console.log('[ok] 拖拽上报');

      // ---- 断言 8：右键菜单上报 ----
      head.dispatchEvent(new window.MouseEvent('contextmenu', { bubbles: true }));
      assert.ok(apiCalls.includes('contextMenu'), '右键菜单上报');
      console.log('[ok] 右键菜单');

      console.log('SMOKE-RENDERER OK');
      dom.window.close();
      process.exit(0);
    }, 800);
  }, 700);
}, 300);
