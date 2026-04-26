/**
 * Python Utils - Funções para interagir com Python
 */

const { spawn, spawnSync } = require('child_process');
const path = require('path');

function resolvePythonExecutable() {
    if (process.env.PYTHON && process.env.PYTHON.trim()) {
        return process.env.PYTHON.trim();
    }

    if (process.platform === 'win32') {
        const whereResult = spawnSync('where', ['python'], { encoding: 'utf-8' });
        if (whereResult.status === 0 && whereResult.stdout) {
            const candidates = whereResult.stdout
                .split(/\r?\n/)
                .map((line) => line.trim())
                .filter(Boolean);
            const realPython = candidates.find(
                (candidate) => !candidate.toLowerCase().includes('windowsapps')
            );
            if (realPython) {
                return realPython;
            }
            if (candidates.length > 0) {
                return candidates[0];
            }
        }
        return 'python';
    }

    return 'python3';
}

/**
 * Verifica se Python está instalado
 */
async function checkPythonInstalled() {
    try {
        const pythonPath = resolvePythonExecutable();

        return new Promise((resolve) => {
            const proc = spawn(pythonPath, ['--version']);
            let output = '';

            proc.stdout.on('data', (data) => {
                output += data.toString();
            });

            proc.stderr.on('data', (data) => {
                output += data.toString();
            });

            proc.on('close', (code) => {
                if (code === 0) {
                    const version = output.trim().replace('Python ', '');
                    resolve({
                        installed: true,
                        version,
                        path: pythonPath
                    });
                } else {
                    resolve({ installed: false, version: null, path: null });
                }
            });

            proc.on('error', () => {
                resolve({ installed: false, version: null, path: null });
            });
        });
    } catch (error) {
        return { installed: false, version: null, path: null };
    }
}

/**
 * Executa um script Python
 */
async function runPythonScript(args, pythonPath = process.cwd()) {
    return new Promise((resolve, reject) => {
        try {
            const pythonExe = resolvePythonExecutable();

            const proc = spawn(pythonExe, args, {
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
async function runPythonScriptWithJSON(args, pythonPath = process.cwd()) {
    return new Promise((resolve, reject) => {
        try {
            const pythonExe = resolvePythonExecutable();

            let output = '';
            let errorOutput = '';

            const proc = spawn(pythonExe, args, {
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
