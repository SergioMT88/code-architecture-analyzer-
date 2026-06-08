#!/usr/bin/env node

/**
 * Code Architecture Analyzer - CLI Principal
 */

const { program } = require('commander');
const chalk = require('chalk');
const ora = require('ora');
const {
    checkPythonInstalled,
    runPythonScript,
    runPythonScriptWithJSON,
} = require('../lib/python-utils');
const { readFileSync, existsSync } = require('fs');
const { join } = require('path');

const packageJson = JSON.parse(
    readFileSync(join(__dirname, '../package.json'), 'utf-8')
);
const version = packageJson.version;

program
    .name('code-analyze')
    .description(chalk.cyan.bold('Code Architecture Analyzer v' + version))
    .version(version, '-v, --version')
    .usage('<arquivo.py> [opcoes]');

program
    .command('analyze <arquivo>')
    .alias('a')
    .description('Analise completa com refatoracao')
    .option('--no-refactor', 'Apenas analise, sem refatorar')
    .option('--dry-run', 'Mostra o que seria feito sem aplicar')
    .option('--interactive', 'Modo interativo: aceite/rejeite cada sugestao')
    .option('--quiet', 'Menos verbosidade no terminal')
    .option('--json', 'Saida JSON para integracoes com outros CLIs')
    .option('--html', 'Gera dashboard HTML visual')
    .option('--output <dir>', 'Diretorio de saida para relatorios')
    .option('--agent', 'Saida Markdown estruturada para agentes de IA (sem ANSI, sem HTML)')
    .option('--stream', 'Emite eventos NDJSON durante analise para agentes de IA')
    .action(async (arquivo, options) => {
        await executeAnalysis(arquivo, options);
    });

program
    .command('check <arquivo>')
    .alias('c')
    .description('Apenas analise (sem refatoracao)')
    .option('--json', 'Saida JSON para integracoes com outros CLIs')
    .option('--html', 'Gera dashboard HTML visual')
    .option('--quiet', 'Menos verbosidade no terminal')
    .option('--agent', 'Saida Markdown estruturada para agentes de IA (sem ANSI, sem HTML)')
    .option('--stream', 'Emite eventos NDJSON durante analise para agentes de IA')
    .action(async (arquivo, options) => {
        await executeAnalysis(arquivo, { noRefactor: true, ...options });
    });

program
    .command('agent <arquivo>')
    .alias('ag')
    .description('Gera prompt metacognitivo para agente de IA')
    .option('--json', 'Saida JSON para integracoes com outros CLIs')
    .option('--output <file>', 'Salvar prompt em arquivo')
    .option('--pipe <tool>', 'Enviar prompt para ferramenta de IA (claude, ollama, curl)')
    .option('--auto', 'Auto-detectar ferramenta de IA disponivel')
    .action(async (arquivo, options) => {
        await executeAgentReview(arquivo, options);
    });

program
    .command('refactor <arquivo>')
    .alias('r')
    .description('Apenas refatoracao')
    .option('--dry-run', 'Mostra diff sem aplicar alteracoes')
    .option('--quiet', 'Menos verbosidade no terminal')
    .option('--json', 'Saida JSON para integracoes com outros CLIs')
    .action(async (arquivo, options) => {
        await executeRefactoring(arquivo, options);
    });

program
    .command('validate <arquivo>')
    .alias('v')
    .description('Apenas validacao')
    .option('--quiet', 'Menos verbosidade no terminal')
    .option('--json', 'Saida JSON para integracoes com outros CLIs')
    .action(async (arquivo, options) => {
        await executeValidation(arquivo, options);
    });

program
    .command('init')
    .description('Cria .analyzer.json com config padrao no projeto')
    .action(async () => {
        await initConfig();
    });

program
    .command('info')
    .description('Informacoes do sistema')
    .action(async () => {
        await showSystemInfo();
    });

program
    .command('setup')
    .description('Instala dependencias Python (ruff, black, isort)')
    .action(async () => {
        await setupPython();
    });

program
    .command('manifest')
    .description('JSON: todas as capacidades da ferramenta para agentes de IA')
    .action(async () => {
        await executePassthrough('manifest', []);
    });

program
    .command('intent [subcommand] [args...]')
    .description('Gerenciar Intent Learning (list/show/reset/export/import)')
    .allowUnknownOption()
    .action(async (subcommand, args) => {
        await executePassthrough('intent', subcommand ? [subcommand, ...(args || [])] : []);
    });

program
    .command('health')
    .description('Relatorio de saude dos detectores')
    .action(async () => {
        await executePassthrough('health', []);
    });

program
    .command('config [subcommand] [args...]')
    .description('Configuracoes (ex: config lang pt|en)')
    .allowUnknownOption()
    .action(async (subcommand, args) => {
        await executePassthrough('config', subcommand ? [subcommand, ...(args || [])] : []);
    });

program
    .arguments('<arquivo>')
    .action(async (arquivo, options) => {
        if (!arquivo.endsWith('.py')) {
            console.error(chalk.red(`Arquivo deve ser Python (.py): ${arquivo}`));
            process.exit(1);
        }
        await executeAnalysis(arquivo, options || {});
    });

program.parse(process.argv);

if (process.argv.length === 2) {
    program.help();
}

async function executeAnalysis(arquivo, options) {
    const jsonMode = !!options.json;

    if (!jsonMode && !options.stream) {
        console.log(chalk.cyan.bold('\nCode Architecture Analyzer v' + version + '\n'));
    }

    if (!existsSync(arquivo)) {
        if (jsonMode) {
            console.log(JSON.stringify({
                success: false,
                command: 'analyze',
                file: arquivo,
                error: `Arquivo nao encontrado: ${arquivo}`,
            }, null, 2));
        } else {
            console.error(chalk.red(`Arquivo nao encontrado: ${arquivo}`));
            console.error(chalk.yellow('Uso: code-analyze analyze <seu_arquivo.py>'));
        }
        process.exit(1);
    }

    const pythonCheck = await checkPythonInstalled();
    if (!pythonCheck.installed) {
        if (jsonMode) {
            console.log(JSON.stringify({
                success: false,
                command: 'analyze',
                file: arquivo,
                error: 'Python nao encontrado',
            }, null, 2));
        } else {
            console.error(chalk.red('Python nao encontrado!'));
            console.error(chalk.yellow('Instale Python 3.8+: https://python.org'));
        }
        process.exit(1);
    }

    if (!jsonMode && !options.stream) {
        console.log(chalk.green(`Python ${pythonCheck.version} encontrado\n`));
    }

    const spinner = (jsonMode || options.stream) ? null : ora(chalk.blue('Analisando codigo...')).start();

    try {
        const scriptPath = join(__dirname, 'cli.py');
        const args = [scriptPath, 'analyze', arquivo];

        if (options.noRefactor) args.push('--no-refactor');
        if (options.dryRun) args.push('--dry-run');
        if (options.interactive) args.push('--interactive');
        if (options.quiet) args.push('--quiet');
        if (options.json) args.push('--json');
        if (options.html) args.push('--html');
        if (options.agent) args.push('--agent');
        if (options.stream) args.push('--stream');
        if (options.output) {
            args.push('--output');
            args.push(options.output);
        }

        if (spinner) spinner.stop();

        if (jsonMode) {
            const result = await runPythonScriptWithJSON(args, process.cwd(), pythonCheck);
            console.log(JSON.stringify(result, null, 2));
        } else if (options.stream) {
            await runPythonScript(args, process.cwd(), pythonCheck);
        } else {
            await runPythonScript(args, process.cwd(), pythonCheck);
            console.log(chalk.green('\nAnalise concluida!'));
        }

    } catch (error) {
        if (spinner) {
            spinner.fail(chalk.red(`Erro: ${error.message}`));
        } else {
            if (jsonMode) {
                console.log(JSON.stringify({
                    success: false,
                    command: 'analyze',
                    file: arquivo,
                    error: error.message,
                }, null, 2));
            } else {
                console.error(chalk.red(`Erro: ${error.message}`));
            }
        }
        process.exit(1);
    }
}

async function executeRefactoring(arquivo, options) {
    const jsonMode = !!options.json;

    if (!jsonMode) {
        console.log(chalk.cyan.bold('\nRefatoracao\n'));
    }

    if (!existsSync(arquivo)) {
        if (jsonMode) {
            console.log(JSON.stringify({
                success: false,
                command: 'refactor',
                file: arquivo,
                error: `Arquivo nao encontrado: ${arquivo}`,
            }, null, 2));
        } else {
            console.error(chalk.red(`Arquivo nao encontrado: ${arquivo}`));
        }
        process.exit(1);
    }

    const pythonCheck = await checkPythonInstalled();
    if (!pythonCheck.installed) {
        if (jsonMode) {
            console.log(JSON.stringify({
                success: false,
                command: 'refactor',
                file: arquivo,
                error: 'Python nao encontrado',
            }, null, 2));
        } else {
            console.error(chalk.red('Python nao encontrado!'));
        }
        process.exit(1);
    }

    const mode = options.dryRun ? ' [DRY-RUN]' : '';
    const spinner = jsonMode ? null : ora(chalk.blue(`Refatorando${mode}...`)).start();

    try {
        const scriptPath = join(__dirname, 'cli.py');
        const args = [scriptPath, 'refactor', arquivo];
        if (options.dryRun) args.push('--dry-run');
        if (options.quiet) args.push('--quiet');
        if (options.json) args.push('--json');

        if (spinner) spinner.stop();
        if (jsonMode) {
            const result = await runPythonScriptWithJSON(args, process.cwd(), pythonCheck);
            console.log(JSON.stringify(result, null, 2));
        } else {
            await runPythonScript(args, process.cwd(), pythonCheck);
            console.log(chalk.green('\nRefatoracao concluida!'));
        }
    } catch (error) {
        if (spinner) {
            spinner.fail(chalk.red(`Erro: ${error.message}`));
        } else {
            if (jsonMode) {
                console.log(JSON.stringify({
                    success: false,
                    command: 'refactor',
                    file: arquivo,
                    error: error.message,
                }, null, 2));
            } else {
                console.error(chalk.red(`Erro: ${error.message}`));
            }
        }
        process.exit(1);
    }
}

async function executeValidation(arquivo, options) {
    const jsonMode = !!options.json;

    if (!jsonMode) {
        console.log(chalk.cyan.bold('\nValidacao\n'));
    }

    if (!existsSync(arquivo)) {
        if (jsonMode) {
            console.log(JSON.stringify({
                success: false,
                command: 'validate',
                file: arquivo,
                error: `Arquivo nao encontrado: ${arquivo}`,
            }, null, 2));
        } else {
            console.error(chalk.red(`Arquivo nao encontrado: ${arquivo}`));
        }
        process.exit(1);
    }

    const pythonCheck = await checkPythonInstalled();
    if (!pythonCheck.installed) {
        if (jsonMode) {
            console.log(JSON.stringify({
                success: false,
                command: 'validate',
                file: arquivo,
                error: 'Python nao encontrado',
            }, null, 2));
        } else {
            console.error(chalk.red('Python nao encontrado!'));
        }
        process.exit(1);
    }

    const spinner = jsonMode ? null : ora(chalk.blue('Validando...')).start();
    try {
        const scriptPath = join(__dirname, 'cli.py');
        if (options.quiet && !jsonMode) process.stdout.write(chalk.gray('Modo: QUIET\n'));
        const args = [scriptPath, 'validate', arquivo];
        if (options.quiet) args.push('--quiet');
        if (options.json) args.push('--json');
        if (spinner) spinner.stop();
        if (jsonMode) {
            const result = await runPythonScriptWithJSON(args, process.cwd(), pythonCheck);
            console.log(JSON.stringify(result, null, 2));
        } else {
            await runPythonScript(args, process.cwd(), pythonCheck);
            console.log(chalk.green('\nValidacao concluida!'));
        }
    } catch (error) {
        if (spinner) {
            spinner.fail(chalk.red(`Erro: ${error.message}`));
        } else {
            if (jsonMode) {
                console.log(JSON.stringify({
                    success: false,
                    command: 'validate',
                    file: arquivo,
                    error: error.message,
                }, null, 2));
            } else {
                console.error(chalk.red(`Erro: ${error.message}`));
            }
        }
        process.exit(1);
    }
}

async function executeAgentReview(arquivo, options) {
    const jsonMode = !!options.json;

    if (!jsonMode) {
        console.log(chalk.cyan.bold('\n🧠 Agent Review — Metacognitive Analysis\n'));
    }

    if (!existsSync(arquivo)) {
        if (jsonMode) {
            console.log(JSON.stringify({
                success: false,
                command: 'agent',
                file: arquivo,
                error: `Arquivo nao encontrado: ${arquivo}`,
            }, null, 2));
        } else {
            console.error(chalk.red(`Arquivo nao encontrado: ${arquivo}`));
        }
        process.exit(1);
    }

    const pythonCheck = await checkPythonInstalled();
    if (!pythonCheck.installed) {
        if (jsonMode) {
            console.log(JSON.stringify({
                success: false,
                command: 'agent',
                file: arquivo,
                error: 'Python nao encontrado',
            }, null, 2));
        } else {
            console.error(chalk.red('Python nao encontrado!'));
        }
        process.exit(1);
    }

    const spinner = jsonMode ? null : ora(chalk.blue('Gerando prompt para agente...')).start();
    try {
        const scriptPath = join(__dirname, 'cli.py');
        const args = [scriptPath, 'agent', arquivo];
        if (options.json) args.push('--json');
        if (options.output) args.push('--output', options.output);
        if (options.pipe) args.push('--pipe', options.pipe);
        if (options.auto) args.push('--auto');
        
        if (spinner) spinner.stop();
        if (jsonMode) {
            const result = await runPythonScriptWithJSON(args, process.cwd(), pythonCheck);
            console.log(JSON.stringify(result, null, 2));
        } else {
            await runPythonScript(args, process.cwd(), pythonCheck);
            if (!options.output && !options.pipe && !options.auto) {
                console.log(chalk.green('\n✅ Prompt gerado com sucesso!'));
                console.log(chalk.gray('Copie o prompt acima e use no seu agente de IA.'));
                console.log(chalk.gray('Ou use: --output <file> para salvar, --auto para enviar automaticamente'));
            }
        }
    } catch (error) {
        if (spinner) {
            spinner.fail(chalk.red(`Erro: ${error.message}`));
        } else {
            if (jsonMode) {
                console.log(JSON.stringify({
                    success: false,
                    command: 'agent',
                    file: arquivo,
                    error: error.message,
                }, null, 2));
            } else {
                console.error(chalk.red(`Erro: ${error.message}`));
            }
        }
        process.exit(1);
    }
}

async function initConfig() {
    const configPath = join(process.cwd(), '.analyzer.json');

    if (existsSync(configPath)) {
        console.log(chalk.yellow('.analyzer.json ja existe neste diretorio.'));
        return;
    }

    const defaultConfig = {
        "max_methods_per_class": 10,
        "max_lines_per_class": 200,
        "max_complexity": 10,
        "max_imports": 20,
        "min_comment_ratio": 10,
        "architecture_style": "generic",
        "ignore_criteria": [],
        "output_dir": null,
        "dry_run": false,
        "interactive": false,
        "_comment": "Personalize este arquivo com as regras do seu projeto"
    };

    require('fs').writeFileSync(
        configPath,
        JSON.stringify(defaultConfig, null, 2),
        'utf-8'
    );

    console.log(chalk.green(`.analyzer.json criado em: ${configPath}`));
    console.log(chalk.gray('Edite o arquivo para personalizar as regras do seu projeto.'));
}

async function showSystemInfo() {
    console.log(chalk.cyan.bold('\nInformacoes do Sistema\n'));

    const pythonCheck = await checkPythonInstalled();

    console.log(chalk.bold('Node.js:'));
    console.log(`  Versao: ${process.version}`);

    console.log(chalk.bold('\nPython:'));
    if (pythonCheck.installed) {
        console.log(`  Status: ${chalk.green('Instalado')}`);
        console.log(`  Versao: ${pythonCheck.version}`);
    } else {
        console.log(`  Status: ${chalk.red('Nao encontrado')}`);
    }

    const configExists = existsSync(join(process.cwd(), '.analyzer.json'));
    console.log(chalk.bold('\nConfig do Projeto:'));
    console.log(`  .analyzer.json: ${configExists
        ? chalk.green('Encontrado')
        : chalk.gray('Nao encontrado (use: code-analyze init)')
    }`);

    console.log(chalk.bold('\nSkill:'));
    console.log(`  Versao: ${version}\n`);
}

async function executePassthrough(command, args) {
    const pythonCheck = await checkPythonInstalled();
    if (!pythonCheck.installed) {
        console.error(chalk.red('Python nao encontrado!'));
        process.exit(1);
    }
    try {
        const scriptPath = join(__dirname, 'cli.py');
        await runPythonScript([scriptPath, command, ...args], process.cwd(), pythonCheck);
    } catch (error) {
        console.error(chalk.red(`Erro: ${error.message}`));
        process.exit(1);
    }
}

async function setupPython() {
    console.log(chalk.cyan.bold('\nSetup de Dependencias Python\n'));

    const pythonCheck = await checkPythonInstalled();
    if (!pythonCheck.installed) {
        console.error(chalk.red('Python nao encontrado.'));
        console.log(chalk.yellow('Instale Python 3.8+: https://python.org'));
        process.exit(1);
    }

    console.log(chalk.green(`Python ${pythonCheck.version} encontrado\n`));

    const deps = ['ruff', 'black', 'isort', 'pytest'];
    const pip = process.platform === 'win32' ? 'pip' : 'pip3';
    const { spawn } = require('child_process');

    for (const dep of deps) {
        const spinner = ora(chalk.blue(`Instalando ${dep}...`)).start();
        try {
            await new Promise((resolve, reject) => {
                const proc = spawn(pip, ['install', '--quiet', dep], {
                    stdio: 'pipe',
                    shell: true,
                });
                proc.on('close', (code) => {
                    if (code === 0) resolve();
                    else reject(new Error(`Falha: ${dep}`));
                });
            });
            spinner.succeed(chalk.green(`${dep} instalado`));
        } catch {
            spinner.warn(chalk.yellow(`${dep} - verifique manualmente`));
        }
    }

    console.log(chalk.green('\nSetup concluido!\n'));
    console.log(chalk.gray('Ferramentas instaladas: ruff, black, isort, pytest'));
    console.log(chalk.gray('Essas ferramentas melhoram a qualidade da analise.\n'));
}
