'use strict';

/**
 * sprite.js —— Q 版流萤（Firefly）本体。
 *
 * 按官方 Q 版形象重绘（全 SVG 手绘 + 程序化生成，零外部素材）：
 *  - 体型：Q 版二头身，超大脑袋、小身体、厚底靴；
 *  - 头发：银白长发，发梢渐变到薄荷青绿，深蓝发带 + 薄荷星形发饰；
 *  - 五官：紫→粉渐变的大眼睛、腮红、小巧的嘴；
 *  - 服装：深蓝外套 + 奶白内衬 + 金色蝴蝶结 + 青绿宝石胸针，白到浅青的百褶裙；
 *  - 配饰：薄荷绿蝴蝶发饰（会扇动）、手中的青绿法杖（宝珠会发光）；
 *  - 长发尾可摆动：飞行 / 大招时用作「翼」的动作载体。
 *
 * 各部件 id 与 style.css、renderer.js 约定一致（head / body / wingL / wingR / hair-back /
 * ponytail / leg-l / leg-r / arm-l / arm-r / core / aura / hairpin / motes）。
 * 坐标系固定 340x506，窗口按比例缩放。
 */

(function () {
  const NAVY = '#2b3550';
  const NAVY_DARK = '#1a2338';

  const grad = `
    <defs>
      <linearGradient id="hairGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#ffffff" />
        <stop offset="48%" stop-color="#f0f7fb" />
        <stop offset="74%" stop-color="#d6ecef" />
        <stop offset="100%" stop-color="#9adcd8" />
      </linearGradient>
      <linearGradient id="hairBackGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#f7fbfe" />
        <stop offset="45%" stop-color="#e6f2f8" />
        <stop offset="78%" stop-color="#c8e6ea" />
        <stop offset="100%" stop-color="#8ed6d4" />
      </linearGradient>
      <linearGradient id="tipGlow" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#c8f0ec" stop-opacity="0.9" />
        <stop offset="100%" stop-color="#6fc8cc" stop-opacity="0" />
      </linearGradient>
      <linearGradient id="skinGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#fff8f2" />
        <stop offset="100%" stop-color="#fbe8de" />
      </linearGradient>
      <linearGradient id="coatGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#33405f" />
        <stop offset="100%" stop-color="#1b2440" />
      </linearGradient>
      <linearGradient id="shirtGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#fffdf8" />
        <stop offset="100%" stop-color="#eef6f6" />
      </linearGradient>
      <linearGradient id="skirtGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#ffffff" />
        <stop offset="62%" stop-color="#e8f6f7" />
        <stop offset="100%" stop-color="#b6e2e4" />
      </linearGradient>
      <linearGradient id="goldGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#f7dfa8" />
        <stop offset="55%" stop-color="#e8bd6a" />
        <stop offset="100%" stop-color="#c9923c" />
      </linearGradient>
      <linearGradient id="gemGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#cffaf6" />
        <stop offset="50%" stop-color="#5fd0dc" />
        <stop offset="100%" stop-color="#2e9ec0" />
      </linearGradient>
      <linearGradient id="eyeGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#7d93d6" />
        <stop offset="42%" stop-color="#a48fe0" />
        <stop offset="78%" stop-color="#e79ec8" />
        <stop offset="100%" stop-color="#fbb6cc" />
      </linearGradient>
      <radialGradient id="orbGrad" cx="38%" cy="34%" r="70%">
        <stop offset="0%" stop-color="#f2fffd" />
        <stop offset="55%" stop-color="#8ce8e6" />
        <stop offset="100%" stop-color="#3fb8d0" />
      </radialGradient>
      <radialGradient id="auraGrad" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#b8f0ea" stop-opacity="0.5" />
        <stop offset="60%" stop-color="#8fd8e0" stop-opacity="0.16" />
        <stop offset="100%" stop-color="#8fd8e0" stop-opacity="0" />
      </radialGradient>
      <linearGradient id="bootGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#2c3a58" />
        <stop offset="100%" stop-color="#161e33" />
      </linearGradient>
      <filter id="blur6" x="-40%" y="-40%" width="180%" height="180%">
        <feGaussianBlur stdDeviation="6" />
      </filter>
    </defs>`;

  /** 一只大眼睛：眼白 + 独立瞳孔组（瞳孔负责跟随鼠标）+ 睫毛高光 */
  function eye(cx, cy) {
    return `
      <g class="eye">
        <ellipse cx="${cx}" cy="${cy}" rx="27" ry="33" fill="${NAVY}" />
        <ellipse cx="${cx}" cy="${cy + 1}" rx="23" ry="29" fill="url(#eyeGrad)" />
        <ellipse cx="${cx}" cy="${cy - 12}" rx="20" ry="12" fill="${NAVY}" opacity="0.45" />
        <g class="pupil">
          <ellipse cx="${cx}" cy="${cy + 13}" rx="15" ry="11" fill="#ffd9e6" opacity="0.55" />
          <ellipse cx="${cx - 7}" cy="${cy - 9}" rx="8.5" ry="9.5" fill="#ffffff" opacity="0.95" />
          <ellipse cx="${cx + 8}" cy="${cy + 11}" rx="4.2" ry="4.6" fill="#ffffff" opacity="0.8" />
          <ellipse cx="${cx + 2}" cy="${cy - 16}" rx="3" ry="2.4" fill="#ffffff" opacity="0.7" />
        </g>
        <path d="M ${cx - 29} ${cy - 20} q 30 -17 58 -1" stroke="${NAVY_DARK}" stroke-width="7" fill="none" stroke-linecap="round" />
        <path d="M ${cx - 27} ${cy + 26} q 27 9 54 -2" stroke="#7a86ad" stroke-width="2.4" fill="none" opacity="0.5" stroke-linecap="round" />
      </g>`;
  }

  /** 长裙褶边（尖角裙摆） */
  function skirtHem(cx, y, halfWidth, teeth) {
    const step = (halfWidth * 2) / teeth;
    let d = `M ${cx - halfWidth} ${y}`;
    for (let i = 0; i < teeth; i += 1) {
      const x0 = cx - halfWidth + step * i;
      d += ` L ${x0 + step * 0.5} ${y + 16} L ${x0 + step} ${y}`;
    }
    return d;
  }

  function leg(side) {
    // 腿中线：左 150 / 右 190
    const c = side === 'l' ? 150 : 190;
    return `
      <g id="leg-${side}" class="limb">
        <!-- 奶白长袜 -->
        <path d="M ${c - 20} 424 L ${c - 16} 470 L ${c + 16} 470 L ${c + 20} 424 Z" fill="#fbf5ec" stroke="#dccfc0" stroke-width="1.6" />
        <path d="M ${c - 15} 436 l 8 8 M ${c - 7} 432 l 8 8 M ${c + 1} 436 l 8 8" stroke="#e0d3c2" stroke-width="1.6" opacity="0.9" />
        <!-- 深蓝短靴 -->
        <path d="M ${c - 18} 466 h 36 a 11 11 0 0 1 0 22 h -36 a 11 11 0 0 1 0 -22 Z" fill="url(#bootGrad)" stroke="${NAVY_DARK}" stroke-width="1.6" />
        <path d="M ${c - 16} 484 h 32 a 11 11 0 0 1 0 20 h -32 a 11 11 0 0 1 0 -20 Z" fill="#141b2e" />
        <path d="M ${c - 12} 490 h 24" stroke="#5fd0dc" stroke-width="2" opacity="0.75" />
        <!-- 靴口蕾丝 + 金色搭扣 -->
        <path d="M ${c - 19} 466 h 38" stroke="#fbf5ec" stroke-width="4" stroke-linecap="round" />
        <circle cx="${c + 8}" cy="478" r="3.4" fill="url(#goldGrad)" />
        <circle cx="${c + 8}" cy="492" r="3" fill="url(#goldGrad)" />
      </g>`;
  }

  function build() {
    return `
<svg id="firefly-svg" viewBox="0 0 340 506" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMax meet">
  ${grad}

  <!-- 背后柔光 -->
  <ellipse id="aura" cx="170" cy="300" rx="152" ry="150" fill="url(#auraGrad)" />

  <!-- 长发主体（后层） -->
  <g id="hair-back">
    <path d="M 170 96 C 106 96, 60 142, 58 202 C 56 272, 50 334, 57 392
             C 61 434, 76 464, 96 478 C 118 490, 152 482, 170 472
             C 188 482, 222 490, 244 478 C 264 464, 279 434, 283 392
             C 290 334, 284 272, 282 202 C 280 142, 234 96, 170 96 Z"
          fill="url(#hairBackGrad)" stroke="${NAVY}" stroke-width="2.6" />
    <path d="M 66 400 C 74 448, 96 474, 122 480 C 96 470, 78 440, 74 396 Z" fill="url(#tipGlow)" />
    <path d="M 274 400 C 266 448, 244 474, 218 480 C 244 470, 262 440, 266 396 Z" fill="url(#tipGlow)" />
  </g>

  <!-- 两条长发尾（飞行/大招时摆动；id 沿用 wingL/wingR 以复用动画） -->
  <g id="wingL" class="wing wing-l">
    <path d="M 104 168 C 74 216, 62 300, 66 372 C 68 416, 82 448, 104 462
             C 92 424, 84 348, 96 268 C 102 226, 112 196, 122 176 Z"
          fill="url(#hairGrad)" stroke="${NAVY}" stroke-width="2.4" />
    <path d="M 74 430 C 80 452, 92 464, 106 462 C 92 458, 82 446, 76 424 Z" fill="url(#tipGlow)" />
  </g>
  <g id="wingR" class="wing wing-r">
    <path d="M 236 168 C 266 216, 278 300, 274 372 C 272 416, 258 448, 236 462
             C 248 424, 256 348, 244 268 C 238 226, 228 196, 218 176 Z"
          fill="url(#hairGrad)" stroke="${NAVY}" stroke-width="2.4" />
    <path d="M 266 430 C 260 452, 248 464, 234 462 C 248 458, 258 446, 264 424 Z" fill="url(#tipGlow)" />
  </g>
  <g id="ponytail">
    <path d="M 214 210 C 244 250, 252 330, 240 400 C 234 434, 220 456, 206 466
             C 226 430, 232 356, 206 268 Z" fill="url(#hairGrad)" stroke="${NAVY}" stroke-width="2" opacity="0.95" />
  </g>
  <g id="ponytail-glow">
    <path d="M 214 452 C 220 462, 210 470, 202 464 C 210 462, 214 458, 214 452 Z" fill="url(#tipGlow)" />
  </g>

  <!-- 萤火微光 -->
  <g id="motes">
    <circle class="mote m1" cx="62" cy="300" r="3.2" fill="#d8f8f4" />
    <circle class="mote m2" cx="292" cy="262" r="2.6" fill="#bff0ea" />
    <circle class="mote m3" cx="256" cy="404" r="2.8" fill="#cff6f2" />
    <circle class="mote m4" cx="86" cy="414" r="2.4" fill="#ffe6b0" />
    <circle class="mote m5" cx="300" cy="180" r="2.2" fill="#e8fffb" />
  </g>

  <!-- 腿 / 袜 / 靴 -->
  ${leg('l')}
  ${leg('r')}

  <!-- 裙 + 外套 + 躯干 -->
  <g id="body">
    <!-- 长裙（白 → 浅青，尖角褶边） -->
    <path id="skirt" d="M 124 366 L 216 366 C 234 396, 246 418, 252 434
             ${''}
             L 230 428 L 228 444 L 200 434 L 196 452 L 170 438 L 144 452 L 140 434 L 112 444 L 110 428 L 88 434
             C 94 418, 106 396, 124 366 Z"
          fill="url(#skirtGrad)" stroke="#8ec9cc" stroke-width="2" />
    <path d="M 118 372 Q 170 392 222 372" stroke="#ffffff" stroke-width="3" fill="none" opacity="0.9" />
    <path d="M 126 404 Q 170 424 214 404" stroke="#a8e0e0" stroke-width="2.2" fill="none" opacity="0.85" />
    <circle cx="170" cy="414" r="3.2" fill="url(#goldGrad)" />
    <circle cx="140" cy="422" r="2.6" fill="url(#goldGrad)" opacity="0.9" />
    <circle cx="200" cy="422" r="2.6" fill="url(#goldGrad)" opacity="0.9" />

    <!-- 深蓝外套 -->
    <path id="torso" d="M 132 288 L 208 288 C 222 318, 224 350, 218 386 Q 170 404 122 386 C 116 350, 118 318, 132 288 Z"
          fill="url(#coatGrad)" stroke="${NAVY_DARK}" stroke-width="2.2" />
    <!-- 奶白内衬与衣领 -->
    <path d="M 150 288 L 190 288 L 170 344 Z" fill="url(#shirtGrad)" />
    <path d="M 128 292 Q 170 314 212 292" stroke="#fbf6ea" stroke-width="9" fill="none" stroke-linecap="round" />
    <path d="M 138 380 L 152 292 M 202 380 L 188 292" stroke="url(#goldGrad)" stroke-width="3.4" fill="none" opacity="0.95" />
    <path d="M 124 386 Q 170 402 216 386" stroke="url(#goldGrad)" stroke-width="2.6" fill="none" opacity="0.8" />

    <!-- 胸前：青绿胸针 + 金色蝴蝶结（core 用于发光呼吸） -->
    <g id="core">
      <ellipse cx="170" cy="308" rx="17" ry="15" fill="#6fe0e8" opacity="0.3" filter="url(#blur6)" />
      <path d="M 170 296 L 180 308 L 170 320 L 160 308 Z" fill="url(#gemGrad)" stroke="#eafaf8" stroke-width="1.6" />
      <circle cx="166" cy="304" r="2.6" fill="#ffffff" opacity="0.9" />
    </g>
    <g id="bow">
      <path d="M 170 340 C 150 326, 132 336, 138 352 C 144 366, 160 358, 170 340 Z" fill="url(#goldGrad)" stroke="#b8873a" stroke-width="1.6" />
      <path d="M 170 340 C 190 326, 208 336, 202 352 C 196 366, 180 358, 170 340 Z" fill="url(#goldGrad)" stroke="#b8873a" stroke-width="1.6" />
      <path d="M 164 350 L 156 378 L 166 374 Z" fill="#e0b25c" stroke="#b8873a" stroke-width="1.2" />
      <path d="M 176 350 L 184 378 L 174 374 Z" fill="#e0b25c" stroke="#b8873a" stroke-width="1.2" />
      <ellipse cx="170" cy="344" rx="8" ry="9" fill="url(#goldGrad)" stroke="#b8873a" stroke-width="1.6" />
      <circle cx="170" cy="344" r="3.2" fill="#4fc8d8" />
    </g>
  </g>

  <!-- 左臂（自然下垂） -->
  <g id="arm-l" class="limb">
    <path d="M 138 302 C 128 328, 124 352, 126 374" stroke="url(#coatGrad)" stroke-width="22" fill="none" stroke-linecap="round" />
    <path d="M 126 372 h 16" stroke="#fbf6ea" stroke-width="7" stroke-linecap="round" />
    <ellipse cx="130" cy="382" rx="10" ry="9.5" fill="url(#skinGrad)" stroke="#e8cfc2" stroke-width="1.2" />
  </g>

  <!-- 法杖（在右臂之后绘制，手会压住杖身） -->
  <g id="staff">
    <path d="M 262 128 L 246 372" stroke="#b8ae94" stroke-width="9" fill="none" stroke-linecap="round" />
    <path d="M 262 128 L 246 372" stroke="url(#goldGrad)" stroke-width="5" fill="none" stroke-linecap="round" />
    <path d="M 250 168 h 22" stroke="url(#goldGrad)" stroke-width="4.5" fill="none" stroke-linecap="round" />
    <ellipse id="staff-orb-glow" cx="263" cy="112" rx="26" ry="26" fill="#7fe8ea" opacity="0.32" filter="url(#blur6)" />
    <circle id="staff-orb" cx="263" cy="112" r="17" fill="url(#orbGrad)" stroke="#eafaf8" stroke-width="1.8" />
    <path d="M 263 100 l 3.4 8.6 8.6 3.4 -8.6 3.4 -3.4 8.6 -3.4 -8.6 -8.6 -3.4 8.6 -3.4 Z" fill="#ffffff" opacity="0.9" />
  </g>

  <!-- 右臂（抬起握杖） -->
  <g id="arm-r" class="limb">
    <path d="M 206 300 C 228 302, 240 306, 246 316" stroke="url(#coatGrad)" stroke-width="22" fill="none" stroke-linecap="round" />
    <path d="M 240 310 l 12 -8" stroke="#fbf6ea" stroke-width="7" stroke-linecap="round" />
    <ellipse cx="252" cy="296" rx="10.5" ry="10" fill="url(#skinGrad)" stroke="#e8cfc2" stroke-width="1.2" />
  </g>

  <!-- 头部 -->
  <g id="head">
    <!-- 脸 -->
    <ellipse cx="170" cy="205" rx="88" ry="84" fill="url(#skinGrad)" stroke="#eccfc4" stroke-width="1.6" />
    <!-- 耳侧腮红 -->
    <ellipse cx="94" cy="238" rx="14" ry="18" fill="#f7c4cd" opacity="0.5" />
    <ellipse cx="246" cy="238" rx="14" ry="18" fill="#f7c4cd" opacity="0.5" />

    <!-- 刘海：齐刘海 + 两侧鬓发 -->
    <path d="M 84 200 C 80 138, 116 102, 170 100 C 224 102, 260 138, 256 200
             C 252 178, 246 164, 236 154 C 212 186, 192 192, 170 192
             C 148 192, 128 186, 104 154 C 94 164, 88 178, 84 200 Z"
          fill="url(#hairGrad)" stroke="${NAVY}" stroke-width="2.4" />
    <path d="M 108 150 C 126 176, 148 188, 170 190 C 192 188, 214 176, 232 150
             C 214 168, 190 178, 170 178 C 150 178, 126 168, 108 150 Z" fill="#dcecf4" opacity="0.75" />
    <!-- 鬓发（左右各一缕） -->
    <path d="M 96 168 C 78 214, 76 268, 86 312 C 90 286, 94 246, 106 208 Z" fill="url(#hairGrad)" stroke="${NAVY}" stroke-width="2.2" />
    <path d="M 244 168 C 262 214, 264 268, 254 312 C 250 286, 246 246, 234 208 Z" fill="url(#hairGrad)" stroke="${NAVY}" stroke-width="2.2" />
    <!-- 呆毛 -->
    <path d="M 166 104 C 152 78, 176 62, 196 54 C 178 74, 170 88, 172 104 Z" fill="url(#hairGrad)" stroke="${NAVY}" stroke-width="2.2" />

    <!-- 深蓝发带 + 薄荷星形发饰 -->
    <path d="M 88 164 C 118 124, 222 124, 252 164" stroke="#232e48" stroke-width="18" fill="none" stroke-linecap="round" />
    <path d="M 96 156 C 124 122, 216 122, 244 156" stroke="#3d4a6b" stroke-width="3" fill="none" opacity="0.85" />
    <path d="M 112 130 l 4.4 11 11 4.4 -11 4.4 -4.4 11 -4.4 -11 -11 -4.4 11 -4.4 Z" fill="#b8ecd8" stroke="#8fd8c8" stroke-width="1.2" />

    <!-- 眼睛 -->
    ${eye(128, 232)}
    ${eye(212, 232)}

    <!-- 腮红 + 嘴 -->
    <ellipse cx="112" cy="262" rx="17" ry="9" fill="#f7aec0" opacity="0.5" />
    <ellipse cx="228" cy="262" rx="17" ry="9" fill="#f7aec0" opacity="0.5" />
    <path d="M 164 268 q 6 7 12 0" stroke="#c4737e" stroke-width="3" fill="none" stroke-linecap="round" />

    <!-- 薄荷蝴蝶发饰（整体内移，避免右边缘裁切） -->
    <g id="hairpin">
      <g id="feather1"><path d="M 282 166 C 292 138, 314 128, 322 142 C 316 158, 300 168, 282 166 Z" fill="#bff0dc" stroke="#8fd8c8" stroke-width="1.5" /></g>
      <g id="feather2"><path d="M 282 172 C 298 152, 322 154, 326 168 C 316 178, 296 182, 282 172 Z" fill="#a8e8cc" stroke="#8fd8c8" stroke-width="1.5" /></g>
      <g id="feather3"><path d="M 280 178 C 292 190, 304 208, 296 220 C 282 214, 274 194, 280 178 Z" fill="#9fe0c8" stroke="#7fccc0" stroke-width="1.5" /></g>
      <g id="feather4"><path d="M 276 180 C 282 196, 280 214, 270 222 C 262 210, 264 190, 276 180 Z" fill="#bfeedc" stroke="#7fccc0" stroke-width="1.5" /></g>
      <ellipse cx="281" cy="176" rx="5" ry="13" fill="#2b3550" />
      <circle cx="281" cy="164" r="4.4" fill="url(#goldGrad)" />
      <path d="M 278 188 C 270 198, 262 206, 256 210" stroke="#2b3550" stroke-width="4" fill="none" stroke-linecap="round" />
      <path d="M 282 190 C 282 202, 280 212, 276 220" stroke="#2b3550" stroke-width="4" fill="none" stroke-linecap="round" />
    </g>
  </g>
</svg>`;
  }

  window.FIREFLY_SPRITE = { build };
})();
