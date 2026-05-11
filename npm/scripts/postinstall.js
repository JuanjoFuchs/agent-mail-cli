const fs = require('fs');
const https = require('https');
const path = require('path');

const REPO = 'JuanjoFuchs/agent-mail-cli';
const PACKAGE_VERSION = require('../package.json').version;

const PLATFORM_MAP = {
  'win32-x64': 'windows-x64.exe',
  'linux-x64': 'linux-x64',
  'darwin-x64': 'darwin-x64',
  'darwin-arm64': 'darwin-arm64'
};

function unsupportedPlatformError(platform, arch) {
  return {
    error: `Unsupported platform: ${platform}-${arch}`,
    supported_platforms: Object.keys(PLATFORM_MAP),
    hint: 'Install via pipx instead: pipx install agent-mail-cli'
  };
}

function resolveBinaryName(version, platform, arch) {
  const suffix = PLATFORM_MAP[`${platform}-${arch}`];
  if (!suffix) {
    return null;
  }
  return `agent-mail-${version}-${suffix}`;
}

async function main() {
  const platform = process.platform;
  const arch = process.arch;
  const binaryName = resolveBinaryName(PACKAGE_VERSION, platform, arch);

  if (!binaryName) {
    console.error(JSON.stringify(unsupportedPlatformError(platform, arch), null, 2));
    process.exit(1);
  }

  const url = `https://github.com/${REPO}/releases/download/v${PACKAGE_VERSION}/${binaryName}`;
  const binDir = path.join(__dirname, '..', 'bin');
  const binaryPath = path.join(binDir, binaryName);

  if (fs.existsSync(binaryPath)) {
    console.log(`agent-mail binary already exists at ${binaryPath}`);
    return;
  }

  console.log(`Downloading agent-mail ${PACKAGE_VERSION} for ${platform}-${arch}...`);
  console.log(`URL: ${url}`);

  try {
    await downloadFile(url, binaryPath);

    if (platform !== 'win32') {
      fs.chmodSync(binaryPath, 0o755);
    }

    console.log(`Successfully installed agent-mail to ${binaryPath}`);
  } catch (err) {
    console.error(JSON.stringify({
      error: `Failed to download agent-mail: ${err.message}`,
      hint: 'Install via pipx instead: pipx install agent-mail-cli'
    }, null, 2));
    process.exit(1);
  }
}

function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);

    const request = (currentUrl) => {
      https.get(currentUrl, (response) => {
        if ([301, 302, 303, 307, 308].includes(response.statusCode)) {
          response.resume();
          request(response.headers.location);
          return;
        }

        if (response.statusCode !== 200) {
          response.resume();
          file.close(() => {
            if (fs.existsSync(dest)) {
              fs.unlinkSync(dest);
            }
            reject(new Error(`HTTP ${response.statusCode}: ${response.statusMessage}`));
          });
          return;
        }

        const totalBytes = Number.parseInt(response.headers['content-length'], 10);
        let downloadedBytes = 0;

        response.on('data', (chunk) => {
          downloadedBytes += chunk.length;
          if (totalBytes) {
            const percent = Math.round((downloadedBytes / totalBytes) * 100);
            process.stdout.write(`\rDownloading: ${percent}%`);
          }
        });

        response.pipe(file);

        file.on('finish', () => {
          file.close();
          console.log('');
          resolve();
        });
      }).on('error', (err) => {
        file.close(() => {
          if (fs.existsSync(dest)) {
            fs.unlinkSync(dest);
          }
          reject(err);
        });
      });
    };

    request(url);
  });
}

if (require.main === module) {
  main().catch((err) => {
    console.error(JSON.stringify({ error: err.message }, null, 2));
    process.exit(1);
  });
}

module.exports = {
  PLATFORM_MAP,
  resolveBinaryName,
  unsupportedPlatformError
};
