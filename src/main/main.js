'use strict';

/**
 * main.js —— 流萤桌宠的主进程。
 *
 * 职责：
 *  1. 开一个「透明 / 无边框 / 置顶 / 不进任务栏」的小窗，里面只有桌宠本体；
 *  2. 在 60Hz 的主循环里做运动学（拖拽跟手、甩抛抛物线、边缘反弹、地面摩擦、按朝向行走、自动漫游）；
 *  3. 托盘、右键菜单、开机自启、配置持久化。
 *
 * 与渲染进程的分工：
 *  - **窗口位置只由主进程改**（唯一权威），渲染进程只负责画面；
 *  - 渲染进程通过 `pet:pointer` 汇报指针阶段，主进程据此算窗口位置与甩出速度；
 *  - 主进程把 `pet:motion` 广播回渲染进程，驱动挤压拉伸、朝向、走路动画。
 */

const path = require('node:path');
const fs = require('node:fs');
const { app, BrowserWindow, ipcMain, Menu, Tray, nativeImage, screen, shell } = require('electron');

const configStore = require('./config');

// ---------------------------------------------------------------------------
// 单实例：再次启动直接唤醒已有的那一只
// ---------------------------------------------------------------------------
if (!app.requestSingleInstanceLock()) {
  // 说明已经有一只流萤在运行：第二只会安静退出（并留一行日志便于排查）
  try {
    fs.appendFileSync(
      path.join(app.getPath('userData'), 'firefly-pet.log'),
      `[${new Date().toISOString()}] single-instance lock denied (another instance is already running)\n`,
      'utf8',
    );
  } catch {
    /* ignore */
  }
  app.quit();
  process.exit(0);
}

const ARGS = new Set(process.argv.slice(1).filter((a) => a.startsWith('--')));
const IS_DEV = ARGS.has('--dev');
const VERBOSE = IS_DEV || ARGS.has('--verbose');

// 本机（向日葵虚拟显示器 + 125% 缩放）下，按显示器 DPI 感知的透明窗口会在每次
// setPosition/setSize 后被 DWM 重复放大（逐帧 +1px 的反馈循环）。
// 关闭 per-monitor DPI 感知 + 强制设备缩放为 1：窗口尺寸/坐标稳定在 96 DPI 空间，
// DPI 重缩放循环被彻底切断；物理尺寸的补偿在 winWidth/winHeight 里做（见 DPI_SCALE）。
app.commandLine.appendSwitch('high-dpi-support', 'false');
app.commandLine.appendSwitch('force-device-scale-factor', '1');

// 透明异形窗口在个别显卡驱动上会全黑，提供逃生舱：--safe
// 远程桌面（RDP）会话下 GPU 合成经常出问题，自动降级
const SESSION_REMOTE = /^RDP[-/]/i.test(process.env.SESSIONNAME || '');
if (ARGS.has('--safe') || SESSION_REMOTE) app.disableHardwareAcceleration();

let config = configStore.load();
log('module loaded', `argv=${JSON.stringify(process.argv.slice(1))} cwd=${process.cwd()} userData=${app.getPath('userData')}`);
if (ARGS.has('--reset')) {
  configStore.resetFile();
  config = configStore.load();
}
if (ARGS.has('--no-roam')) config.roam = false;
if (ARGS.has('--no-top')) config.topmost = false;
{
  const sizeArg = process.argv.find((a) => a.startsWith('--size='));
  if (sizeArg) config = configStore.normalize({ ...config, size: sizeArg.split('=')[1] });
}

// ---------------------------------------------------------------------------
// 窗口几何：宠物按 340x480 的坐标系绘制，窗口比它大一圈用来放气泡与阴影
// ---------------------------------------------------------------------------
const EXTRA_W = 1.34;
// 窗口比立绘高一些：上方留出气泡空间（立绘底部对齐）
const EXTRA_H = 2.15;

/**
 * 系统 DPI 缩放系数。
 * 强制 force-device-scale-factor=1 后窗口按 96 DPI 渲染，视觉会比预期小；
 * 把窗口几何乘以系统缩放系数即可恢复正确的物理大小（精灵是 SVG，无损缩放）。
 * 取不到时回落到 1（视觉偏小但功能正常）。
 */
let DPI_SCALE = 1;
function detectDpiScale() {
  try {
    const d = screen.getPrimaryDisplay();
    const s = Number(d && d.scaleFactor);
    if (Number.isFinite(s) && s >= 1.05 && s <= 4) DPI_SCALE = s;
  } catch {
    /* ignore */
  }
  if (DPI_SCALE <= 1.05) {
    // force-device-scale-factor=1 下 scaleFactor 恒为 1，改从注册表读系统 DPI（如 120→1.25）
    try {
      const { execSync } = require('node:child_process');
      const out = execSync('reg query "HKCU\\Control Panel\\Desktop\\WindowMetrics" /v AppliedDPI', {
        encoding: 'utf8',
        windowsHide: true,
        timeout: 3000,
      });
      const m = /0x([0-9a-fA-F]+)/.exec(out);
      if (m) {
        const dpi = parseInt(m[1], 16);
        if (dpi >= 96 && dpi <= 480) DPI_SCALE = dpi / 96;
      }
    } catch {
      /* ignore：取不到就保持 1（视觉偏小但功能正常） */
    }
  }
  if (!Number.isFinite(DPI_SCALE) || DPI_SCALE < 1) DPI_SCALE = 1;
}

const winWidth = () => Math.round(config.size * EXTRA_W * DPI_SCALE);
const winHeight = () => Math.round(config.size * EXTRA_H * DPI_SCALE);

let win = null;
let tray = null;
let quitting = false;

// ---------------------------------------------------------------------------
// 运动状态（px / px·s⁻¹）
// ---------------------------------------------------------------------------
const motion = {
  x: 0,
  y: 0,
  vx: 0,
  vy: 0,
  dragged: false,
  airborne: false,
  facing: 1, // 1 = 朝右，-1 = 朝左
  action: 'idle',
  squash: 0,
};

const pointer = {
  dragging: false,
  offsetX: 0,
  offsetY: 0,
  samples: [], // { t, x, y } 用于估算甩出速度
};

const roamState = {
  walking: false,
  targetX: 0,
  targetY: 0,
  nextThink: 0, // 秒
};

let lastActivity = Date.now();
let lastTick = Date.now();
let savePosTimer = null;
let loopTimer = null;
let tickCount = 0;

function log(...parts) {
  const line = `[${new Date().toISOString()}] ${parts.join(' ')}\n`;
  try {
    const dir = app.getPath('userData');
    fs.mkdirSync(dir, { recursive: true });
    fs.appendFileSync(path.join(dir, 'firefly-pet.log'), line, 'utf8');
  } catch {
    /* ignore */
  }
  if (VERBOSE) console.error('[firefly-pet]', ...parts);
}

// ---------------------------------------------------------------------------
// 屏幕 / 工作区
// ---------------------------------------------------------------------------
function workAreas() {
  return screen.getAllDisplays().map((d) => d.workArea);
}

/** 取包含（或最接近）某个点的显示器工作区，作为「这块屏的地面」 */
function workAreaAt(x, y) {
  const areas = workAreas();
  const cx = x + winWidth() / 2;
  const cy = y + winHeight() / 2;
  for (const a of areas) {
    if (cx >= a.x && cx <= a.x + a.width && cy >= a.y && cy <= a.y + a.height) return a;
  }
  let best = areas[0];
  let bestDist = Infinity;
  for (const a of areas) {
    const dx = Math.max(a.x - cx, 0, cx - (a.x + a.width));
    const dy = Math.max(a.y - cy, 0, cy - (a.y + a.height));
    const dist = dx * dx + dy * dy;
    if (dist < bestDist) {
      bestDist = dist;
      best = a;
    }
  }
  return best;
}

/** 站在地面时的窗口 y：宠物底边贴住工作区底边 */
function groundY(area) {
  return area.y + area.height - winHeight();
}

const EDGE_SLACK = 36; // 允许露到屏幕外的宽容度，方便把它拽去别的屏

function applyPosition() {
  if (!win || win.isDestroyed()) return;
  win.setPosition(Math.round(motion.x), Math.round(motion.y));
}

function broadcast() {
  if (!win || win.isDestroyed()) return;
  win.webContents.send('pet:motion', {
    action: motion.action,
    facing: motion.facing,
    dragged: motion.dragged,
    airborne: motion.airborne,
    walking: roamState.walking,
    vx: Math.round(motion.vx),
    vy: Math.round(motion.vy),
    squash: Number(motion.squash.toFixed(3)),
    x: Math.round(motion.x),
    y: Math.round(motion.y),
  });
}

function setAction(action) {
  if (motion.action === action) return;
  motion.action = action;
  broadcast();
}

function touch() {
  lastActivity = Date.now();
}

function sendSquash(value) {
  const next = Number.isFinite(value) ? Math.max(0, value) : 0;
  if (Math.abs(next - motion.squash) < 0.02) return;
  motion.squash = next;
  broadcast();
}

// ---------------------------------------------------------------------------
// 主循环
// ---------------------------------------------------------------------------
function tick() {
  const now = Date.now();
  const dt = Math.min(0.05, Math.max(0.001, (now - lastTick) / 1000));
  lastTick = now;
  tickCount += 1;

  if (!win || win.isDestroyed()) return;

  // 位置/速度以 ~8Hz 同步给渲染端（驱动前倾、快速模糊、眼睛与挤压等视觉）
  const heartbeat = tickCount % 8 === 0;

  // —— 1. 拖拽：直接跟手 ——
  if (pointer.dragging) {
    const p = screen.getCursorScreenPoint();
    motion.x = p.x - pointer.offsetX;
    motion.y = p.y - pointer.offsetY;
    motion.airborne = true;
    motion.facing = p.x >= motion.x + winWidth() / 2 ? 1 : -1;
    const samples = pointer.samples;
    samples.push({ t: now, x: p.x, y: p.y });
    while (samples.length > 12) samples.shift();
    applyPosition();
    if (heartbeat) broadcast();
    return;
  }

  // —— 2. 空中：抛物线 + 边缘反弹 ——
  if (motion.airborne) {
    motion.vy += config.gravity * dt;
    motion.vx *= 1 - 0.15 * dt;
    motion.x += motion.vx * dt;
    motion.y += motion.vy * dt;

    const area = workAreaAt(motion.x, motion.y);
    const minX = area.x - EDGE_SLACK;
    const maxX = area.x + area.width - winWidth() + EDGE_SLACK;
    if (motion.x < minX) {
      motion.x = minX;
      motion.vx = Math.abs(motion.vx) * config.bounce;
      sendSquash(0.5);
    } else if (motion.x > maxX) {
      motion.x = maxX;
      motion.vx = -Math.abs(motion.vx) * config.bounce;
      sendSquash(0.5);
    }
    if (Math.abs(motion.vx) > 30) motion.facing = motion.vx > 0 ? 1 : -1;

    const minY = area.y - EDGE_SLACK;
    const floor = groundY(area);
    if (motion.y >= floor) {
      motion.y = floor;
      const impact = Math.abs(motion.vy);
      if (impact > 460) {
        motion.vy = -impact * config.bounce;
        sendSquash(Math.min(1.2, impact / 2200));
      } else {
        motion.vy = 0;
        motion.vx *= 0.4;
        motion.airborne = false;
        sendSquash(Math.min(1, impact / 1500 + 0.25));
        setAction('idle');
        scheduleSavePosition();
      }
    } else if (motion.y < minY) {
      motion.y = minY;
      motion.vy = Math.abs(motion.vy) * config.bounce;
      sendSquash(0.5);
    }
    applyPosition();
    if (heartbeat) broadcast();
    return;
  }

  // —— 3. 行走 ——
  if (roamState.walking) {
    const dx = roamState.targetX - motion.x;
    const dy = roamState.targetY - motion.y;
    const dist = Math.hypot(dx, dy);
    if (dist < 3) {
      roamState.walking = false;
      motion.vx = 0;
      motion.vy = 0;
      setAction('idle');
      roamState.nextThink = now / 1000 + 2 + Math.random() * 4;
      scheduleSavePosition();
      return;
    }
    const step = Math.min(dist, config.walkSpeed * dt);
    motion.vx = (dx / dist) * config.walkSpeed;
    motion.vy = (dy / dist) * config.walkSpeed;
    motion.x += (dx / dist) * step;
    motion.y += (dy / dist) * step;
    motion.facing = dx >= 0 ? 1 : -1;
    applyPosition();
    if (heartbeat) broadcast();
  }
}

function startLoop() {
  if (loopTimer) return;
  loopTimer = setInterval(tick, 16);
}

function stopLoop() {
  if (!loopTimer) return;
  clearInterval(loopTimer);
  loopTimer = null;
}

// ---------------------------------------------------------------------------
// 自动漫游
// ---------------------------------------------------------------------------
function pickRoamTarget() {
  const areas = workAreas();
  const area = Math.random() < 0.25 && areas.length > 1
    ? areas[Math.floor(Math.random() * areas.length)]
    : workAreaAt(motion.x, motion.y);
  const minX = area.x + 8;
  const maxX = Math.max(minX + 1, area.x + area.width - winWidth() - 8);
  return { x: minX + Math.random() * (maxX - minX), y: groundY(area) };
}

function roamThink() {
  if (!win || win.isDestroyed()) return;
  if (pointer.dragging || motion.airborne) return;
  if (!config.roam) return;

  const idleFor = (Date.now() - lastActivity) / 1000;
  if (config.sleepAfterSec > 0 && idleFor > config.sleepAfterSec) {
    if (motion.action !== 'sleep' && !roamState.walking) setAction('sleep');
    return;
  }
  if (motion.action === 'sleep') setAction('idle');
  if (roamState.walking) return;

  const now = Date.now() / 1000;
  if (now < roamState.nextThink) return;

  if (Math.random() < 0.42) {
    const target = pickRoamTarget();
    roamState.targetX = target.x;
    roamState.targetY = target.y;
    roamState.walking = true;
    setAction('walk');
  } else {
    roamState.nextThink = now + 4 + Math.random() * 8;
    // 让渲染端自己挑个小动作（打哈欠 / 伸懒腰 / 东张西望…）
    if (motion.action === 'idle' && Math.random() < 0.55) {
      win.webContents.send('pet:idle-flavor', { seed: Math.random() });
    }
  }
}

// ---------------------------------------------------------------------------
// 拖拽
// ---------------------------------------------------------------------------
function beginDrag(target) {
  if (!win || win.isDestroyed()) return;
  const p = screen.getCursorScreenPoint();
  pointer.dragging = true;
  pointer.offsetX = p.x - motion.x;
  pointer.offsetY = p.y - motion.y;
  pointer.samples = [{ t: Date.now(), x: p.x, y: p.y }];
  motion.dragged = true;
  motion.airborne = false;
  roamState.walking = false;
  setAction(target === 'head' ? 'drag-head' : 'drag');
  touch();
  broadcast();
}

function endDrag() {
  if (!pointer.dragging) return;
  pointer.dragging = false;
  motion.dragged = false;

  // 用最近 ~120ms 的采样估算甩出速度
  const samples = pointer.samples;
  pointer.samples = [];
  let vx = 0;
  let vy = 0;
  if (samples.length >= 2) {
    const last = samples[samples.length - 1];
    const cutoff = last.t - 120;
    let first = samples[0];
    for (const s of samples) {
      if (s.t >= cutoff) {
        first = s;
        break;
      }
    }
    const dt = Math.max(0.016, (last.t - first.t) / 1000);
    vx = ((last.x - first.x) / dt) * 1.15;
    vy = ((last.y - first.y) / dt) * 1.15;
  }
  const cap = 2800;
  vx = Math.max(-cap, Math.min(cap, vx));
  vy = Math.max(-cap, Math.min(cap, vy));

  const area = workAreaAt(motion.x, motion.y);
  const floor = groundY(area);
  const nearFloor = motion.y >= floor - 28;
  const speed = Math.hypot(vx, vy);

  if (speed < 90 || (nearFloor && speed < 170)) {
    // 轻轻放下：原地站好
    motion.vx = 0;
    motion.vy = 0;
    motion.airborne = false;
    if (nearFloor) motion.y = floor;
    setAction('idle');
    sendSquash(0.42);
    roamState.nextThink = Date.now() / 1000 + 3; // 落地后喘口气再走动
  } else {
    motion.airborne = true;
    motion.vx = vx;
    motion.vy = vy;
    if (Math.abs(vx) > 40) motion.facing = vx > 0 ? 1 : -1;
    setAction('fly');
  }
  applyPosition();
  broadcast();
  scheduleSavePosition();
  touch();
}

function scheduleSavePosition() {
  if (savePosTimer) clearTimeout(savePosTimer);
  savePosTimer = setTimeout(() => {
    savePosTimer = null;
    config.position = { x: Math.round(motion.x), y: Math.round(motion.y) };
    configStore.save(config);
  }, 800);
}

// ---------------------------------------------------------------------------
// 动作点播
// ---------------------------------------------------------------------------
function playAction(action) {
  if (!win || win.isDestroyed()) return;
  touch();
  switch (action) {
    case 'walk-random': {
      const target = pickRoamTarget();
      roamState.targetX = target.x;
      roamState.targetY = target.y;
      roamState.walking = true;
      motion.airborne = false;
      setAction('walk');
      return;
    }
    case 'throw': {
      motion.airborne = true;
      roamState.walking = false;
      motion.vx = (Math.random() < 0.5 ? -1 : 1) * (520 + Math.random() * 680);
      motion.vy = -940 - Math.random() * 320;
      motion.facing = motion.vx > 0 ? 1 : -1;
      setAction('fly');
      return;
    }
    case 'home': {
      const area = screen.getPrimaryDisplay().workArea;
      roamState.walking = false;
      motion.airborne = false;
      motion.vx = 0;
      motion.vy = 0;
      motion.x = area.x + area.width - winWidth() - config.marginX;
      motion.y = groundY(area) - config.marginY;
      applyPosition();
      setAction('idle');
      scheduleSavePosition();
      return;
    }
    case 'sleep':
      setAction('sleep');
      return;
    case 'wake':
      setAction('idle');
      return;
    default:
      // 其余都是「原地演一段」的动作，交给渲染端
      win.webContents.send('pet:play', { action: String(action) });
  }
}

// ---------------------------------------------------------------------------
// 窗口
// ---------------------------------------------------------------------------
function initialPosition() {
  const areas = workAreas();
  const area = screen.getPrimaryDisplay().workArea;
  const fallback = {
    x: area.x + area.width - winWidth() - config.marginX,
    y: groundY(area) - config.marginY,
  };
  if (!config.position || !Number.isFinite(config.position.x) || !Number.isFinite(config.position.y)) {
    return fallback;
  }
  // 保存的位置可能落在已被拔掉的显示器上：验证是否与任何一块屏有交集
  const x = config.position.x;
  const y = config.position.y;
  const intersects = areas.some(
    (a) => x + winWidth() > a.x && x < a.x + a.width && y + winHeight() > a.y && y < a.y + a.height,
  );
  if (!intersects) return fallback;
  // 保证底边不越出工作区（其他方向宽容，用户可以再拽回来）
  const nearest = workAreaAt(x, y);
  return { x, y: Math.min(y, groundY(nearest)) };
}

function createWindow() {
  const start = initialPosition();
  motion.x = start.x;
  motion.y = start.y;

  win = new BrowserWindow({
    width: winWidth(),
    height: winHeight(),
    x: Math.round(start.x),
    y: Math.round(start.y),
    transparent: true,
    frame: false,
    resizable: false,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    hasShadow: false,
    alwaysOnTop: config.topmost,
    show: false,
    backgroundColor: '#00000000',
    title: '流萤桌宠',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
      spellcheck: false,
    },
  });

  win.setAlwaysOnTop(config.topmost, 'screen-saver');
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  win.setIgnoreMouseEvents(config.clickThrough, { forward: true });

  // 锁死窗口尺寸：部分显示环境（虚拟显示器/远程桌面/非标 DPI）会让透明无边框窗
  // 逐帧被 DWM 重复放大（见 sizeWatchdog 日志），min=max 能阻止系统侧缩放
  win.setMinimumSize(winWidth(), winHeight());
  win.setMaximumSize(winWidth(), winHeight());
  win.on('resize', () => {
    const [w, h] = win.getSize();
    log('resize event ->', `${w}x${h}`);
  });

  win.loadFile(path.join(__dirname, '..', 'renderer', 'index.html'));

  win.once('ready-to-show', () => {
    if (!win || win.isDestroyed()) return;
    win.show();
    win.setAlwaysOnTop(config.topmost, 'screen-saver');
    log('ready-to-show fired, window visible');
    // 某些显示环境（虚拟显示器/DPI 切换）会在 show 后把窗口尺寸放大多倍，稍后校准一次
    setTimeout(() => applySize(), 200);
    setTimeout(() => applySize(), 1200);
    // --form=<id>：启动即进入指定形态（用于演示 / 截图）
    {
      const formArg = process.argv.find((a) => a.startsWith('--form='));
      if (formArg) {
        const id = formArg.split('=')[1];
        setTimeout(() => {
          if (win && !win.isDestroyed()) win.webContents.send('pet:form', { id });
        }, 1500);
      }
    }
    // 诊断：抓一帧渲染进程实际绘制的内容，用来区分「没画出来」和「画了但没合成到屏幕」
    if (VERBOSE) {      setTimeout(async () => {
        try {
          if (!win || win.isDestroyed()) return;
          const image = await win.webContents.capturePage();
          const png = image.toPNG();
          fs.writeFileSync(path.join(app.getPath('userData'), 'render-debug.png'), png);
          log('captured render-debug.png', `bytes=${png.length} size=${image.getSize().width}x${image.getSize().height}`);
        } catch (error) {
          log('capturePage failed', String(error && error.message));
        }
      }, 3000);
    }
  });

  win.on('closed', () => {
    win = null;
    // Alt+F4 之类把窗口关了也别让宠物消失：只要没退出就再开一只
    if (!quitting) {
      try {
        createWindow();
      } catch (error) {
        log('recreate window failed', String(error && error.message));
      }
    }
  });

  win.webContents.on('render-process-gone', (_e, details) => {
    log('render-process-gone', String(details && details.reason), String(details && details.exitCode));
    if (win && !win.isDestroyed()) win.reload();
  });

  win.webContents.on('did-fail-load', (_e, code, desc) => {
    log('did-fail-load', String(code), String(desc));
  });

  win.webContents.on('console-message', (_e, level, message) => {
    log('renderer console:', String(message));
  });

  win.webContents.on('before-input-event', (_event, input) => {
    if (input.type !== 'keyDown' || input.key !== 'Escape') return;
    if (pointer.dragging) endDrag();
    if (win && !win.isDestroyed()) win.webContents.send('pet:escape');
  });

  if (IS_DEV) win.webContents.openDevTools({ mode: 'detach' });
  log('window created', JSON.stringify({ x: start.x, y: start.y, w: winWidth(), h: winHeight() }));
}

function applySize() {
  if (!win || win.isDestroyed()) return;
  const before = win.getSize();
  win.setSize(winWidth(), winHeight());
  const after = win.getSize();
  if (before[0] !== after[0] || before[1] !== after[1]) {
    log('size corrected', `${before[0]}x${before[1]} -> ${after[0]}x${after[1]}`);
  }
  const area = workAreaAt(motion.x, motion.y);
  const floor = groundY(area);
  if (motion.y > floor) motion.y = floor;
  applyPosition();
  broadcast();
}

/** 尺寸看门狗：显示环境把窗口撑大时自动拉回（透明窗在 DPI/虚拟显示器切换时的已知坑） */
function sizeWatchdog() {
  if (!win || win.isDestroyed()) return;
  if (pointer.dragging || motion.airborne) return;
  const [w, h] = win.getSize();
  const ew = winWidth();
  const eh = winHeight();
  if (Math.abs(w - ew) > 24 || Math.abs(h - eh) > 24) {
    log('watchdog: window ballooned', `${w}x${h} -> ${ew}x${eh}`);
    applySize();
  }
}

function resizeBy(delta) {
  config.size = Math.round(Math.min(460, Math.max(120, config.size + delta)));
  configStore.save(config);
  applySize();
  refreshTrayMenu();
}

function applyClickThrough(on) {
  config.clickThrough = Boolean(on);
  configStore.save(config);
  if (win && !win.isDestroyed()) {
    win.setIgnoreMouseEvents(config.clickThrough, { forward: true });
    win.webContents.send('pet:click-through', { on: config.clickThrough });
  }
  refreshTrayMenu();
}

// ---------------------------------------------------------------------------
// 托盘与菜单
// ---------------------------------------------------------------------------
const IDLE_FLAVORS = [
  { id: 'greet', label: '打个招呼' },
  { id: 'shy', label: '害羞一下' },
  { id: 'stretch', label: '伸个懒腰' },
  { id: 'look', label: '东张西望' },
  { id: 'hum', label: '哼歌' },
  { id: 'nap', label: '打个瞌睡' },
  { id: 'butterfly', label: '召唤小蝴蝶' },
];

/** 表情包一套（短反应动作） */
const EXPRESSIONS = [
  { id: 'happy', label: '开心' },
  { id: 'angry', label: '生气' },
  { id: 'surprised', label: '惊讶' },
  { id: 'confused', label: '疑惑' },
  { id: 'sad', label: '难过' },
  { id: 'proud', label: '得意' },
  { id: 'thumbs', label: '点赞' },
  { id: 'call', label: '加油打气' },
  { id: 'nod', label: '点头' },
  { id: 'shake', label: '摇头' },
  { id: 'dizzy', label: '晕乎乎' },
  { id: 'shy', label: '害羞' },
];

/** 17 形态（对应鼠标指针皮肤的 17 种角色状态） */
const FORMS = [
  { id: 'normal', label: '1 正常选择' },
  { id: 'help', label: '2 帮助' },
  { id: 'bg', label: '3 后台运行' },
  { id: 'busy', label: '4 忙碌' },
  { id: 'precise', label: '5 精确定位' },
  { id: 'text', label: '6 文本选择' },
  { id: 'hand', label: '7 手写' },
  { id: 'no', label: '8 不可用' },
  { id: 'vsize', label: '9 垂直调整' },
  { id: 'hsize', label: '10 水平调整' },
  { id: 'diag1', label: '11 对角调整 ↘' },
  { id: 'diag2', label: '12 对角调整 ↙' },
  { id: 'move', label: '13 移动' },
  { id: 'alt', label: '14 候选' },
  { id: 'link', label: '15 链接选择' },
  { id: 'locate', label: '16 位置选择' },
  { id: 'person', label: '17 人员选择' },
];

function buildMenuTemplate() {
  return [
    { label: '流萤 · Firefly', enabled: false },
    { type: 'separator' },
    {
      label: '互动',
      submenu: [
        { label: '摸摸头', click: () => playAction('headpat') },
        { label: '投喂能量块', click: () => playAction('snack') },
        { label: '让她说句话', click: () => playAction('talk') },
        { type: 'separator' },
        ...IDLE_FLAVORS.map((f) => ({ label: f.label, click: () => playAction(f.id) })),
        { label: '萤火全开（大招）', click: () => playAction('ultimate') },
      ],
    },
    {
      label: '表情',
      submenu: EXPRESSIONS.map((e) => ({ label: e.label, click: () => playAction(e.id) })),
    },
    {
      label: '形态（17 种）',
      submenu: [
        { label: '▶ 形态巡演（依次演示）', click: () => playAction('form-tour') },
        { type: 'separator' },
        ...FORMS.map((f) => ({ label: f.label, click: () => playAction(`form:${f.id}`) })),
      ],
    },
    {
      label: '动作',
      submenu: [
        { label: '坐下 / 站起来', click: () => playAction('toggle-sit') },
        { label: '把她扔出去', click: () => playAction('throw') },
        { label: '睡觉 / 唤醒', click: () => playAction(motion.action === 'sleep' ? 'wake' : 'sleep') },
        { label: '回到右下角', click: () => playAction('home') },
      ],
    },
    { type: 'separator' },
    {
      label: '自动漫游',
      type: 'checkbox',
      checked: config.roam,
      click: (item) => {
        config.roam = item.checked;
        configStore.save(config);
        if (!config.roam) {
          roamState.walking = false;
          setAction(motion.action === 'walk' ? 'idle' : motion.action);
        }
      },
    },
    {
      label: '始终置顶',
      type: 'checkbox',
      checked: config.topmost,
      click: (item) => {
        config.topmost = item.checked;
        configStore.save(config);
        if (win && !win.isDestroyed()) win.setAlwaysOnTop(config.topmost, 'screen-saver');
      },
    },
    {
      label: '鼠标穿透（点不到她）',
      type: 'checkbox',
      checked: config.clickThrough,
      click: (item) => applyClickThrough(item.checked),
    },
    { type: 'separator' },
    {
      label: '大小',
      submenu: [
        ...[120, 160, 220, 300, 380].map((s) => ({
          label: `${s}px`,
          type: 'radio',
          checked: Math.abs(config.size - s) < 10,
          click: () => {
            config.size = s;
            configStore.save(config);
            applySize();
            refreshTrayMenu();
          },
        })),
        { type: 'separator' },
        { label: '放大一点 (+20)', click: () => resizeBy(20) },
        { label: '缩小一点 (-20)', click: () => resizeBy(-20) },
      ],
    },
    {
      label: '开机自启',
      type: 'checkbox',
      checked: config.autoLaunch,
      click: (item) => setAutoLaunch(item.checked),
    },
    { type: 'separator' },
    { label: '打开配置文件夹', click: () => shell.openPath(app.getPath('userData')) },
    { label: '打开日志（需 --verbose）', click: () => shell.openPath(path.join(app.getPath('userData'), 'firefly-pet.log')) },
    { type: 'separator' },
    { label: '退出流萤', click: () => quit() },
  ];
}

function refreshTrayMenu() {
  if (!tray || tray.isDestroyed()) return;
  tray.setContextMenu(Menu.buildFromTemplate(buildMenuTemplate()));
}

function trayIconImage() {
  // 程序化画一个 16x16 的「小萤火」托盘图标（BGRA 原始位图，不依赖任何外部图片/编码器）
  const S = 16;
  const buf = Buffer.alloc(S * S * 4);
  const layer = (d, inner, outer, rr, gg, bb) => {
    // 软边圆：d 从 inner 到 outer 淡出
    if (d > outer) return;
    const a = d < inner ? 1 : Math.max(0, 1 - (d - inner) / (outer - inner));
    return a;
  };
  for (let y = 0; y < S; y += 1) {
    for (let x = 0; x < S; x += 1) {
      const dx = x - 7.5;
      const dy = y - 7.5;
      const d = Math.sqrt(dx * dx + dy * dy);
      let r = 0;
      let g = 0;
      let b = 0;
      let a = 0;
      const a0 = layer(d, 7.2, 7.8, 13, 39, 49);
      const a1 = layer(d, 4.6, 5.2, 127, 240, 230);
      const a2 = layer(d, 2.7, 3.3, 255, 177, 84);
      const a3 = layer(d, 0, 1.4, 255, 253, 245);
      if (a0 !== undefined) {
        r = 13; g = 39; b = 49; a = a0 * 255;
      }
      if (a1 !== undefined) {
        r = 127; g = 240; b = 230; a = a1 * 255;
      }
      if (a2 !== undefined) {
        r = 255; g = 177; b = 84; a = a2 * 255;
      }
      if (a3 !== undefined) {
        r = 255; g = 253; b = 245; a = a3 * 255;
      }
      const off = 4 * (y * S + x);
      buf[off] = Math.round(b);
      buf[off + 1] = Math.round(g);
      buf[off + 2] = Math.round(r);
      buf[off + 3] = Math.round(a);
    }
  }
  const image = nativeImage.createFromBitmap(buf, { width: S, height: S });
  return image.isEmpty() ? nativeImage.createEmpty() : image;
}

function createTray() {
  try {
    tray = new Tray(trayIconImage());
    tray.setToolTip('流萤桌宠 · 右键查看菜单');
    refreshTrayMenu();
    tray.on('click', () => {
      if (!win || win.isDestroyed()) return;
      win.show();
      playAction('talk');
    });
    log('tray created');
  } catch (error) {
    // 无托盘的环境（如某些远程会话）不影响桌宠本体
    log('tray creation failed (ignored):', String(error && error.message));
  }
}

function setAutoLaunch(on) {
  config.autoLaunch = Boolean(on);
  configStore.save(config);
  try {
    if (process.platform === 'win32') {
      app.setLoginItemSettings({ openAtLogin: config.autoLaunch, path: process.execPath, args: [app.getAppPath()] });
    } else {
      app.setLoginItemSettings({ openAtLogin: config.autoLaunch });
    }
  } catch (error) {
    log('setLoginItemSettings failed', String(error && error.message));
  }
  refreshTrayMenu();
}

function quit() {
  quitting = true;
  configStore.flush();
  stopLoop();
  if (win && !win.isDestroyed()) win.destroy();
  app.quit();
}

// ---------------------------------------------------------------------------
// IPC
// ---------------------------------------------------------------------------
function wireIpc() {
  ipcMain.on('pet:ready', () => {
    log('renderer ready (pet:ready received)');
    broadcast();
    if (!config.position) scheduleSavePosition();
  });

  ipcMain.on('pet:pointer', (_e, payload) => {
    const phase = payload && payload.phase;
    if (phase === 'start') beginDrag(payload && payload.target);
    else if (phase === 'move') {
      if (pointer.dragging) {
        const now = Date.now();
        const p = screen.getCursorScreenPoint();
        pointer.samples.push({ t: now, x: p.x, y: p.y });
        while (pointer.samples.length > 12) pointer.samples.shift();
      }
    } else if (phase === 'end') endDrag();
  });

  ipcMain.on('pet:activity', () => touch());

  // 物理冲量：点击互动时给她一个力，走同一套重力/反弹/地面模型
  ipcMain.on('pet:impulse', (_e, payload) => {
    if (!win || win.isDestroyed()) return;
    if (pointer.dragging) return;
    const p = payload || {};
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, Number.isFinite(Number(v)) ? Number(v) : 0));
    const vx = clamp(p.vx, -1400, 1400);
    const vy = clamp(p.vy, -1600, 700);
    roamState.walking = false;
    motion.airborne = true;
    motion.vx += vx;
    motion.vy += vy;
    if (Math.abs(vx) > 24) motion.facing = vx > 0 ? 1 : -1;
    const sq = clamp(p.squash, 0, 1.2);
    if (sq > 0) sendSquash(sq);
    // 只有明显被弹起来才切成飞行表现，小磕碰保持原动作
    if (vy < -260 || Math.abs(vx) > 220) setAction('fly');
    touch();
    broadcast();
  });

  ipcMain.on('pet:action', (_e, payload) => {
    const action = payload && payload.action;
    if (typeof action === 'string') playAction(action);
  });

  ipcMain.on('pet:speak-done', () => touch());

  ipcMain.handle('pet:get-config', () => ({ ...config, version: app.getVersion() }));

  ipcMain.handle('pet:set-config', (_e, patch) => {
    config = configStore.normalize({ ...config, ...(patch || {}) });
    configStore.save(config);
    if (win && !win.isDestroyed()) {
      win.setAlwaysOnTop(config.topmost, 'screen-saver');
      win.setIgnoreMouseEvents(config.clickThrough, { forward: true });
      applySize();
    }
    refreshTrayMenu();
    return { ...config };
  });

  ipcMain.handle('pet:context-menu', () => {
    if (!win || win.isDestroyed()) return;
    Menu.buildFromTemplate(buildMenuTemplate()).popup({ window: win });
  });

  ipcMain.on('pet:quit', () => quit());
  ipcMain.on('pet:set-ignore-mouse', (_e, on) => applyClickThrough(on));
}

// ---------------------------------------------------------------------------
// 生命周期
// ---------------------------------------------------------------------------
app.on('second-instance', () => {
  if (win && !win.isDestroyed()) {
    win.show();
    playAction('talk');
  }
});

app.on('window-all-closed', () => {
  // 桌宠常驻：窗口没了也留着托盘（只有显式退出才结束进程）
  if (quitting) app.quit();
});

app.on('before-quit', () => {
  quitting = true;
  configStore.flush();
});

app.on('will-quit', () => {
  if (tray && !tray.isDestroyed()) tray.destroy();
});

app.whenReady().then(() => {
  detectDpiScale();
  log('app ready', `platform=${process.platform} node=${process.versions.node} electron=${process.versions.electron} size=${config.size} dpiScale=${DPI_SCALE} workArea=${JSON.stringify(screen.getPrimaryDisplay().workArea)} session=${process.env.SESSIONNAME || '?'} gpuAccel=${!ARGS.has('--safe') && !SESSION_REMOTE}`);
  createWindow();
  createTray();
  wireIpc();
  startLoop();
  setInterval(roamThink, 1000);
  setInterval(sizeWatchdog, 4000);
  screen.on('display-metrics-changed', () => {
    log('display-metrics-changed');
    setTimeout(() => applySize(), 120);
  });
  screen.on('display-added', () => applySize());
  screen.on('display-removed', () => applySize());
});

app.on('activate', () => {
  if (!win) createWindow();
  else win.show();
});

process.on('uncaughtException', (error) => log('uncaughtException', String(error && error.stack)));
process.on('unhandledRejection', (error) => log('unhandledRejection', String(error && error.stack)));
process.on('exit', (code) => log('process exit, code =', String(code)));
