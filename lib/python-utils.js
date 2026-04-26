/**
 * Python Utils - Funções para interagir com Python
 */

const { existsSync, readdirSync } = require('fs');
const { spawn, spawnSync } = require('child_process');

function buildPythonCandidates() {
    const candidates = [];

    if (process.env.PYTHON && process.env.PYTHON.trim()) {
        candidates.push({ command: process.env.PYTHON.trim(), argsPrefix: [] });
    }

    if (process.platform === 'win32') {
        const roots = [
            process.env.LOCALAPPDATA && `${process.env.LOCALAPPDATA}\\Programs\\Python`,
            process.env.ProgramFiles && `${process.env.ProgramFiles}\\Python`,
            process.env['ProgramFiles(x86)'] && `${process.env['ProgramFiles(x86)']}\\Python`,
        ].filter(Boolean);
        const versions = ['313', '312', '311', '310', '39', '38'];

        for (const root of roots) {
            for (const version of versions) {
                const direct = `${root}\\Python${version}\\python.exe`;
                const legacy = `${root}\\Python-${version}\\python.exe`;
                if (existsSync(direct)) {
                    candidates.push({ command: direct, argsPrefix: [] });
                }
                if (existsSync(legacy)) {
                    candidates.push({ command: legacy, argsPrefix: [] });
                }
            }
        }

        const pyLauncher = `${process.env.SystemRoot || 'C:\\Windows'}\\py.exe`;
        if (existsSync(pyLauncher)) {
            candidates.push({ command: pyLauncher, argsPrefix: ['-3'] });
        }

        const whereResult = spawnSync('where.exe', ['python'], { encoding: 'utf-8' });
        if (whereResult.status === 0 && whereResult.stdout) {
            const whereCandidates = whereResult.stdout
                .split(/\r?\n/)
                .map((line) => line.trim())
                .filter(Boolean)
                .filter((candidate) => !candidate.toLowerCase().includes('windowsapps'))
                .map((command) => ({ command, argsPrefix: [] }));
            candidates.push(...whereCandidates);
        }

        candidates.push(
            { command: 'py', argsPrefix: ['-3'] },
            { command: 'python', argsPrefix: [] }
        );

        return candidates;
    }

    candidates.push({ command: 'python3', argsPrefix: [] }, { command: 'python', argsPrefix: [] });
    return candidates;
}

/**
 * Verifica se Python está instalado
 */
async function checkPythonInstalled() {
    try {
        for (const candidate of buildPythonCandidates()) {
            const command = candidate.command;
            const args = [...(candidate.argsPrefix || []), '--version'];
            const result = spawnSync(command, args, { encoding: 'utf-8' });
            if (result.status === 0) {
                const output = `${result.stdout || ''}${result.stderr || ''}`.trim();
                const version = output.replace(/^Python\s+/i, '');
                return {
                    installed: true,
                    version,
                    path: command,
                    argsPrefix: candidate.argsPrefix || [],
                };
            }
        }
        return { installed: false, version: null, path: null, argsPrefix: [] };
    } catch (error) {
        return { installed: false, version: null, path: null, argsPrefix: [] };
    }
}

/**
 * Executa um script Python
 */
async function runPythonScript(args, pythonPath = process.cwd(), pythonInfo = null) {
    return new Promise((resolve, reject) => {
        try {
            const fallbackCandidate = buildPythonCandidates()[0] || { command: 'python', argsPrefix: [] };
            const pythonExe = pythonInfo || {};
            const command = pythonExe.path || pythonExe.command || pythonExe.executable || fallbackCandidate.command;
            const argsPrefix = pythonExe.argsPrefix || fallbackCandidate.argsPrefix || [];
            const executable = command;

            const proc = spawn(executable, [...argsPrefix, ...args], {
                cwd: pythonPath,
                stdio: 'inherit',
            });

            proc.on('close', (code) => {
                if (code === 0) {
                    resolve();
                } else {
                    reject(new Error(`Python exited with code ${code}`));
                }
            });

            proc.on('error', (error) => {
                reject(new Error(`Failed to run Python: ${error.message}`));
            });

        } catch (error) {
            reject(error);
        }
    });
}

/**
 * Executa um script Python e retorna JSON
 */
async function runPythonScriptWithJSON(args, pythonPath = process.cwd(), pythonInfo = null) {
    return new Promise((resolve, reject) => {
        try {
            const fallbackCandidate = buildPythonCandidates()[0] || { command: 'python', argsPrefix: [] };
            const pythonExe = pythonInfo || {};
            const command = pythonExe.path || pythonExe.command || pythonExe.executable || fallbackCandidate.command;
            const argsPrefix = pythonExe.argsPrefix || fallbackCandidate.argsPrefix || [];
            const executable = command;

            let output = '';
            let errorOutput = '';

            const proc = spawn(executable, [...argsPrefix, ...args], {
                cwd: pythonPath,
                stdio: ['pipe', 'pipe', 'pipe'],
            });

            proc.stdout.on('data', (data) => {
                output += data.toString();
            });

            proc.stderr.on('data', (data) => {
                errorOutput += data.toString();
            });

            proc.on('close', (code) => {
                if (code === 0) {
                    try {
                        const result = JSON.parse(output);
                        resolve(result);
                    } catch (parseError) {
                        reject(new Error(`Failed to parse Python output: ${parseError.message}`));
                    }
                } else {
                    reject(new Error(`Python exited with code ${code}: ${errorOutput}`));
                }
            });

            proc.on('error', (error) => {
                reject(new Error(`Failed to run Python: ${error.message}`));
            });

        } catch (error) {
            reject(error);
        }
    });
}

module.exports = {
    checkPythonInstalled,
    runPythonScript,
    runPythonScriptWithJSON
};
