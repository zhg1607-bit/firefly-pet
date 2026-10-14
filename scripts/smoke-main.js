'use strict';

/**
 * scripts/smoke-main.js —— 用「伪 electron 模块」冒烟测试 main.js 的纯逻辑：
 *  - 配置加载与归一化
 *  - 窗口创建参数
 *  - 拖拽开始/结束 → 甩出 → 抛物线落地 → 停在地面线的完整运动学链路
 * 运行：node scripts/smoke-main.js
 * 注意：这不是 UI 测试，Electron 二进制无法在沙箱里跑；这里验证的是逻辑与 IPC 通路。
 */

const assert = require('node:assert');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const Module = require('node:module');

const marker = (m) => console.error(`[smoke] ${m}`);
marker('start');

// 先于 main.js 注册，任何未捕获异常都要浮出水面
process.on('uncaughtException', (error) => {
  console.error('SMOKE uncaughtException:', error && error.stack ? error.stack : error);
  process.exit(2);
});

// ---------------------------------------------------------------------------
// 伪 electron
// ---------------------------------------------------------------------------
const state = {
  positions: [],
  sends: [],
  windows: [],
  display: { x: 0, y: 0, width: 1920, height: 1040 },
  displays: [
    { x: 0, y: 0, width: 1920, height: 1040 },
    { x: 1920, y: 0, width: 1280, height: 1024 },
  ],
  cursor: { x: 1600, y: 900 },
  ipcHandlers: {},
  whenReadyCb: null,
  ready: false,
};

class FakeWindow {
  constructor(options) {
    this.options = options;
    this.currentSize = [options.width, options.height];
    this.webContents = {
      send: (channel, payload) => state.sends.push({ channel, payload }),
      on: () => {},
      openDevTools: () => {},
    };
    this.handlers = {};
    this.destroyed = false;
    state.windows.push(this);
  }
  setPosition(x, y) {
    state.positions.push({ x, y });
  }
  getSize() {
    return this.currentSize.slice();
  }
  setSize(w, h) {
    this.currentSize = [w, h];
  }
  setAlwaysOnTop() {}
  setVisibleOnAllWorkspaces() {}
  setIgnoreMouseEvents() {}
  setMinimumSize() {}
  setMaximumSize() {}
  loadFile(file) {
    this.loaded = file;
  }
  show() {}
  focus() {}
  reload() {}
  isDestroyed() {
    return this.destroyed;
  }
  destroy() {
    this.destroyed = true;
  }
  once(event, cb) {
    this.handlers[event] = cb;
  }
  on(event, cb) {
    this.handlers[event] = cb;
  }
  openDevTools() {}
}

const fakeElectron = {
  app: {
    on() {},
    requestSingleInstanceLock: () => true,
    disableHardwareAcceleration() {},
    getPath: () => path.join(os.tmpdir(), 'firefly-pet-smoke'),
    getVersion: () => '0.0.0-smoke',
    getAppPath: () => process.cwd(),
    setLoginItemSettings() {},
    quit() {},
    commandLine: { appendSwitch() {} },
    whenReady: () => ({
      then(cb) {
        state.whenReadyCb = cb;
        return this;
      },
    }),
  },
  BrowserWindow: FakeWindow,
  ipcMain: {
    on(channel, fn) {
      state.ipcHandlers[channel] = fn;
    },
    handle(channel, fn) {
      state.ipcHandlers[`handle:${channel}`] = fn;
    },
  },
  Menu: {
    buildFromTemplate: (template) => ({ popup() {}, template }),
  },
  Tray: class {
    constructor(image) {
      this.image = image;
    }
    setToolTip() {}
    setContextMenu() {}
    on() {}
    isDestroyed() {
      return false;
    }
    destroy() {}
  },
  nativeImage: {
    createFromBitmap: (buf, opt) => ({ isEmpty: () => buf.length === 0 }),
  },
  screen: {
    getAllDisplays: () => state.displays.map((d) => ({ workArea: d })),
    getPrimaryDisplay: () => ({ workArea: state.display }),
    getCursorScreenPoint: () => ({ x: state.cursor.x, y: state.cursor.y }),
    on() {},
  },
  shell: { openPath: () => Promise.resolve('') },
};

const originalLoad = Module._load;
Module._load = function (request, ...rest) {
  if (request === 'electron') return fakeElectron;
  return originalLoad.call(this, request, ...rest);
};

// 清掉运行目录
const userData = path.join(os.tmpdir(), 'firefly-pet-smoke');
fs.rmSync(userData, { recursive: true, force: true });

require(path.join(process.cwd(), 'src', 'main', 'main.js'));
marker('main.js loaded');

assert.ok(state.whenReadyCb, 'whenReady 回调已注册');
state.whenReadyCb();
marker('whenReady invoked');

const win = state.windows[0];
assert.ok(win, '创建了窗口');
assert.strictEqual(win.options.transparent, true, '透明窗');
assert.strictEqual(win.options.frame, false, '无边框');
assert.strictEqual(win.options.skipTaskbar, true, '不进任务栏');
assert.ok(win.loaded.endsWith(path.join('src', 'renderer', 'index.html')), '加载渲染页');
console.log('window options ok:', JSON.stringify({ w: win.options.width, h: win.options.height, x: win.options.x, y: win.options.y }));

// 触发 ready → 广播
state.ipcHandlers['pet:ready']({}, {});
assert.ok(state.sends.some((s) => s.channel === 'pet:motion'), 'ready 后有 motion 广播');

// ---- 拖拽：start → 指针移动 → end（快速甩动）----
state.cursor = { x: 1600, y: 900 };
state.ipcHandlers['pet:pointer']({}, { phase: 'start', target: 'body' });
// 模拟快速甩动：主循环 tick 里会采样光标，直接改光标并喂 move
for (let i = 0; i < 10; i += 1) {
  state.cursor = { x: 1600 + i * 40, y: 900 - i * 30 };
  state.ipcHandlers['pet:pointer']({}, { phase: 'move' });
}
state.ipcHandlers['pet:pointer']({}, { phase: 'end' });

// 等物理循环跑一段：抛飞后应落回某块屏的地面线
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  await wait(2500);
  const last = state.positions[state.positions.length - 1];
  assert.ok(last, '窗口位置被持续更新');
  const windowH = win.options.height;
  // 落点应停在其中一块屏的地面线上（工作区底 - 窗高）
  const onFloor = state.displays.some((d) => Math.abs(last.y - (d.y + d.height - windowH)) < 3);
  console.log('final position:', JSON.stringify(last), 'floor check:', onFloor);
  assert.ok(onFloor, '抛掷后应落回地面线');

  // ---- 动作点播路径 ----
  state.ipcHandlers['pet:action']({}, { action: 'ultimate' });
  await wait(50);
  assert.ok(state.sends.some((s) => s.channel === 'pet:play' && s.payload.action === 'ultimate'), '动作点播转发');

  // ---- 物理冲量：点击互动给她一个力，应进入空中并被重力拉回地面 ----
  const posBefore = state.positions.length;
  state.ipcHandlers['pet:impulse']({}, { vx: 320, vy: -520, squash: 0.5 });
  await wait(120);
  const airborneSeen = state.sends.some((s) => s.channel === 'pet:motion' && s.payload.airborne === true);
  assert.ok(airborneSeen, '冲量后进入空中');
  assert.ok(state.positions.length > posBefore, '冲量后窗口位置持续更新');
  await wait(2500);
  const final = state.positions[state.positions.length - 1];
  const windowH2 = win.options.height;
  const backOnFloor = state.displays.some((d) => Math.abs(final.y - (d.y + d.height - windowH2)) < 3);
  console.log('impulse landing:', JSON.stringify(final), 'floor:', backOnFloor);
  assert.ok(backOnFloor, '冲量后落回地面线');

  // ---- 配置读取/写入 ----
  const getConfig = state.ipcHandlers['handle:pet:get-config'];
  const cfg = getConfig({}, {});
  assert.ok(typeof cfg.size === 'number' && cfg.size >= 120, '配置读取正常');
  console.log('config ok:', JSON.stringify({ size: cfg.size, roam: cfg.roam, topmost: cfg.topmost }));

  // ---- 落地后位置保存（800ms 防抖）----
  await wait(1000);
  const saved = JSON.parse(fs.readFileSync(path.join(userData, 'config.json'), 'utf8'));
  assert.ok(saved.position && Number.isFinite(saved.position.x) && Number.isFinite(saved.position.y), '位置已持久化');
  console.log('persisted position:', JSON.stringify(saved.position));

  console.log('SMOKE-MAIN OK');
  process.exit(0);
})().catch((error) => {
  console.error('SMOKE-MAIN FAIL:', error);
  process.exit(1);
});
