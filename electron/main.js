const { app, BrowserWindow, Tray, Menu, nativeImage } = require('electron')
const path = require('node:path')

const IS_DEV = process.env.NODE_ENV !== 'production'
const DEV_RENDERER_URL = 'http://127.0.0.1:5173'

// Inline 16x16 monochrome circle — no asset files needed during dev
const TRAY_ICON_BASE64 = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAADCSURBVDiNpZMxDoMwDEUfVReGDhw5R+AAHIG5HZAYkDhIxpahHIAjsHVhyNChUod2KFIlJXaeLP/v2E+WJQAhhBBCCCGEkBBCCCGEEEIIIYQQQgghhBBCCCGEkBBCCCGEEEJICCGEEEIIIYQQQgghhBBCCCGEEEIIIYSQkO0BAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABICEIIIYQQQgghhBBCCCGEEEIIIf8BXkoGSsTjitMAAAAASUVORK5CYII='

let tray = null
let win = null

function createWindow() {
  win = new BrowserWindow({
    width: 420,
    height: 600,
    show: false,
    frame: false,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (IS_DEV) {
    win.loadURL(DEV_RENDERER_URL)
  } else {
    win.loadFile(path.join(__dirname, 'renderer', 'dist', 'index.html'))
  }

  win.on('blur', () => {
    if (!win.webContents.isDevToolsOpened()) win.hide()
  })

  win.on('close', (e) => {
    e.preventDefault()
    win.hide()
  })
}

function createTray() {
  const icon = nativeImage.createFromDataURL(TRAY_ICON_BASE64)
  icon.setTemplateImage(true)
  tray = new Tray(icon)
  tray.setToolTip('LifePilot')

  tray.on('click', (_event, bounds) => toggleWindow(bounds))
}

function toggleWindow(trayBounds) {
  if (win.isVisible()) {
    win.hide()
    return
  }
  const { width: wW } = win.getBounds()
  win.setPosition(
    Math.round(trayBounds.x - wW / 2 + trayBounds.width / 2),
    Math.round(trayBounds.y + trayBounds.height + 4)
  )
  win.show()
  win.focus()
}

app.whenReady().then(() => {
  if (app.dock) app.dock.hide()
  createWindow()
  createTray()
})

app.on('window-all-closed', (e) => {
  e.preventDefault() // keep alive in tray
})
