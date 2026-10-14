'use strict';

/**
 * fx.js —— 轻量粒子：星光、爱心、小蝴蝶、Zzz、汗滴、金币…
 *
 * 只用 DOM 元素 + CSS 动画（不用 canvas），保证透明窗口里开销极低：
 * 每个粒子播完自己删掉，同时在场的数量有上限。
 */

(function () {
  const layer = () => document.getElementById('fx');

  const PRESETS = {
    star: { glyph: '✦', cls: '', size: 15, dy: -80, dx: 0, rot: 40 },
    spark: { glyph: '✨', cls: '', size: 16, dy: -95, dx: 0, rot: 20 },
    heart: { glyph: '♥', cls: 'heart', size: 15, dy: -85, dx: 0, rot: -14 },
    butterfly: { glyph: '🦋', cls: 'butterfly', size: 17, dy: -105, dx: 0, rot: 24 },
    zzz: { glyph: 'Z', cls: '', size: 18, dy: -100, dx: 26, rot: 18 },
    sweat: { glyph: '💧', cls: '', size: 15, dy: -70, dx: 0, rot: 0 },
    coin: { glyph: '◆', cls: '', size: 14, dy: -90, dx: 0, rot: 120 },
    note: { glyph: '♪', cls: '', size: 17, dy: -95, dx: -18, rot: -18 },
    snack: { glyph: '🍬', cls: '', size: 17, dy: -70, dx: 0, rot: 0 },
    fire: { glyph: '✹', cls: '', size: 20, dy: -120, dx: 0, rot: 160 },
    // 表情包一类的反应符号
    anger: { glyph: '💢', cls: '', size: 19, dy: -78, dx: 10, rot: 12 },
    exclaim: { glyph: '❗', cls: '', size: 20, dy: -92, dx: 0, rot: -8 },
    question: { glyph: '❓', cls: '', size: 19, dy: -88, dx: -8, rot: 10 },
    tear: { glyph: '💧', cls: '', size: 16, dy: -66, dx: -12, rot: 0 },
    thumb: { glyph: '👍', cls: '', size: 18, dy: -84, dx: 6, rot: -10 },
    bolt: { glyph: '⚡', cls: '', size: 18, dy: -95, dx: 0, rot: 14 },
    music: { glyph: '🎵', cls: '', size: 17, dy: -98, dx: -14, rot: -16 },
    clap: { glyph: '👏', cls: '', size: 17, dy: -80, dx: 8, rot: 8 },
    dizzy: { glyph: '💫', cls: '', size: 18, dy: -92, dx: 0, rot: 30 },
    shine: { glyph: '🌟', cls: '', size: 18, dy: -100, dx: 0, rot: 22 },
  };

  let live = 0;
  const MAX_LIVE = 26;

  /**
   * 在窗口内某个相对位置（0~1）弹一个粒子
   * @param {string} kind 预设名
   * @param {{x?:number,y?:number,dx?:number,dy?:number,size?:number}} [opts]
   */
  function spawn(kind, opts) {
    const host = layer();
    if (!host) return;
    if (live >= MAX_LIVE) return;
    const preset = PRESETS[kind] || PRESETS.star;
    const o = opts || {};
    const node = document.createElement('span');
    node.className = `fx-item ${preset.cls}`.trim();
    node.textContent = preset.glyph;
    const x = (typeof o.x === 'number' ? o.x : 0.5) * 100;
    const y = (typeof o.y === 'number' ? o.y : 0.62) * 100;
    node.style.left = `${x}%`;
    node.style.top = `${y}%`;
    node.style.fontSize = `${(o.size || preset.size)}px`;
    node.style.setProperty('--dx', `${o.dx ?? preset.dx}px`);
    node.style.setProperty('--dy', `${o.dy ?? preset.dy}px`);
    node.style.setProperty('--rot', `${preset.rot}deg`);
    host.appendChild(node);
    live += 1;
    const cleanup = () => {
      live -= 1;
      node.remove();
    };
    node.addEventListener('animationend', cleanup, { once: true });
    // 兜底：动画被系统禁用（prefers-reduced-motion）时也要清掉
    setTimeout(cleanup, 2600);
  }

  /** 一次性撒一把粒子 */
  function burst(kind, count, opts) {
    const n = Math.max(1, count || 3);
    for (let i = 0; i < n; i += 1) {
      setTimeout(() => {
        spawn(kind, {
          ...(opts || {}),
          x: (opts && opts.x ? opts.x : 0.5) + (Math.random() - 0.5) * 0.22,
          y: (opts && opts.y ? opts.y : 0.62) + (Math.random() - 0.5) * 0.1,
          dx: (Math.random() - 0.5) * 70,
          dy: -(60 + Math.random() * 70),
          size: 12 + Math.random() * 7,
        });
      }, i * 110);
    }
  }

  /**
   * 技能光圈：向外扩散的圆环（施法 / 大招 / 落地冲击用）
   * @param {number} count 圈数
   * @param {{x?:number,y?:number}} [opts] 相对位置（0~1）
   */
  function ring(count, opts) {
    const host = layer();
    if (!host) return;
    const n = Math.max(1, count || 1);
    const o = opts || {};
    for (let i = 0; i < n; i += 1) {
      setTimeout(() => {
        if (live >= MAX_LIVE) return;
        const node = document.createElement('span');
        node.className = 'fx-ring';
        node.style.left = `${(typeof o.x === 'number' ? o.x : 0.5) * 100}%`;
        node.style.top = `${(typeof o.y === 'number' ? o.y : 0.62) * 100}%`;
        host.appendChild(node);
        live += 1;
        const cleanup = () => {
          live -= 1;
          node.remove();
        };
        node.addEventListener('animationend', cleanup, { once: true });
        setTimeout(cleanup, 1700);
      }, i * 170);
    }
  }

  window.FireflyFx = { spawn, burst, ring, PRESETS };
})();
