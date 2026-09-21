/**
 * PoseRenderer — WiFi-DensePose skeleton & keypoint renderer
 * Rewritten v2 (2026-07-10): direct canvas 2D calls, no gradient state bugs,
 * handles confidence=0.0 ESP32 signal-derived keypoints correctly.
 */

// COCO-17 skeleton connections  [from, to]
const SKELETON = [
  [15, 13], [13, 11], [16, 14], [14, 12], [11, 12],  // lower-body
  [5, 11],  [6, 12],  [5, 6],                          // torso
  [5, 7],   [6, 8],   [7, 9],   [8, 10],               // arms
  [11, 13], [12, 14], [13, 15], [14, 16]               // legs
];

// Per-segment colours (index matches SKELETON array)
const SEG_COLORS = [
  '#ff6b6b','#ff6b6b','#ff6b6b','#ff6b6b','#ff6b6b',  // lower-body: red
  '#4ecdc4','#4ecdc4','#4ecdc4',                        // torso: teal
  '#ffe66d','#ffe66d','#ffe66d','#ffe66d',              // arms: yellow
  '#a29bfe','#a29bfe','#a29bfe','#a29bfe'              // legs: purple
];

// Per-keypoint colours (COCO-17 order)
const KP_COLORS = [
  '#ff6b6b',  // 0  nose
  '#ff9ff3',  // 1  left_eye
  '#ff9ff3',  // 2  right_eye
  '#ffeaa7',  // 3  left_ear
  '#ffeaa7',  // 4  right_ear
  '#74b9ff',  // 5  left_shoulder
  '#0984e3',  // 6  right_shoulder
  '#55efc4',  // 7  left_elbow
  '#00b894',  // 8  right_elbow
  '#fdcb6e',  // 9  left_wrist
  '#e17055',  // 10 right_wrist
  '#a29bfe',  // 11 left_hip
  '#6c5ce7',  // 12 right_hip
  '#fd79a8',  // 13 left_knee
  '#e84393',  // 14 right_knee
  '#81ecec',  // 15 left_ankle
  '#00cec9'   // 16 right_ankle
];

// Person colours for multi-person
const PERSON_COLORS = ['#00e676','#40c4ff','#ff6d00','#ea80fc','#ffff00'];

export class PoseRenderer {
  constructor(canvas, options = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.config = {
      mode: 'skeleton',
      showKeypoints: true,
      showSkeleton: true,
      showBoundingBox: false,
      showConfidence: true,
      showZones: true,
      showDebugInfo: false,
      skeletonColor: '#00ff00',
      keypointColor: '#ff0000',
      boundingBoxColor: '#0000ff',
      confidenceColor: '#ffffff',
      zoneColor: '#ffff00',
      keypointRadius: 5,
      skeletonWidth: 3,
      boundingBoxWidth: 2,
      fontSize: 12,
      // -1 means ALL keypoints render regardless of confidence value
      confidenceThreshold: 0.0,
      keypointConfidenceThreshold: -1,
      enableSmoothing: true,
      maxFps: 30,
      ...options
    };

    this.performanceMetrics = { frameCount: 0, lastFrameTime: 0, averageFps: 0, renderTime: 0 };

    // EMA smoothing state: personIdx → [{x,y}]
    this._smooth = new Map();
    this._alpha = 0.3; // lerp weight toward new position

    this._initCtx();
  }

  _initCtx() {
    this.ctx.imageSmoothingEnabled = true;
    this.ctx.font = `${this.config.fontSize}px monospace`;
    this.ctx.textAlign = 'left';
    this.ctx.textBaseline = 'top';
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  render(poseData, metadata = {}) {
    const t0 = performance.now();
    this.clearCanvas();

    if (!poseData || !Array.isArray(poseData.persons) || poseData.persons.length === 0) {
      this._noData();
      return;
    }

    const mode = this.config.mode || 'skeleton';

    poseData.persons.forEach((person, idx) => {
      if (!person) return;
      // Accept person-level confidence=0 (signal-derived) — only skip if
      // explicitly below the threshold (default 0.0, so nothing is skipped).
      if (typeof person.confidence === 'number' && person.confidence < this.config.confidenceThreshold) return;

      const kps = this._smooth_kps(idx, person.keypoints);

      if (mode === 'skeleton' || mode === 'keypoints' || mode === 'dense') {
        if (this.config.showSkeleton && kps && kps.length > 0) this._drawSkeleton(kps, idx);
        if (this.config.showKeypoints && kps && kps.length > 0) this._drawKeypoints(kps, idx);
      } else if (mode === 'heatmap') {
        if (kps && kps.length > 0) this._drawHeatmap(kps, idx);
      }

      if (this.config.showBoundingBox && person.bbox) this._drawBBox(person.bbox, idx);
      if (this.config.showConfidence) this._drawLabel(person, idx, kps);
    });

    if (this.config.showZones && poseData.zone_summary) this._drawZones(poseData.zone_summary);
    if (this.config.showDebugInfo) this._drawDebug(poseData);

    this._updateFps(t0);
  }

  clearCanvas() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    // Dark translucent background so content is always visible
    this.ctx.fillStyle = 'rgba(10, 15, 25, 0.85)';
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
  }

  resize(w, h) {
    this.canvas.width  = Math.round(w);
    this.canvas.height = Math.round(h);
    this._initCtx();
  }

  setMode(mode) { this.config.mode = mode; }
  updateConfig(c) { Object.assign(this.config, c); this._initCtx(); }
  getPerformanceMetrics() { return { ...this.performanceMetrics }; }
  getConfig() { return { ...this.config }; }
  exportFrame(fmt = 'png') { try { return this.canvas.toDataURL(`image/${fmt}`); } catch { return null; } }

  // ── Coordinate scaling ─────────────────────────────────────────────────────

  /**
   * scaleX — map a server x-coordinate to canvas pixels.
   * Server sends values in an 800-pixel-wide coordinate space.
   * Values ≤ 1.0 are treated as normalised [0,1].
   */
  scaleX(x) {
    if (x == null || isNaN(x)) return this.canvas.width / 2;
    return x > 1 ? (x / 800) * this.canvas.width : x * this.canvas.width;
  }

  scaleY(y) {
    if (y == null || isNaN(y)) return this.canvas.height / 2;
    return y > 1 ? (y / 600) * this.canvas.height : y * this.canvas.height;
  }

  // ── Keypoint smoothing ─────────────────────────────────────────────────────

  _smooth_kps(personIdx, kps) {
    if (!kps || kps.length === 0) return kps;
    if (!this.config.enableSmoothing) return kps;

    const prev = this._smooth.get(personIdx);
    if (!prev || prev.length !== kps.length) {
      this._smooth.set(personIdx, kps.map(k => ({ x: k.x, y: k.y })));
      return kps;
    }

    const a = this._alpha;
    const out = kps.map((kp, i) => ({
      ...kp,
      x: prev[i].x + (kp.x - prev[i].x) * a,
      y: prev[i].y + (kp.y - prev[i].y) * a,
    }));
    this._smooth.set(personIdx, out.map(k => ({ x: k.x, y: k.y })));
    return out;
  }

  // ── Drawing primitives ─────────────────────────────────────────────────────

  _drawSkeleton(kps, personIdx) {
    const ctx = this.ctx;
    ctx.save();
    ctx.lineWidth = this.config.skeletonWidth;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    SKELETON.forEach(([a, b], si) => {
      const kpA = kps[a], kpB = kps[b];
      if (!kpA || !kpB) return;

      const x1 = this.scaleX(kpA.x), y1 = this.scaleY(kpA.y);
      const x2 = this.scaleX(kpB.x), y2 = this.scaleY(kpB.y);

      if (isNaN(x1) || isNaN(y1) || isNaN(x2) || isNaN(y2)) return;

      const color = SEG_COLORS[si % SEG_COLORS.length];
      ctx.strokeStyle = color;
      ctx.shadowColor  = color;
      ctx.shadowBlur   = 8;
      ctx.globalAlpha  = 0.95;

      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    });

    ctx.restore();
  }

  _drawKeypoints(kps, personIdx) {
    const ctx = this.ctx;
    ctx.save();
    ctx.globalAlpha = 1.0;

    kps.forEach((kp, i) => {
      if (!kp) return;
      const x = this.scaleX(kp.x), y = this.scaleY(kp.y);
      if (isNaN(x) || isNaN(y)) return;

      const r = this.config.keypointRadius;
      const color = KP_COLORS[i % KP_COLORS.length];

      // Outer glow ring
      ctx.shadowColor = color;
      ctx.shadowBlur  = 10;
      ctx.fillStyle   = color;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();

      // White inner dot
      ctx.shadowBlur = 0;
      ctx.fillStyle  = '#ffffff';
      ctx.beginPath();
      ctx.arc(x, y, Math.max(1.5, r - 2.5), 0, Math.PI * 2);
      ctx.fill();
    });

    ctx.restore();
  }

  _drawHeatmap(kps, personIdx) {
    const ctx = this.ctx;
    const hue = personIdx * 60;
    ctx.save();

    kps.forEach((kp) => {
      if (!kp) return;
      const cx = this.scaleX(kp.x), cy = this.scaleY(kp.y);
      if (isNaN(cx) || isNaN(cy)) return;
      const r = 35;
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
      g.addColorStop(0,   `hsla(${hue},100%,60%,0.6)`);
      g.addColorStop(0.5, `hsla(${hue},100%,50%,0.25)`);
      g.addColorStop(1,   `hsla(${hue},100%,40%,0)`);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();
    });

    ctx.restore();
    // Overlay skeleton at reduced opacity
    ctx.save();
    ctx.globalAlpha = 0.4;
    this._drawSkeleton(kps, personIdx);
    ctx.restore();
  }

  _drawBBox(bbox, personIdx) {
    if (!bbox) return;
    const ctx = this.ctx;
    const x = this.scaleX(bbox.x), y = this.scaleY(bbox.y);
    const w = this.scaleX(bbox.x + (bbox.width  || 0)) - x;
    const h = this.scaleY(bbox.y + (bbox.height || 0)) - y;
    if (isNaN(x) || isNaN(y) || isNaN(w) || isNaN(h)) return;

    ctx.save();
    ctx.strokeStyle = PERSON_COLORS[personIdx % PERSON_COLORS.length];
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.7;
    ctx.strokeRect(x, y, w, h);
    ctx.restore();
  }

  _drawLabel(person, idx, kps) {
    const ctx = this.ctx;
    let lx = 12, ly = 20 + idx * 24;

    // Anchor to nose keypoint if available
    if (kps && kps[0]) {
      const nx = this.scaleX(kps[0].x), ny = this.scaleY(kps[0].y);
      if (!isNaN(nx) && !isNaN(ny) && nx > 0 && ny > 0) {
        lx = nx;
        ly = Math.max(14, ny - 14);
      }
    }

    const label = `P${idx + 1} ${Math.round((person.confidence || 0) * 100)}%`;
    ctx.save();
    ctx.font        = 'bold 12px monospace';
    ctx.shadowColor = '#000';
    ctx.shadowBlur  = 4;
    ctx.fillStyle   = PERSON_COLORS[idx % PERSON_COLORS.length];
    ctx.globalAlpha = 1.0;
    ctx.fillText(label, lx, ly);
    ctx.restore();
  }

  _drawZones(zoneSummary) {
    const ctx = this.ctx;
    ctx.save();
    ctx.font      = '11px monospace';
    ctx.fillStyle = '#ffd700';
    ctx.globalAlpha = 0.9;
    ctx.shadowColor = '#000';
    ctx.shadowBlur  = 3;
    Object.entries(zoneSummary).forEach(([zone, count], i) => {
      ctx.fillText(`Zone ${zone}: ${count} person(s)`, 10, 12 + i * 16);
    });
    ctx.restore();
  }

  _drawDebug(poseData) {
    const ctx = this.ctx;
    const lines = [
      `frame: ${poseData.frame_id || '—'}`,
      `persons: ${poseData.persons?.length || 0}`,
      `fps: ${this.performanceMetrics.averageFps.toFixed(1)}`,
      `render: ${this.performanceMetrics.renderTime.toFixed(1)}ms`,
      `canvas: ${this.canvas.width}×${this.canvas.height}`
    ];
    const bh = lines.length * 14 + 8;
    const bw = 160;
    const bx = this.canvas.width - bw - 6;
    const by = this.canvas.height - bh - 6;

    ctx.save();
    ctx.fillStyle   = 'rgba(0,0,0,0.65)';
    ctx.globalAlpha = 1;
    ctx.fillRect(bx, by, bw, bh);
    ctx.fillStyle = '#aaa';
    ctx.font      = '11px monospace';
    lines.forEach((l, i) => ctx.fillText(l, bx + 4, by + 4 + i * 14));
    ctx.restore();
  }

  _noData() {
    const ctx = this.ctx;
    ctx.save();
    ctx.font      = '15px monospace';
    ctx.fillStyle = '#556';
    ctx.textAlign = 'center';
    ctx.fillText('Waiting for pose data…', this.canvas.width / 2, this.canvas.height / 2);
    ctx.fillText('Click  ▶ Start  to connect', this.canvas.width / 2, this.canvas.height / 2 + 22);
    ctx.restore();
  }

  _updateFps(t0) {
    const now = performance.now();
    this.performanceMetrics.renderTime  = now - t0;
    this.performanceMetrics.frameCount++;
    if (this.performanceMetrics.lastFrameTime > 0) {
      const dt  = Math.max(now - this.performanceMetrics.lastFrameTime, 1);
      const fps = 1000 / dt;
      this.performanceMetrics.averageFps = this.performanceMetrics.averageFps === 0
        ? fps
        : this.performanceMetrics.averageFps * 0.9 + fps * 0.1;
    }
    this.performanceMetrics.lastFrameTime = now;
  }
}

// Kept for compatibility
export const PoseRendererUtils = {
  createDefaultConfig: () => ({
    mode: 'skeleton',
    showKeypoints: true,
    showSkeleton: true,
    showBoundingBox: false,
    showConfidence: true,
    showZones: true,
    showDebugInfo: false,
    keypointRadius: 5,
    skeletonWidth: 3,
    confidenceThreshold: 0.0,
    keypointConfidenceThreshold: -1,
    enableSmoothing: true,
    maxFps: 30
  }),
  validatePoseData: (d) => ({
    valid: d && Array.isArray(d.persons),
    errors: d && Array.isArray(d.persons) ? [] : ['persons must be an array']
  })
};
