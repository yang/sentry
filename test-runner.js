const fs = require('node:fs/promises');
const exec = require('node:child_process').execSync;

async function runTestSuite(dc) {
  if (dc.indexOf('__') === 0) {
    return null;
  }

  console.log(`\n\nRunning test suite on: ${dc}\n\n`);
  const result = {success: false, input: `tests/sentry/${dc}`};
  try {
    exec(`pytest -n 2 tests/sentry/${dc}`, {
      timeout: 180 * 1000,
    });
    console.error('    ✅');
    result.success = true;
  } catch (err) {
    console.error('    ❌');
    if (err.stdout) {
      result.stdout = err.stdout.toString();
    }
  }
  return result;
}

function logResults(results) {
  const success = results.filter(r => r.success);
  const failures = results.filter(r => !r.success);

  for (const f of failures) {
    console.log(`    ❌ ${f.input}:\n${f.stdout}`);
  }

  for (const s of success) {
    console.log(`    ✅ ${s.input}`);
  }

  for (const f of failures) {
    console.log(`    ❌ ${f.input}`);
  }
}

async function run() {
  const results = [];
  const dirContents = await fs.readdir('./tests/sentry/');
  for (const dc of dirContents) {
    const r = await runTestSuite(dc);
    if (r) {
      results.push(r);
    }
  }
  logResults(results);
}

run();
