#!/usr/bin/env node

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const binDir = __dirname;
const ext = process.platform === 'win32' ? '.exe' : '';

const binaryName = fs.readdirSync(binDir).find((fileName) => (
  fileName.startsWith('agent-mail-')
    && fileName.endsWith(ext)
    && !fileName.endsWith('.js')
));

if (!binaryName) {
  console.error(JSON.stringify({
    error: 'agent-mail binary not found',
    hint: 'Try reinstalling: npm install -g agent-mail'
  }, null, 2));
  process.exit(1);
}

const binaryPath = path.join(binDir, binaryName);
const child = spawn(binaryPath, process.argv.slice(2), {
  stdio: 'inherit',
  windowsHide: true
});

child.on('error', (err) => {
  const payload = err.code === 'ENOENT'
    ? {
        error: 'agent-mail binary is not compatible with this system',
        hint: 'Install via pipx instead: pipx install agent-mail-cli'
      }
    : {
        error: `Error executing agent-mail: ${err.message}`
      };
  console.error(JSON.stringify(payload, null, 2));
  process.exit(1);
});

child.on('close', (code) => {
  process.exit(code || 0);
});
