// usage: node install.js <device.zip> <appId>
const WebSocket = require(process.env.WS_PATH)
const fs = require('fs')
const [zip, appIdStr] = process.argv.slice(2)
const hex = Number(appIdStr).toString(16).toUpperCase().padStart(8, '0')
const file = fs.readFileSync(zip)
const ws = new WebSocket('ws://localhost:7833/SIMULATOR')
ws.on('message', (m) => console.log('RECV', String(m).slice(0, 300)))
ws.on('error', (e) => { console.log('ERR', e.message); process.exit(1) })
ws.on('open', () => {
  console.log('open; installing', hex, file.length, 'bytes')
  const head = Buffer.from(`{"method":"Project","type":"install","appid":"${hex}","length":${file.length},"file":"`)
  ws.send(Buffer.concat([head, file, Buffer.from('"}')]), () => {
    setTimeout(() => ws.send(JSON.stringify({ method: 'ChangeWatchFace', appid: hex })), 1500)
    setTimeout(() => process.exit(0), 6000)
  })
})
