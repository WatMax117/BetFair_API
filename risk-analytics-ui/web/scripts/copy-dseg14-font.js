#!/usr/bin/env node
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const src = path.join(__dirname, '../node_modules/dseg/fonts/DSEG14-Modern/DSEG14Modern-BoldItalic.woff2')
const destDir = path.join(__dirname, '../public/fonts')
const dest = path.join(destDir, 'DSEG14Modern-BoldItalic.woff2')

if (fs.existsSync(src)) {
  fs.mkdirSync(destDir, { recursive: true })
  fs.copyFileSync(src, dest)
  console.log('Copied DSEG14Modern-BoldItalic.woff2 to public/fonts/')
} else {
  console.warn('DSEG14 font not found at', src, '- run npm install dseg first')
}
