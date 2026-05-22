const { join } = require('path');
const { runPythonScript } = require('./lib/python-utils');

async function analyze(file, options = {}) {
  const args = ['-m', 'code_analyzer.orchestrator', file];
  if (options.noRefactor) args.push('--no-refactor');
  if (options.dryRun) args.push('--dry-run');
  if (options.interactive) args.push('--interactive');
  return runPythonScript(args, join(__dirname, 'src'));
}

async function refactor(file, options = {}) {
  const args = ['-m', 'code_analyzer.refactorer', file];
  if (options.dryRun) args.push('--dry-run');
  return runPythonScript(args, join(__dirname, 'src'));
}

async function validate(file) {
  const args = ['-m', 'code_analyzer.validator', file];
  return runPythonScript(args, join(__dirname, 'src'));
}

module.exports = {
  analyze,
  refactor,
  validate,
};
