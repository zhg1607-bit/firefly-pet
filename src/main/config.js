'use strict';

/**
 * config.js —— 用户配置的读写。
 *
 * 配置文件位置：%APPDATA%/firefly-pet/config.json（Windows）
 * 结构见 DEFAULTS；任何缺失/非法字段都会回落到默认值，绝不因为配置坏掉而起不来。
 */

const fs = require('node:fs');
const path = require('node:path');

let app = null;
try {
  app = require('electron').app;
} catch {
  app = null;
}

const DEFAULTS = Object.freeze({
  /** 宠物宽度（px），窗口尺寸由它推导 */
  size: 220,
  /** 记住的上次位置（null = 首次启动，落到右下角） */
  position: null,
  /** 右下角时的边距 */
  marginX: 40,
  marginY: 90,
  /** 自动漫游：默认关（用户以拖动为主） */
  roam: false,
  /** 是否始终置顶 */
  topmost: true,
  /** 鼠标穿透（开启后点击会穿过宠物落到桌面上） */
  clickThrough: false,
  /** 头顶气泡说话 */
  speech: true,
  /** 音效（暂未内置音源，保留开关） */
  sound: false,
  /** 开机自启 */
  autoLaunch: false,
  /** 闲置多久后自己睡觉（秒，0 = 不睡） */
  sleepAfterSec: 180,
  /** 漫游速度（px/s） */
  walkSpeed: 110,
  /** 物理：重力 与 弹性 */
  gravity: 2200,
  bounce: 0.48,
  friction: 0.86,
  /** 累计好感度（摸头会涨，只用于台词） */
  affection: 0,
});

function userDataDir() {
  if (app && typeof app.getPath === 'function') {
    try {
      return app.getPath('userData');
    } catch {
      /* fall through */
    }
  }
  return process.cwd();
}

function configPath() {
  return path.join(userDataDir(), 'config.json');
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function num(value, fallback, min, max) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  if (typeof min === 'number' && n < min) return min;
  if (typeof max === 'number' && n > max) return max;
  return n;
}

function bool(value, fallback) {
  return typeof value === 'boolean' ? value : fallback;
}

/** 归一化任意输入为一份合法配置 */
function normalize(raw) {
  const input = raw && typeof raw === 'object' ? raw : {};
  let position = null;
  if (input.position && Number.isFinite(Number(input.position.x)) && Number.isFinite(Number(input.position.y))) {
    position = { x: Math.round(Number(input.position.x)), y: Math.round(Number(input.position.y)) };
  }
  return {
    size: Math.round(num(input.size, DEFAULTS.size, 120, 460)),
    position,
    marginX: Math.round(num(input.marginX, DEFAULTS.marginX, 0, 4000)),
    marginY: Math.round(num(input.marginY, DEFAULTS.marginY, 0, 4000)),
    roam: bool(input.roam, DEFAULTS.roam),
    topmost: bool(input.topmost, DEFAULTS.topmost),
    clickThrough: bool(input.clickThrough, DEFAULTS.clickThrough),
    speech: bool(input.speech, DEFAULTS.speech),
    sound: bool(input.sound, DEFAULTS.sound),
    autoLaunch: bool(input.autoLaunch, DEFAULTS.autoLaunch),
    sleepAfterSec: Math.round(num(input.sleepAfterSec, DEFAULTS.sleepAfterSec, 0, 7200)),
    walkSpeed: num(input.walkSpeed, DEFAULTS.walkSpeed, 20, 600),
    gravity: num(input.gravity, DEFAULTS.gravity, 200, 12000),
    bounce: num(input.bounce, DEFAULTS.bounce, 0, 0.95),
    friction: num(input.friction, DEFAULTS.friction, 0.5, 0.99),
    affection: Math.round(num(input.affection, DEFAULTS.affection, 0, 100000)),
  };
}

function load() {
  try {
    const text = fs.readFileSync(configPath(), 'utf8');
    return normalize(JSON.parse(text));
  } catch {
    return normalize(null);
  }
}

let saveTimer = null;
let pending = null;

function writeNow(config) {
  try {
    fs.mkdirSync(path.dirname(configPath()), { recursive: true });
    fs.writeFileSync(configPath(), JSON.stringify(config, null, 2), 'utf8');
    return true;
  } catch (error) {
    console.error('[firefly-pet] 配置写入失败：', error && error.message);
    return false;
  }
}

/** 延迟合并写入，避免拖拽时疯狂落盘 */
function save(config) {
  pending = config;
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    saveTimer = null;
    const next = pending;
    pending = null;
    if (next) writeNow(next);
  }, 400);
}

function flush() {
  if (saveTimer) {
    clearTimeout(saveTimer);
    saveTimer = null;
  }
  if (pending) {
    const next = pending;
    pending = null;
    writeNow(next);
  }
}

function resetFile() {
  try {
    fs.rmSync(configPath(), { force: true });
  } catch {
    /* ignore */
  }
}

module.exports = { DEFAULTS, load, save, flush, resetFile, normalize, configPath, clamp };
