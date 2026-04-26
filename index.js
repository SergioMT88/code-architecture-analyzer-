const { join } = require('path');
const { checkPythonInstalled, runPythonScript, runPythonScriptWithJSON } = require('./lib/python-utils');

function buildScriptPath(scriptName) {
  return join(__dirname, 'scripts', scriptName);
}

async function analyze(file, options = {}) {
  const args = [buildScriptPath('orchestrator.py'), file];
  if (options.noRefactor) args.push('--no-refactor');
  if (options.dryRun) args.push('--dry-run');
  if (options.interactive) args.push('--interactive');
  return runPythonScript(args);
}

async function refactor(file, options = {}) {
  const args = [buildScriptPath('refactorer.py'), file];
  if (options.dryRun) args.push('--dry-run');
  return runPythonScript(args);
}

async function validate(file) {
  const args = [buildScriptPath('validator.py'), file];
  return runPythonScript(args);
}

module.exports = {
  analyze,
  refactor,
  validate,
  checkPythonInstalled,
  runPythonScript,
  runPythonScriptWithJSON,
};
