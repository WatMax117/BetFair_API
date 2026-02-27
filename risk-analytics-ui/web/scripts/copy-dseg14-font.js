#!/usr/bin/env node
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const destDir = path.join(__dirname, '../public/fonts')

const fonts = [
  {
    src: path.join(__dirname, '../node_modules/dseg/fonts/DSEG14-Modern/DSEG14Modern-BoldItalic.woff2'),
    dest: 'DSEG14Modern-BoldItalic.woff2',
    name: 'DSEG14',
  },
  {
    src: path.join(__dirname, '../node_modules/dseg/fonts/DSEG7-Modern-MINI/DSEG7ModernMini-BoldItalic.woff2'),
    dest: 'DSEG7ModernMini-BoldItalic.woff2',
    name: 'DSEG7 Modern Mini',
    altSrc: path.join(__dirname, '../node_modules/dseg/fonts/DSEG7-Modern-Mini/DSEG7ModernMini-BoldItalic.woff2'),
  },
]

fs.mkdirSync(destDir, { recursive: true })
for (const entry of fonts) {
  const src = entry.altSrc && !fs.existsSync(entry.src) ? entry.altSrc : entry.src
  const dest = path.join(destDir, entry.dest)
  const name = entry.name
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, dest)
    console.log('Copied', entry.dest, 'to public/fonts/')
  } else {
    console.warn(name, 'font not found - run npm install dseg first')
  }
}
