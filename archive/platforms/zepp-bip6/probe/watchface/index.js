import { createWidget, widget } from '@zos/ui'
import { HeartRate, Time, Compass, Geolocation } from '@zos/sensor'
import { LocalStorage } from '@zos/storage'
import { getScene, SCENE_AOD } from '@zos/app'
import { setPageBrightTime } from '@zos/display'

const W = 390
const H = 450
function L(k, v) { console.log('ZT ' + k + '=' + v) }
function E(k, e) { console.log('ZT ' + k + '=ERR ' + (e && e.message ? e.message : e)) }

let canvas = null
let time = null
let hr = null
let tick = 0
let hist = []
let lastMs = -1

// tiny LCG so frames are reproducible
let seed = 1
function rnd() { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff }

const MOSS = [0x1b5e20, 0x2e7d32, 0x388e3c, 0x43a047, 0x66bb6a, 0x9ccc65, 0xc0ca33, 0x827717]

function draw(nBlobs) {
  const t0 = Date.now()
  canvas.clear({ x: 0, y: 0, w: W, h: H })
  seed = 777 + tick
  // moss: irregular filled polygons
  for (let i = 0; i < nBlobs; i++) {
    const cx = 40 + rnd() * (W - 80)
    const cy = 90 + rnd() * (H - 200)
    const r = 6 + rnd() * 18
    const pts = []
    const n = 5 + ((rnd() * 4) | 0)
    for (let k = 0; k < n; k++) {
      const a = (k / n) * 6.2832
      const rr = r * (0.6 + rnd() * 0.6)
      pts.push({ x: (cx + Math.cos(a) * rr) | 0, y: (cy + Math.sin(a) * rr) | 0 })
    }
    canvas.drawPoly({ data_array: pts, color: MOSS[(rnd() * MOSS.length) | 0] })
  }
  // spores: single pixels
  for (let i = 0; i < 300; i++) {
    canvas.drawPixel({ x: (rnd() * W) | 0, y: (rnd() * H) | 0, color: 0xffaa00 })
  }
  // sun arc + marker
  canvas.strokeArc({ x: 15, y: 15, w: W - 30, h: H - 30, start_angle: 200, end_angle: 340, color: 0xffaa00, line_width: 3 })
  canvas.drawCircle({ center_x: 300, center_y: 60, radius: 10, color: 0xffdd55 })
  // HR sparkline (last 180 minutes)
  const n = hist.length
  if (n > 1) {
    const x0 = 40, y0 = H - 40, sw = W - 80, sh = 50
    let prev = null
    for (let i = 0; i < n; i++) {
      const v = hist[i]
      if (!v) { prev = null; continue }
      const x = x0 + ((i * sw) / (n - 1)) | 0
      const y = y0 - (((v - 40) * sh) / 140) | 0
      if (prev) canvas.drawLine({ x1: prev.x, y1: prev.y, x2: x, y2: y, color: 0xff5555, line_width: 2 })
      prev = { x, y }
    }
  }
  canvas.drawText({ x: 20, y: 20, text: 'tick ' + tick + '  ' + lastMs + 'ms', text_size: 22, color: 0xffffff })
  return Date.now() - t0
}

function refreshHr() {
  try {
    const today = hr.getToday()
    L('hr.getToday.len', today ? today.length : 'null')
    hist = today ? today.slice(-180) : []
    let nz = 0
    for (let i = 0; i < hist.length; i++) if (hist[i]) nz++
    L('hr.hist.nonzero', nz)
    L('hr.getLast', hr.getLast())
  } catch (e) { E('hr.getToday', e) }
}

function frame(label) {
  tick++
  try { L('scene', getScene() + (getScene() === SCENE_AOD ? ' (AOD)' : '')) } catch (e) { E('scene', e) }
  refreshHr()
  try {
    lastMs = draw(150)
    L(label + '.draw150.ms', lastMs)
  } catch (e) { E(label + '.draw', e) }
}

WatchFace({
  onInit() { L('onInit', 1) },

  build() {
    L('build', 1)
    try { L('brightTime', JSON.stringify(setPageBrightTime({ brightTime: 300000 }))) } catch (e) { E('brightTime', e) }
    try { L('hmUI.show_level', typeof hmUI !== 'undefined' ? JSON.stringify(hmUI.show_level) : 'no hmUI') } catch (e) { E('show_level', e) }

    try {
      canvas = createWidget(widget.CANVAS, { x: 0, y: 0, w: W, h: H, show_level: 1 | 2 | 4 | 8 })
      L('canvas.create', canvas ? 'ok' : 'null')
    } catch (e) { E('canvas.create', e) }

    try { hr = new HeartRate(); L('hr.new', 'ok') } catch (e) { E('hr.new', e) }

    try {
      const ls = new LocalStorage()
      const c = (ls.getItem('boots', 0) | 0) + 1
      ls.setItem('boots', c)
      L('storage.boots', c)
    } catch (e) { E('storage', e) }

    try {
      const cp = new Compass(); cp.start()
      L('compass', cp.getStatus() + ' ' + cp.getDirectionAngle())
    } catch (e) { E('compass', e) }

    try {
      const g = new Geolocation(); g.start()
      L('geo', g.getStatus() + ' ' + g.getLatitude() + ',' + g.getLongitude())
    } catch (e) { E('geo', e) }

    if (canvas) {
      frame('build')
      // CPU budget probe: time progressively heavier frames once
      const sizes = [300, 600, 1200]
      for (let i = 0; i < sizes.length; i++) {
        try { L('stress.draw' + sizes[i] + '.ms', draw(sizes[i])) } catch (e) { E('stress.' + sizes[i], e); break }
      }
      lastMs = draw(150)
    }

    try {
      time = new Time()
      time.onPerMinute(() => frame('minute'))
      L('time.onPerMinute', 'registered')
    } catch (e) { E('time.onPerMinute', e) }
  },

  onResume() { L('onResume', getScene()); if (canvas) frame('resume') },
  onPause() { L('onPause', 1) },
  onDestroy() { L('onDestroy', 1) },
})
