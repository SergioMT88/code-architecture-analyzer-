#!/usr/bin/env node

/**
 * Code Architecture Analyzer v2.0 - CLI Principal
 */

const { program } = require('commander');
const chalk = require('chalk');
const ora = require('ora');
const { checkPythonInstalled, runPythonScript } = require('../lib/python-utils');
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
    .option('--output <dir>', 'Diretorio de saida para relatorios')
    .action(async (arquivo, options) => {
        await executeAnalysis(arquivo, options);
    });

program
    .command('check <arquivo>')
    .alias('c')
    .description('Apenas analise (sem refatoracao)')
    .action(async (arquivo) => {
        await executeAnalysis(arquivo, { noRefactor: true });
    });

program
    .command('refactor <arquivo>')
    .alias('r')
    .description('Apenas refatoracao')
    .option('--dry-run', 'Mostra diff sem aplicar alteracoes')
    .action(async (arquivo, options) => {
        await executeRefactoring(arquivo, options);
    });

program
    .command('validate <arquivo>')
    .alias('v')
    .description('Apenas validacao')
    .action(async (arquivo) => {
        await executeValidation(arquivo);
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
    .description('Instala dependencias Python (pylint, ruff, black, isort)')
    .action(async () => {
        await setupPython();
    });

program
    .arguments('<arquivo>')
    .action(async (arquivo) => {
        if (!arquivo.endsWith('.py')) {
            console.error(chalk.red(`Arquivo deve ser Python (.py): ${arquivo}`));
            process.exit(1);
        }
        await executeAnalysis(arquivo, {});
    });

program.parse(process.argv);

if (process.argv.length === 2) {
    program.help();
}

async function executeAnalysis(arquivo, options) {
    console.log(chalk.cyan.bold('\nCode Architecture Analyzer v' + version + '\n'));

    if (!existsSync(arquivo)) {
        console.error(chalk.red(`Arquivo nao encontrado: ${arquivo}`));
        console.error(chalk.yellow('Uso: code-analyze analyze <seu_arquivo.py>'));
        process.exit(1);
    }

    const pythonCheck = await checkPythonInstalled();
    if (!pythonCheck.installed) {
        console.error(chalk.red('Python nao encontrado!'));
        console.error(chalk.yellow('Instale Python 3.8+: https://python.org'));
        process.exit(1);
    }

    console.log(chalk.green(`Python ${pythonCheck.version} encontrado\n`));

    const spinner = ora(chalk.blue('Analisando codigo...')).start();

    try {
        const scriptPath = join(__dirname, '..', 'scripts', 'orchestrator.py');
        const args = [scriptPath, arquivo];

        if (options.noRefactor) args.push('--no-refactor');
        if (options.dryRun) args.push('--dry-run');
        if (options.interactive) args.push('--interactive');

        spinner.stop();

        await runPythonScript(args);

        console.log(chalk.green('\nAnalise concluida!'));

    } catch (error) {
        spinner.fail(chalk.red(`Erro: ${error.message}`));
        process.exit(1);
    }
}

async function executeRefactoring(arquivo, options) {
    console.log(chalk.cyan.bold('\nRefatoracao\n'));

    if (!existsSync(arquivo)) {
        console.error(chalk.red(`Arquivo nao encontrado: ${arquivo}`));
        process.exit(1);
    }

    const pythonCheck = await checkPythonInstalled();
    if (!pythonCheck.installed) {
        console.error(chalk.red('Python nao encontrado!'));
        process.exit(1);
    }

    const mode = options.dryRun ? ' [DRY-RUN]' : '';
    const spinner = ora(chalk.blue(`Refatorando${mode}...`)).start();

    try {
        const scriptPath = join(__dirname, '..', 'scripts', 'refactorer.py');
        const args = [scriptPath, arquivo];
        if (options.dryRun) args.push('--dry-run');

        spinner.stop();
        await runPythonScript(args);
        console.log(chalk.green('\nRefatoracao concluida!'));
    } catch (error) {
        spinner.fail(chalk.red(`Erro: ${error.message}`));
        process.exit(1);
    }
}

async function executeValidation(arquivo) {
    console.log(chalk.cyan.bold('\nValidacao\n'));

    if (!existsSync(arquivo)) {
        console.error(chalk.red(`Arquivo nao encontrado: ${arquivo}`));
        process.exit(1);
    }

    const pythonCheck = await checkPythonInstalled();
    if (!pythonCheck.installed) {
        console.error(chalk.red('Python nao encontrado!'));
        process.exit(1);
    }

    const spinner = ora(chalk.blue('Validando...')).start();
    try {
        const scriptPath = join(__dirname, '..', 'scripts', 'validator.py');
        spinner.stop();
        await runPythonScript([scriptPath, arquivo]);
        console.log(chalk.green('\nValidacao concluida!'));
    } catch (error) {
        spinner.fail(chalk.red(`Erro: ${error.message}`));
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

async function setupPython() {
    console.log(chalk.cyan.bold('\nSetup de Dependencias Python\n'));

    const pythonCheck = await checkPythonInstalled();
    if (!pythonCheck.installed) {
        console.error(chalk.red('Python nao encontrado.'));
        console.log(chalk.yellow('Instale Python 3.8+: https://python.org'));
        process.exit(1);
    }

    console.log(chalk.green(`Python ${pythonCheck.version} encontrado\n`));

    const deps = ['pylint', 'ruff', 'black', 'isort', 'pytest'];
    const pip = process.platform === 'win32' ? 'pip' : 'pip3';
    const { spawn } = require('child_process');

    for (const dep of deps) {
        const spinner = ora(chalk.blue(`Instalando ${dep}...`)).start();
        try {
            await new Promise((resolve, reject) => {
                const proc = spawn(pip, ['install', '--quiet', dep], { stdio: 'pipe' });
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
    console.log(chalk.gray('Ferramentas instaladas: pylint, ruff, black, isort, pytest'));
    console.log(chalk.gray('Essas ferramentas melhoram a qualidade da analise.\n'));
}
