'use strict';

/**
 * preload.js —— 渲染进程唯一的对外通道。
 * 只暴露必要的能力，且全部是「单向命令 + 少量查询」，渲染端拿不到 Node。
 */

const { contextBridge, ipcRenderer } = require('electron');

const listeners = new Map();

function on(channel, handler) {
  const wrapped = (_event, payload) => handler(payload);
  ipcRenderer.on(channel, wrapped);
  listeners.set(handler, { channel, wrapped });
  return () => {
    ipcRenderer.removeListener(channel, wrapped);
    listeners.delete(handler);
  };
}

contextBridge.exposeInMainWorld('desktopPet', {
  /** 渲染端自报家门：主进程收到后开始广播运动状态 */
  ready: () => ipcRenderer.send('pet:ready'),

  /** 指针阶段：start / move / end，附带抓到的部位（head / body / wing…） */
  pointer: (payload) => ipcRenderer.send('pet:pointer', payload || {}),

  /** 有任何互动都刷新一次「闲置计时」，避免刚被摸完就去睡觉 */
  activity: () => ipcRenderer.send('pet:activity'),

  /** 请求主进程执行一个动作（headpat / snack / talk / ultimate / walk-random / throw / home / sleep …） */
  action: (action) => ipcRenderer.send('pet:action', { action: String(action) }),

  /** 物理冲量：点击时给她一个力（vx/vy 像素每秒，squash 挤压量 0~1） */
  impulse: (payload) => ipcRenderer.send('pet:impulse', payload || {}),

  /** 说完了（用于同步闲置计时） */
  speakDone: () => ipcRenderer.send('pet:speak-done'),

  getConfig: () => ipcRenderer.invoke('pet:get-config'),
  setConfig: (patch) => ipcRenderer.invoke('pet:set-config', patch || {}),

  /** 让主进程在光标处弹出原生右键菜单 */
  contextMenu: () => ipcRenderer.invoke('pet:context-menu'),

  setIgnoreMouse: (on) => ipcRenderer.send('pet:set-ignore-mouse', Boolean(on)),

  quit: () => ipcRenderer.send('pet:quit'),

  /** 监听主进程广播（motion / play / escape / click-through / idle-flavor） */
  on,
});
