const { spawn } = require('child_process');

const child = spawn('npx', ['-y', '@alanxchen/google-workspace-mcp'], {
  shell: true,
  env: process.env
});

process.stdin.pipe(child.stdin);

child.stdout.on('data', (data) => {
  const str = data.toString();
  // "Starting"으로 시작하는 안내 문구만 stderr로 보내고 나머지는 모두 stdout으로 통과
  if (str.includes('Starting Google Workspace') || str.includes('Google Workspace MCP Server is running')) {
    process.stderr.write('[Filtered Log] ' + str);
  } else {
    process.stdout.write(data);
  }
});

child.stderr.on('data', (data) => {
  process.stderr.write(data);
});

child.on('close', (code) => {
  process.exit(code);
});
