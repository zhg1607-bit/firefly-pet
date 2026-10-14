'use strict';

/**
 * renderer.js —— 桌宠的「表现层」。
 *
 * 分工：
 *  - 主进程负责窗口位置与运动学（拖拽、抛飞、落地、行走）；
 *  - 本文件负责：渲染精灵、按状态切动画、指针交互上报、气泡、粒子、挤压拉伸的逐帧演算。
 *
 * 状态机只认两种来源：主进程广播的 action（走/飞/被抓/睡），以及本地点播的短动作（摸头/大招…）。
 */

(function () {
  const SPRITE_W = 340;
  const SPRITE_H = 480;

  const pet = document.getElementById('pet');
  const spriteHost = document.getElementById('sprite');
  const petImg = document.getElementById('pet-img');
  const poseStand = document.getElementById('pose-stand');
  const poseSit = document.getElementById('pose-sit');
  const sitBody = document.getElementById('sit-body');
  const legL = document.getElementById('sit-leg-l');
  const legR = document.getElementById('sit-leg-r');
  const bubble = document.getElementById('bubble');
  const bubbleText = document.getElementById('bubble-text');
  const root = document.documentElement;
  const api = window.desktopPet || null;

  // 本体是参考图立绘：站姿（stand.png）+ 坐姿三层（sit-body / sit-leg-l / sit-leg-r）
  if (petImg) {
    petImg.addEventListener('error', () => console.warn('[diag] 立绘加载失败：' + petImg.getAttribute('src')));
  }
  if (sitBody) sitBody.addEventListener('load', () => relayout());
  if (petImg) petImg.addEventListener('load', () => relayout());

  // 腿的髋部枢轴（坐姿图片坐标，画布 792x1070）；按坐姿图片的实际缩放映射成 CSS 像素原点
  const LEG_PIVOTS = { l: { x: 282, y: 848 }, r: { x: 554, y: 848 } };
  function updateLegOrigins() {
    if (!legL || !legR || !sitBody || !sitBody.naturalWidth) return;
    const k = Math.min(SPRITE_W / sitBody.naturalWidth, SPRITE_H / sitBody.naturalHeight);
    const offY = SPRITE_H - sitBody.naturalHeight * k;
    const setOrigin = (el, p) => {
      el.style.transformOrigin = `${(p.x * k).toFixed(1)}px ${(offY + p.y * k).toFixed(1)}px`;
    };
    setOrigin(legL, LEG_PIVOTS.l);
    setOrigin(legR, LEG_PIVOTS.r);
  }

  /** 切换姿势：stand（站姿）/ sit（坐下晃腿） */
  function setPose(mode) {
    const next = mode === 'sit' ? 'sit' : 'stand';
    if (state.pose === next) return;
    state.pose = next;
    if (poseStand) poseStand.classList.toggle('hidden', next !== 'stand');
    if (poseSit) poseSit.classList.toggle('hidden', next !== 'sit');
    updateLegOrigins();
  }

  /** 任何交互都算「她在被关注」：站起来 + 重置闲置计时 + 停止形态巡演 */
  function noteInteraction() {
    state.idleSince = Date.now();
    if (state.pose === 'sit') setPose('stand');
    stopFormTour(true);
  }

  // ------------------------------------------------------------------
  // 17 形态：对应鼠标指针皮肤的 17 种角色状态（可菜单点播，也按情境自动切换）
  // ------------------------------------------------------------------
  const FX = () => window.FireflyFx;
  const FORMS = {
    normal: { n: 1, label: '正常选择', fx: null },
    help: { n: 2, label: '帮助', fx: () => FX().spawn('note', { x: 0.68, y: 0.22, dx: 8, dy: -70, size: 20 }) },
    bg: { n: 3, label: '后台运行', fx: () => FX().burst('star', 2, { x: 0.5, y: 0.72 }) },
    busy: { n: 4, label: '忙碌', fx: () => FX().burst('spark', 3, { x: 0.5, y: 0.5 }) },
    precise: { n: 5, label: '精确定位', fx: () => FX().ring(1, { y: 0.5 }) },
    text: { n: 6, label: '文本选择', fx: () => FX().burst('note', 2, { x: 0.62, y: 0.4 }) },
    hand: { n: 7, label: '手写', fx: () => FX().spawn('star', { x: 0.64, y: 0.5, size: 14 }) },
    no: { n: 8, label: '不可用', fx: () => FX().spawn('sweat', { x: 0.68, y: 0.24, size: 15 }) },
    vsize: { n: 9, label: '垂直调整', fx: null },
    hsize: { n: 10, label: '水平调整', fx: null },
    diag1: { n: 11, label: '对角调整 ↘', fx: null },
    diag2: { n: 12, label: '对角调整 ↙', fx: null },
    move: { n: 13, label: '移动', fx: null },
    alt: { n: 14, label: '候选', fx: () => FX().burst('star', 3, { x: 0.5, y: 0.6 }) },
    link: { n: 15, label: '链接选择', fx: () => FX().burst('butterfly', 2, { x: 0.42, y: 0.42 }) },
    locate: { n: 16, label: '位置选择', fx: () => FX().ring(1, { y: 0.56 }) },
    person: { n: 17, label: '人员选择', fx: () => FX().burst('heart', 3, { x: 0.5, y: 0.36 }) },
  };
  const FORM_IDS = Object.keys(FORMS);
  let formRevertTimer = null;

  function setForm(id, opts) {
    const o = opts || {};
    const next = FORMS[id] ? id : 'normal';
    if (state.form === next && !o.force) return;
    const prev = state.form;
    state.form = next;
    FORM_IDS.forEach((f) => pet.classList.remove(`form-${f}`));
    if (next !== 'normal') pet.classList.add(`form-${next}`);
    const spec = FORMS[next];
    if (spec && spec.fx && !o.silent) spec.fx();
    if (formRevertTimer) {
      clearTimeout(formRevertTimer);
      formRevertTimer = null;
    }
    if (o.revertMs) {
      formRevertTimer = setTimeout(() => {
        formRevertTimer = null;
        setForm(prev === state.form ? 'normal' : prev, { silent: true });
      }, o.revertMs);
    }
  }

  // ------------------------------------------------------------------
  // 状态
  // ------------------------------------------------------------------
  const state = {
    action: 'idle',
    facing: 1,
    dragged: false,
    airborne: false,
    walking: false,
    vx: 0,
    vy: 0,
    squashImpulse: 0,
    x: window.screenX,
    y: window.screenY,
    clickThrough: false,
    busyUntil: 0,
    pose: 'stand',
    form: 'normal',
    idleSince: Date.now(),
    lastPointer: { x: window.innerWidth / 2, y: window.innerHeight / 2 },
  };

  const squash = { x: 1, y: 1 };
  const pointerState = { down: false, moved: false, started: false, target: 'body' };

  let config = { size: 220, roam: true, speech: true };
  let bubbleTimer = null;
  let useIntervalDriver = false;

  // ------------------------------------------------------------------
  // 台词
  // ------------------------------------------------------------------
  const LINES = {
    greet: ['…你好呀。', '我是流萤，请多指教～', '咦，你在看我吗？', '今天也要一起加油哦。'],
    headpat: [
      '唔…别摸啦，头发会乱的。',
      '嘿嘿…好舒服。',
      '再摸下去，我可要撒娇了哦？',
      '这是…被摸头的感觉吗？',
      '（悄悄把脑袋往你手上蹭了蹭）',
    ],
    body: ['嗯？', '有事吗？', '我在。', '小心别把我摔了…'],
    wing: ['法杖别乱碰啦，会放电的。', '唔…那是我很重要的东西。', '看，宝珠在发光呢。'],
    hair: ['头发…会被弄乱的。', '呼，好痒。'],
    drag: ['哇啊——！', '放我下来啦！', '我、我会飞！', '抓稳一点呀…'],
    fall: ['呀——！', '要掉下去了！'],
    land: ['呼…落地成功。', '唔，有点晕…', '下次轻一点嘛。'],
    sleep: ['Zzz…', '晚安…', '（睡得很香）'],
    feed: ['呜，是能量块！', '好吃…还想再来一块。', '谢谢招待～'],
    idle: ['……（发呆中）', '在想别的事情。', '萤火虫也会迷路吗？', '今天的风很舒服。'],
    ultimate: ['萤火，全开——', '这一击，为开拓者！', '绽放吧，流萤！'],
    shy: ['唔…别、别一直盯着看啦。', '才、才没有害羞呢！', '（把脸别到一边）'],
    happy: ['嘿嘿～', '今天心情很好！', '（开心地晃了晃）'],
    angry: ['哼！不理你了。', '生气了哦…', '（鼓起腮帮子）'],
    surprised: ['诶？！', '哇啊——', '吓、吓我一跳！'],
    confused: ['唔……？', '什么意思呀？', '（歪头）'],
    sad: ['呜……', '有点难过…', '（垂下了头）'],
    proud: ['怎么样，厉害吧？', '哼哼～', '（挺起了胸）'],
    nod: ['嗯嗯！', '知道了！', '好呀好呀。'],
    shake: ['才不要呢。', '不行不行～', '（摇了摇头）'],
    thumbs: ['交给我吧！', '没问题！', '（比了个赞）'],
    call: ['流萤，加油——！', '冲呀！', '（给你打气）'],
    dizzy: ['晕乎乎的…', '转得有点多了…'],
    greet: ['你好呀～', '今天也要一起加油哦。', '（朝你挥了挥手）'],
  };

  function line(kind) {
    const pool = LINES[kind] || LINES.idle;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  // ------------------------------------------------------------------
  // 气泡
  // ------------------------------------------------------------------
  function say(text, ms) {
    if (!text) return;
    bubbleText.textContent = text;
    bubble.classList.add('show');
    const dur = Math.max(1200, ms || 3200);
    // 说话时嘴动（若当前已有具体表情，则不覆盖）
    if (bubbleTimer) clearTimeout(bubbleTimer);
    bubbleTimer = setTimeout(() => {
      bubble.classList.remove('show');
      bubbleTimer = null;
      if (api) api.speakDone();
    }, dur);
  }

  function hideBubble() {
    if (bubbleTimer) {
      clearTimeout(bubbleTimer);
      bubbleTimer = null;
    }
    bubble.classList.remove('show');
  }

  // ------------------------------------------------------------------
  // 动画状态机
  // ------------------------------------------------------------------
  function setAction(action, opts) {
    const o = opts || {};
    if (state.action === action && !o.force) return;
    state.action = action;
    if (!o.keepBusy) state.busyUntil = 0;
    [...pet.classList].forEach((cls) => {
      if (cls.startsWith('state-') || cls.startsWith('anim-')) pet.classList.remove(cls);
    });
    pet.classList.add(`state-${action}`);
    applyFacing();
    if (o.effect) o.effect();
  }

  /** 播一段一次性动作，结束回到主进程给的稳态 */
  function playAnim(name, opts) {
    const o = opts || {};
    setAction(o.state || 'idle', { keepBusy: true });
    pet.classList.add(`anim-${name}`);
    state.busyUntil = performance.now() + (o.duration || 1200);
    if (o.effect) o.effect();
    if (o.say) say(o.say, o.sayMs);
    if (api) api.activity();
    if (o.after) setTimeout(o.after, o.duration || 1200);
  }

  /** 主进程广播的稳态动作（走/飞/被抓/睡） */
  function setBaseAction(action) {
    const map = {
      walk: 'walk',
      fly: 'fly',
      drag: 'drag',
      'drag-head': 'drag',
      sleep: 'sleep',
      idle: 'idle',
    };
    setAction(map[action] || 'idle', { force: false });
  }

  function applyFacing() {
    // 被抓起来时朝向跟着鼠标，其余按运动方向
    const facing = state.facing >= 0 ? 1 : -1;
    pet.classList.toggle('facing-left', facing < 0);
  }

  // ------------------------------------------------------------------
  // 尺度：把 340x480 的精灵塞进任意窗口
  // ------------------------------------------------------------------
  function relayout() {
    const width = window.innerWidth;
    const height = window.innerHeight;
    const scale = Math.min(width / SPRITE_W, height / SPRITE_H);
    root.style.setProperty('--s', String(scale));
    root.style.setProperty('--pet-w', `${SPRITE_W}px`);
    root.style.setProperty('--pet-h', `${SPRITE_H}px`);
    root.style.setProperty('--shadow-w', `${150 * scale}px`);
    root.style.setProperty('--shadow-h', `${24 * scale}px`);
    root.style.setProperty('--glow-w', `${230 * scale}px`);
    root.style.setProperty('--glow-h', `${60 * scale}px`);
    root.style.setProperty('--bubble-max', `${Math.max(120, 240 * scale)}px`);
    root.style.setProperty('--bubble-font', `${Math.round(Math.max(10, 14 * scale))}px`);
    // 立绘底部对齐、等比缩放后头顶约在盒顶下方 29 个单位，气泡放在头顶再往上一点
    root.style.setProperty('--bubble-bottom', `${(SPRITE_H - 24) * scale}px`);
  }

  // ------------------------------------------------------------------
  // 主循环：把运动状态翻译成视觉参数
  // ------------------------------------------------------------------
  let prevMotion = { x: state.x, y: state.y, vx: 0, vy: 0, t: performance.now() };

  function frame(now) {
    const dt = Math.min(0.05, Math.max(0.001, (now - prevMotion.t) / 1000));
    const vx = (state.x - prevMotion.x) / dt;
    const vy = (state.y - prevMotion.y) / dt;
    prevMotion = { x: state.x, y: state.y, vx, vy, t: now };
    // 兜底：主进程推送丢了也能从窗口自身位置取到（window.move 事件同样会更新）
    if (!state.dragged && !state.airborne && !state.walking) {
      state.x = window.screenX;
      state.y = window.screenY;
    }

    const width = window.innerWidth;
    const height = window.innerHeight;
    const scale = Number(root.style.getPropertyValue('--s')) || 1;

    // 1) 落地冲量 → 挤压（弹性衰减）
    if (state.squashImpulse > 0.001) {
      const k = state.squashImpulse;
      squash.x = 1 + 0.36 * k;
      squash.y = 1 - 0.3 * k;
      state.squashImpulse *= Math.exp(-dt * 5.5);
    } else {
      state.squashImpulse = 0;
      squash.x += (1 - squash.x) * Math.min(1, dt * 12);
      squash.y += (1 - squash.y) * Math.min(1, dt * 12);
    }

    // 2) 滞空感：被提着 / 飞起来时略微拉长
    if (state.dragged) {
      squash.x = 0.95;
      squash.y = 1.07;
    } else if (state.airborne) {
      const speed = Math.min(1, Math.hypot(vx, vy) / 1400);
      squash.x = 1 - 0.07 * speed;
      squash.y = 1 + 0.1 * speed;
    }

    // 3) 走路时轻微前倾；空中时朝运动方向倾（像被抛出去的身体）
    const lean = state.walking ? Math.sign(vx || 1) * 2.6 : 0;
    let tilt = state.dragged ? Math.sin(now / 240) * 4 : 0;
    if (!state.dragged && state.airborne) {
      tilt = Math.max(-15, Math.min(15, vx / 20));
    }

    root.style.setProperty('--squash-x', squash.x.toFixed(4));
    root.style.setProperty('--squash-y', squash.y.toFixed(4));
    root.style.setProperty('--lean', `${lean}deg`);
    root.style.setProperty('--tilt', `${tilt}deg`);

    // 4) 影子：离地越高越淡越大
    const airborne = state.dragged || state.airborne;
    const shadowScale = airborne ? 0.82 : 1;
    const shadowOpacity = airborne ? 0.18 : 0.42;
    root.style.setProperty('--shadow', shadowOpacity.toFixed(3));
    root.style.setProperty('--shadow-w', `${150 * scale * shadowScale}px`);

    // 5) 光环：飞行/大招更亮，大招偏金色
    const auraOn = state.action === 'fly' || state.action === 'ultimate';
    const auraPulse = 0.45 + 0.18 * Math.sin(now / 620);
    root.style.setProperty('--aura', (auraOn ? 0.95 : auraPulse).toFixed(3));
    root.style.setProperty('--aura-hue', state.action === 'ultimate' ? '-28deg' : '0deg');
    root.style.setProperty('--core-op', state.action === 'ultimate' ? '1' : '0.92');

    // 6) 朝鼠标轻微倾身（单张立绘没有独立眼珠，用整体微倾表达「注意力」）
    if (petImg) {
      const r = petImg.getBoundingClientRect();
      if (r.width > 4 && r.height > 4) {
        const nx = (state.lastPointer.x - (r.left + r.width / 2)) / (r.width * 0.85);
        const ny = (state.lastPointer.y - (r.top + r.height * 0.45)) / (r.height * 0.85);
        const cx = Math.max(-1, Math.min(1, nx));
        const cy = Math.max(-1, Math.min(1, ny));
        const facingFlip = pet.classList.contains('facing-left') ? -1 : 1;
        root.style.setProperty('--lean-x', (cx * facingFlip * 5 * scale).toFixed(2) + 'px');
        root.style.setProperty('--lean-r', (cx * facingFlip * 2.2).toFixed(2) + 'deg');
        root.style.setProperty('--eye-y', (cy * 1.5 * scale).toFixed(2) + 'px');
      }
    }

    // 7) 一次性动作结束后回落到稳态
    if (state.busyUntil && now > state.busyUntil) {
      state.busyUntil = 0;
      setBaseAction(currentBaseAction());
    }

    // rAF 不可用时不再自我调度（由 setInterval 兜底驱动）
    if (!useIntervalDriver) requestAnimationFrame(frame);
  }

  function currentBaseAction() {
    if (state.dragged) return 'drag';
    if (state.airborne) return 'fly';
    if (state.walking) return 'walk';
    return 'idle';
  }

  // ------------------------------------------------------------------
  // 指针交互
  // ------------------------------------------------------------------
  // 点击判定：立绘是单张图，按图内相对位置划分区域
  //   顶部 → 头发/发饰；右上 → 法杖与蝴蝶；左上/右上中段 → 长发；中间 → 身体；下部 → 裙摆与腿
  function targetOf(event) {
    if (!petImg) return 'body';
    const r = petImg.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return 'body';
    const rx = (event.clientX - r.left) / r.width;
    const ry = (event.clientY - r.top) / r.height;
    if (ry < 0.16) return 'hair';
    if (ry < 0.45) return rx > 0.66 ? 'wing' : 'head';
    if (ry < 0.78) return rx < 0.14 || rx > 0.86 ? 'hair' : 'body';
    return 'body';
  }

  pet.addEventListener('pointerenter', () => {
    if (api) api.activity();
    // 形态 15：链接选择（凑近看她）
    setForm('link', { silent: true, revertMs: 1800 });
  });
  pet.addEventListener('pointerleave', () => {
    /* 保留：将来用于悬停表情 */
  });

  // 指针事件挂在 window 上：拖拽期间窗口会跟着鼠标走，
  // 挂在宠物元素上的 move/up 有可能因窗口移动而丢失，window 级最稳。
  window.addEventListener('pointermove', (event) => {
    state.lastPointer = { x: event.clientX, y: event.clientY };
    if (!pointerState.down) return;
    const dx = Math.abs(event.movementX || 0);
    const dy = Math.abs(event.movementY || 0);
    if (!pointerState.started && (dx > 2 || dy > 2)) {
      pointerState.started = true;
      pointerState.moved = true;
      if (api) api.pointer({ phase: 'start', target: pointerState.target });
      setAction('drag', { force: true });
      setForm('move', { silent: true }); // 形态 13：移动
    }
    if (pointerState.started && api) api.pointer({ phase: 'move' });
  });

  function endPointer(event) {
    if (!pointerState.down) return;
    pointerState.down = false;
    pet.classList.remove('grabbing');
    if (pointerState.started) {
      if (api) api.pointer({ phase: 'end' });
      pointerState.started = false;
      pointerState.moved = false;
      if (api) api.activity();
      return;
    }
    // 没有拖动 = 一次点击
    reactToClick(pointerState.target);
    pointerState.moved = false;
  }

  pet.addEventListener('pointerdown', (event) => {
    if (state.clickThrough) return;
    if (event.button !== 0) return;
    noteInteraction();
    state.lastPointer = { x: event.clientX, y: event.clientY };
    pointerState.down = true;
    pointerState.moved = false;
    pointerState.started = false;
    pointerState.target = targetOf(event);
    pet.classList.add('grabbing');
    if (api) api.activity();
  });

  window.addEventListener('pointerup', endPointer);
  window.addEventListener('pointercancel', endPointer);

  pet.addEventListener('dblclick', () => {
    if (state.clickThrough) return;
    playAnim('spin', { duration: 1000, effect: () => window.FireflyFx.burst('star', 4) });
    if (api) api.activity();
  });

  pet.addEventListener('contextmenu', (event) => {
    event.preventDefault();
    if (api) api.contextMenu();
  });

  // 点击互动：从「表情包 / 17 形态」里挑动作来回应，连点会生气
  // 条目可以是动作 id，也可以是 'form:xxx'（临时进入某形态若干秒）
  const CLICK_POOL = [
    'happy',
    'surprised',
    'confused',
    'nod',
    'thumbs',
    'proud',
    'call',
    'shake',
    'dizzy',
    'form:help',
    'form:busy',
    'form:alt',
    'form:no',
    'form:person',
    'form:link',
    'form:locate',
    'form:vsize',
    'form:hsize',
  ];
  const clickTimes = [];

  /** 形态巡演：依次演示 17 种形态（像展示视频那样，每种 ~1.4 秒） */
  let tourTimer = null;
  function stopFormTour(quiet) {
    if (tourTimer) {
      clearTimeout(tourTimer);
      tourTimer = null;
      if (!quiet) say('巡演结束～', 2000);
    }
  }
  function startFormTour() {
    stopFormTour(true);
    const ids = FORM_IDS.slice();
    let i = 0;
    say('形态巡演，开始！', 2000);
    const step = () => {
      if (i >= ids.length) {
        tourTimer = null;
        setForm('normal', { force: true, silent: true });
        say('17 种形态，都看完了～', 2400);
        return;
      }
      const id = ids[i];
      const spec = FORMS[id];
      setForm(id, { force: true, silent: true });
      if (spec && spec.label) say(`${spec.n}. ${spec.label}`, 1200);
      i += 1;
      tourTimer = setTimeout(step, 1400);
    };
    step();
  }

  /** 把点击换算成一个物理冲量：点哪边就往反方向弹，连点会叠加 */
  function clickImpulse(target, burst) {
    if (!api || !api.impulse) return;
    const r = petImg ? petImg.getBoundingClientRect() : null;
    const lp = state.lastPointer;
    let rx = 0.5;
    if (r && r.width > 4) rx = Math.max(0, Math.min(1, (lp.x - r.left) / r.width));
    const side = rx < 0.5 ? 1 : -1; // 点左边 → 往右弹
    const away = Math.abs(rx - 0.5) * 2; // 0=正中，1=最外侧
    const boost = 1 + Math.min(2, Math.max(0, burst - 1)) * 0.35;
    let vx = 0;
    let vy = 0;
    let squash = 0.35;
    if (target === 'head') {
      vy = 150;
      squash = 0.55; // 被按了一下：先往下压
    } else if (target === 'wing') {
      vy = -430 * boost;
      vx = side * (80 + 90 * away);
      squash = 0.5; // 吓一跳：弹起来
    } else if (target === 'hair') {
      vy = -240;
      vx = side * 70 * away;
      squash = 0.4;
    } else {
      vy = -300 * boost;
      vx = side * (70 + 110 * away) * boost;
      squash = 0.38; // 戳一下：小跳 + 侧推
    }
    api.impulse({ vx, vy, squash });
  }

  function reactToClick(target) {
    if (api) api.activity();
    noteInteraction();
    stopFormTour(true);

    const now = Date.now();
    clickTimes.push(now);
    while (clickTimes.length && now - clickTimes[0] > 2600) clickTimes.shift();
    const burst = clickTimes.length;

    // 连点太多：先闹脾气（原地乱晃），再被点晕（转着晃）
    if (burst >= 5) {
      clickTimes.length = 0;
      if (api && api.impulse) api.impulse({ vx: (Math.random() < 0.5 ? -1 : 1) * 320, vy: -200, squash: 0.5 });
      ACTION_PLAY.dizzy();
      return;
    }
    if (burst >= 3) {
      if (api && api.impulse) api.impulse({ vx: (Math.random() < 0.5 ? -1 : 1) * (260 + Math.random() * 180), vy: -170, squash: 0.5 });
      ACTION_PLAY.angry();
      return;
    }

    if (target === 'head') {
      clickImpulse(target, burst);
      // 摸头：主体是撒娇，但偶尔会冒出别的表情
      if (Math.random() < 0.3) {
        ACTION_PLAY[Math.random() < 0.5 ? 'shy' : 'happy']();
        return;
      }
      playAnim('pat', {
        duration: 900,
        say: line('headpat'),
        effect: () => window.FireflyFx.burst('heart', 3, { x: 0.5, y: 0.35 }),
      });
      return;
    }
    if (target === 'wing') {
      clickImpulse(target, burst);
      ACTION_PLAY.surprised();
      return;
    }
    if (target === 'hair') {
      clickImpulse(target, burst);
      playAnim('pat', {
        duration: 900,
        say: line('hair'),
        effect: () => window.FireflyFx.burst('butterfly', 2, { x: 0.6, y: 0.3 }),
      });
      return;
    }

    // 戳身体：物理小跳 + 从「表情 + 形态」混合池里随机抽一个
    clickImpulse(target, burst);
    const pick = CLICK_POOL[Math.floor(Math.random() * CLICK_POOL.length)];
    if (pick.indexOf('form:') === 0) {
      const spec = FORMS[pick.slice(5)];
      setForm(pick.slice(5), { force: true, revertMs: 2800 });
      if (spec && spec.label) say(`${spec.n}. ${spec.label}`, 2200);
      return;
    }
    const player = ACTION_PLAY[pick];
    if (player) player();
    else
      playAnim('pat', {
        duration: 700,
        say: line('body'),
        effect: () => window.FireflyFx.burst('star', 2, { x: 0.5, y: 0.4 }),
      });
  }

  // ------------------------------------------------------------------
  // 主进程指令
  // ------------------------------------------------------------------
  const ACTION_PLAY = {
    headpat: () =>
      playAnim('pat', {
        duration: 900,
        say: line('headpat'),
        effect: () => window.FireflyFx.burst('heart', 4, { x: 0.5, y: 0.35 }),
      }),
    snack: () =>
      playAnim('eat', {
        duration: 2600,
        say: line('feed'),
        effect: () => window.FireflyFx.burst('snack', 3, { x: 0.5, y: 0.45 }),
      }),
    talk: () =>
      playAnim('talk', {
        duration: 3600,
        say: line('greet'),
        sayMs: 3600,
      }),
    stretch: () =>
      playAnim('stretch', { duration: 1900, effect: () => window.FireflyFx.burst('star', 3, { x: 0.5, y: 0.5 }) }),
    look: () => playAnim('look', { duration: 2600 }),
    hum: () =>
      playAnim('hum', {
        duration: 3000,
        effect: () => window.FireflyFx.burst('note', 3, { x: 0.42, y: 0.32 }),
      }),
    nap: () =>
      playAnim('nap', {
        duration: 3400,
        say: '呼…呼…',
        effect: () => {
          window.FireflyFx.burst('zzz', 3, { x: 0.66, y: 0.26 });
        },
      }),
    sit: () => playAnim('sit', { duration: 2600, effect: () => window.FireflyFx.burst('star', 2, { x: 0.5, y: 0.5 }) }),
    butterfly: () =>
      playAnim('cheer', {
        duration: 1600,
        effect: () => window.FireflyFx.burst('butterfly', 5, { x: 0.5, y: 0.4 }),
      }),
    ultimate: () =>
      playAnim('cheer', {
        state: 'ultimate',
        duration: 2700,
        say: line('ultimate'),
        effect: () => {
          window.FireflyFx.ring(3, { y: 0.6 });
          window.FireflyFx.burst('fire', 5, { x: 0.5, y: 0.5 });
          window.FireflyFx.burst('spark', 6, { x: 0.5, y: 0.55 });
        },
      }),
    sit: () => setPose('sit'),
    stand: () => setPose('stand'),
    'form-tour': () => startFormTour(),
    'form-tour-stop': () => stopFormTour(),
    'toggle-sit': () => {
      const next = state.pose === 'sit' ? 'stand' : 'sit';
      setPose(next);
      say(next === 'sit' ? '那…我坐一会儿。' : '嗯，站起来啦～', 2600);
    },
    greet: () =>
      playAnim('greet', {
        duration: 1600,
        say: line('greet'),
        effect: () => {
          window.FireflyFx.ring(1, { y: 0.66 });
          window.FireflyFx.burst('spark', 4, { x: 0.5, y: 0.5 });
        },
      }),
    shy: () =>
      playAnim('shy', {
        duration: 1500,
        say: line('shy'),
        effect: () => {
          window.FireflyFx.burst('heart', 3, { x: 0.5, y: 0.3 });
          window.FireflyFx.spawn('sweat', { x: 0.64, y: 0.26, dx: 6, dy: -46, size: 14 });
        },
      }),

    // ---- 表情包一套（短反应动作） ----
    happy: () =>
      playAnim('cheer', {
        duration: 1600,
        say: line('happy'),
        effect: () => {
          window.FireflyFx.burst('heart', 2, { x: 0.5, y: 0.34 });
          window.FireflyFx.burst('shine', 3, { x: 0.5, y: 0.5 });
        },
      }),
    angry: () =>
      playAnim('angry', {
        duration: 1700,
        say: line('angry'),
        effect: () => window.FireflyFx.spawn('anger', { x: 0.7, y: 0.2, dx: 8, dy: -46, size: 20 }),
      }),
    surprised: () =>
      playAnim('shock', {
        duration: 950,
        say: line('surprised'),
        effect: () => window.FireflyFx.spawn('exclaim', { x: 0.7, y: 0.18, dx: 6, dy: -54, size: 22 }),
      }),
    confused: () =>
      playAnim('look', {
        duration: 1900,
        say: line('confused'),
        effect: () => window.FireflyFx.spawn('question', { x: 0.7, y: 0.2, dx: 4, dy: -50, size: 21 }),
      }),
    sad: () =>
      playAnim('sad', {
        duration: 2200,
        say: line('sad'),
        effect: () => {
          window.FireflyFx.burst('tear', 2, { x: 0.46, y: 0.3 });
          window.FireflyFx.spawn('sweat', { x: 0.7, y: 0.3, size: 14 });
        },
      }),
    proud: () =>
      playAnim('proud', {
        duration: 1700,
        say: line('proud'),
        effect: () => window.FireflyFx.burst('spark', 4, { x: 0.5, y: 0.42 }),
      }),
    nod: () =>
      playAnim('nod', {
        duration: 1400,
        say: line('nod'),
        effect: () => window.FireflyFx.burst('star', 2, { x: 0.5, y: 0.6 }),
      }),
    shake: () =>
      playAnim('shake', {
        duration: 1600,
        say: line('shake'),
        effect: () => window.FireflyFx.spawn('sweat', { x: 0.7, y: 0.24, size: 14 }),
      }),
    thumbs: () =>
      playAnim('like', {
        duration: 1300,
        say: line('thumbs'),
        effect: () => window.FireflyFx.spawn('thumb', { x: 0.66, y: 0.26, dx: 8, dy: -58, size: 20 }),
      }),
    call: () =>
      playAnim('call', {
        duration: 2100,
        say: line('call'),
        effect: () => {
          window.FireflyFx.burst('music', 3, { x: 0.46, y: 0.34 });
          window.FireflyFx.burst('fire', 2, { x: 0.56, y: 0.5 });
        },
      }),
    dizzy: () =>
      playAnim('dizzy', {
        duration: 2000,
        say: line('dizzy'),
        effect: () => window.FireflyFx.burst('dizzy', 3, { x: 0.5, y: 0.22 }),
      }),
  };

  if (api) {
    api.on('pet:motion', (payload) => {
      if (!payload) return;
      const previousAction = state.action;
      state.facing = payload.facing >= 0 ? 1 : -1;
      state.dragged = Boolean(payload.dragged);
      state.airborne = Boolean(payload.airborne);
      state.walking = Boolean(payload.walking);
      state.vx = Number(payload.vx) || 0;
      state.vy = Number(payload.vy) || 0;
      state.x = Number(payload.x) || state.x;
      state.y = Number(payload.y) || state.y;
      if (typeof payload.squash === 'number' && payload.squash > state.squashImpulse) {
        state.squashImpulse = payload.squash;
      }
      // 拖拽/抛飞/行走是物理状态，随时打断一次性动作；其余状态等动作播完
      // （state.action 只由 setBaseAction 写，避免「已记录动作但类没挂上」的错位）
      const interruptible = payload.action === 'drag' || payload.action === 'fly' || payload.action === 'walk';
      const canTransition = interruptible || !state.busyUntil || performance.now() > state.busyUntil;
      if (canTransition) {
        if (interruptible) state.busyUntil = 0;
        setBaseAction(payload.action);
        // 睡觉时坐下打盹，醒来站起
        if (payload.action === 'sleep') setPose('sit');
        if (payload.action === 'drag') noteInteraction();
        if (payload.action === 'drag' && previousAction !== 'drag') say(line('drag'), 1800);
        if (payload.action === 'fly' && previousAction === 'drag') say(line('fall'), 1500);
        if (previousAction === 'fly' && payload.action === 'idle') {
          say(line('land'), 1800);
          window.FireflyFx.burst('sweat', 3, { x: 0.5, y: 0.5 });
        }
      }
      const fast = Math.hypot(state.vx, state.vy) > 1100;
      pet.classList.toggle('fast', fast);
      applyFacing();
    });

    api.on('pet:play', (payload) => {
      const action = payload && payload.action;
      if (typeof action === 'string' && action.indexOf('form:') === 0) {
        setForm(action.slice(5), { force: true });
        return;
      }
      const player = ACTION_PLAY[action];
      if (player) player();
      else if (action) say(line('idle'), 2600);
    });

    api.on('pet:form', (payload) => {
      const id = payload && payload.id;
      if (typeof id === 'string' && id !== 'auto') setForm(id, { force: true });
    });


    api.on('pet:idle-flavor', () => {
      if (state.dragged || state.airborne || state.busyUntil) return;
      const flavors = ['look', 'hum', 'stretch', 'sit', 'butterfly'];
      const pick = flavors[Math.floor(Math.random() * flavors.length)];
      const player = ACTION_PLAY[pick];
      if (player) player();
    });

    api.on('pet:escape', () => {
      hideBubble();
      state.busyUntil = 0;
      setBaseAction(currentBaseAction());
    });

    api.on('pet:click-through', (payload) => {
      state.clickThrough = Boolean(payload && payload.on);
      document.body.classList.toggle('click-through', state.clickThrough);
      if (state.clickThrough) {
        hideBubble();
        say('鼠标穿透已开启，右键托盘图标可以关掉～', 2600);
      }
    });

    api.ready();
  }

  // ------------------------------------------------------------------
  // 键盘快捷键（窗口有焦点时）
  // ------------------------------------------------------------------
  window.addEventListener('keydown', (event) => {
    if (event.key === 'F1') {
      if (api) api.action('headpat');
    } else if (event.key === 'F2') {
      if (api) api.action('snack');
    } else if (event.key === 'F3') {
      if (api) api.action('ultimate');
    } else if (event.key === 'F4') {
      if (api) api.action('throw');
    } else if (event.key === 'F5') {
      if (api) api.action('walk-random');
    } else if (event.key === 'Escape') {
      hideBubble();
    }
  });

  // ------------------------------------------------------------------
  // 启动
  // ------------------------------------------------------------------
  relayout();
  window.addEventListener('resize', relayout);
  setAction('idle', { force: true });

  // 上屏：不依赖 requestAnimationFrame —— 某些显示/合成环境（虚拟显示器、
  // 远程桌面）里 rAF 可能不触发，若把 body 的 opacity 交给 rAF 解除，
  // 整只宠物就会"隐形"（窗口在、进程在、画面全空）。
  document.body.classList.add('ready');

  let rafAlive = false;
  function frameTick() {
    rafAlive = true;
    frame(performance.now());
  }
  requestAnimationFrame(frameTick);

  setTimeout(() => {
    // 诊断快照：窗口在、进程在、却看不见时，这一行能定位到底哪一环是空的
    try {
      const petEl = document.getElementById('pet');
      const sprEl = document.getElementById('sprite');
      const rect = (el) => (el ? `${Math.round(el.getBoundingClientRect().width)}x${Math.round(el.getBoundingClientRect().height)}` : 'null');
      const cs = (el, prop) => (el ? getComputedStyle(el)[prop] : 'null');
      const img = petImg;
      console.log(
        `[diag] img=${img ? 'yes' : 'no'} loaded=${img ? img.complete : '-'} natural=${img ? img.naturalWidth + 'x' + img.naturalHeight : '-'} ` +
          `imgRect=${rect(img)} petRect=${rect(petEl)} spriteRect=${rect(sprEl)} bodyOpacity=${cs(document.body, 'opacity')} ` +
          `petPos=${cs(petEl, 'position')} inner=${window.innerWidth}x${window.innerHeight} ` +
          `scale=${getComputedStyle(document.documentElement).getPropertyValue('--s')} dpr=${window.devicePixelRatio}`,
      );
    } catch (error) {
      console.log('[diag] failed: ' + (error && error.message));
    }
  }, 1500);

  // 帧循环兜底：rAF 若 800ms 内没跑过，改用 setInterval 驱动
  setTimeout(() => {
    if (rafAlive) return;
    useIntervalDriver = true;
    console.warn('requestAnimationFrame 未触发，切换到 setInterval 驱动');
    setInterval(() => frame(performance.now()), 16);
  }, 800);

  if (api) {
    api
      .getConfig()
      .then((cfg) => {
        config = { ...config, ...(cfg || {}) };
        state.clickThrough = Boolean(config.clickThrough);
        document.body.classList.toggle('click-through', state.clickThrough);
        relayout();
      })
      .catch(() => {
        /* 拿不到配置也能跑 */
      });
  }

  setTimeout(() => say(line('greet'), 3600), 700);

  // 定期自言自语（配置里关了说话就静默）
  setInterval(() => {
    if (!config.speech) return;
    if (state.dragged || state.airborne || state.busyUntil) return;
    if (bubble.classList.contains('show')) return;
    if (Math.random() < 0.35) say(line('idle'), 3000);
  }, 75000);

  // 本地随机小动作（不依赖漫游：原地伸懒腰 / 张望 / 哼歌 / 打招呼 / 害羞 / 蝴蝶 / 打瞌睡）
  setInterval(() => {
    if (state.dragged || state.airborne || state.walking || state.busyUntil) return;
    if (bubble.classList.contains('show')) return;
    if (Math.random() >= 0.45) return;
    const flavors = ['look', 'hum', 'stretch', 'greet', 'shy', 'butterfly', 'nap'];
    const pick = flavors[Math.floor(Math.random() * flavors.length)];
    const player = ACTION_PLAY[pick];
    if (player) player();
  }, 32000);

  // 闲置一会儿自己坐下晃腿；任何交互都会站起来（不走路，移动靠拖动）
  setInterval(() => {
    if (state.dragged || state.airborne || state.walking || state.busyUntil) {
      state.idleSince = Date.now();
      return;
    }
    const idleFor = (Date.now() - state.idleSince) / 1000;
    // 形态 3：后台运行（闲着但没闲透，站在原地小动作）
    if (idleFor > 12 && idleFor <= 25 && state.pose === 'stand' && state.form === 'normal') {
      setForm('bg', { silent: true });
    }
    if (idleFor > 25 && state.pose !== 'sit') {
      setForm('normal', { silent: true });
      setPose('sit');
    }
  }, 3000);
})();