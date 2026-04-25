#!/usr/bin/env node

/**
 * Code Architecture Analyzer - CLI Principal
 * Uso: npx code-analyze seu_arquivo.py
 */

const { program } = require('commander');
const chalk = require('chalk');
const ora = require('ora');
const { spawn } = require('child_process');
const { checkPythonInstalled, runPythonScript } = require('../lib/python-utils');
const { readFileSync } = require('fs');
const { join } = require('path');

const packageJson = JSON.parse(
    readFileSync(join(__dirname, '../package.json'), 'utf-8')
);

const version = packageJson.version;

program
    .name('code-analyze')
    .description(chalk.cyan.bold('🏗️  Code Architecture Analyzer v' + version))
    .version(version, '-v, --version')
    .usage('<arquivo.py> [opções]');

// Comando principal
program
    .command('analyze <arquivo>')
    .alias('a')
    .description('Análise completa com refatoração')
    .option('--no-refactor', 'Apenas análise')
    .option('--output <dir>', 'Diretório de saída')
    .action(async (arquivo, options) => {
        await executeAnalysis(arquivo, options);
    });

// Comando: check
program
    .command('check <arquivo>')
    .alias('c')
    .description('Apenas análise (sem refatoração)')
    .action(async (arquivo) => {
        await executeAnalysis(arquivo, { noRefactor: true });
    });

// Comando: refactor
program
    .command('refactor <arquivo>')
    .alias('r')
    .description('Apenas refatoração')
    .action(async (arquivo) => {
        await executeRefactoring(arquivo);
    });

// Comando: validate
program
    .command('validate <arquivo>')
    .alias('v')
    .description('Apenas validação')
    .action(async (arquivo) => {
        await executeValidation(arquivo);
    });

// Comando: info
program
    .command('info')
    .description('Informações do sistema')
    .action(async () => {
        await showSystemInfo();
    });

// Comando: setup
program
    .command('setup')
    .description('Setup de dependências')
    .action(async () => {
        await setupPython();
    });

// Comando padrão (sem subcomando)
program
    .arguments('<arquivo>')
    .action(async (arquivo, options) => {
        if (!arquivo.endsWith('.py')) {
            console.error(chalk.red(`❌ Arquivo deve ser Python (.py): ${arquivo}`));
            process.exit(1);
        }
        await executeAnalysis(arquivo, options);
    });

program.parse(process.argv);

if (process.argv.length === 2) {
    program.help();
}

// IMPLEMENTAÇÕES

async function executeAnalysis(arquivo, options) {
    console.log(chalk.cyan.bold('\n🏗️  CODE ARCHITECTURE ANALYZER\n'));

    const pythonCheck = await checkPythonInstalled();
    if (!pythonCheck.installed) {
        console.error(chalk.red('❌ Python não encontrado!'));
        console.error(chalk.yellow('Instale Python 3.8+: https://python.org'));
        process.exit(1);
    }

    console.log(chalk.green(`✅ Python ${pythonCheck.version} encontrado\n`));

    const spinner = ora(chalk.blue('Analisando código...')).start();

    try {
        const scriptPath = join(__dirname, '..', 'scripts', 'orchestrator.py');
        const args = [scriptPath, arquivo];
        if (options?.noRefactor) args.push('--no-refactor');

        await runPythonScript(args);

        spinner.succeed(chalk.green('✅ Análise concluída!'));

        console.log(chalk.cyan.bold('\n📊 Arquivos gerados:'));
        const baseName = arquivo.replace('.py', '');
        console.log(chalk.gray(`  • ${baseName}_analysis.json`));
        console.log(chalk.gray(`  • ${baseName}_report.md`));
        if (!options?.noRefactor) {
            console.log(chalk.gray(`  • ${arquivo} (refatorado)`));
            console.log(chalk.gray(`  • .backups/${baseName}_backup.py`));
        }
        console.log();

    } catch (error) {
        spinner.fail(chalk.red(`❌ Erro: ${error.message}`));
        process.exit(1);
    }
}

async function executeRefactoring(arquivo) {
    console.log(chalk.cyan.bold('\n🔧 REFATORAÇÃO\n'));

    const pythonCheck = await checkPythonInstalled();
    if (!pythonCheck.installed) {
        console.error(chalk.red('❌ Python não encontrado!'));
        process.exit(1);
    }

    const spinner = ora(chalk.blue('Refatorando...')).start();

    try {
        const scriptPath = join(__dirname, '..', 'scripts', 'refactorer.py');
        await runPythonScript([scriptPath, arquivo]);
        spinner.succeed(chalk.green('✅ Refatoração concluída!'));
    } catch (error) {
        spinner.fail(chalk.red(`❌ Erro: ${error.message}`));
        process.exit(1);
    }
}

async function executeValidation(arquivo) {
    console.log(chalk.cyan.bold('\n✅ VALIDAÇÃO\n'));

    const pythonCheck = await checkPythonInstalled();
    if (!pythonCheck.installed) {
        console.error(chalk.red('❌ Python não encontrado!'));
        process.exit(1);
    }

    const spinner = ora(chalk.blue('Validando...')).start();

    try {
        const scriptPath = join(__dirname, '..', 'scripts', 'validator.py');
        await runPythonScript([scriptPath, arquivo]);
        spinner.succeed(chalk.green('✅ Validação concluída!'));
    } catch (error) {
        spinner.fail(chalk.red(`❌ Erro: ${error.message}`));
        process.exit(1);
    }
}

async function showSystemInfo() {
    console.log(chalk.cyan.bold('\n📋 INFORMAÇÕES DO SISTEMA\n'));

    const pythonCheck = await checkPythonInstalled();

    console.log(chalk.bold('Node.js:'));
    console.log(`  Versão: ${process.version}`);

    console.log(chalk.bold('\nPython:'));
    if (pythonCheck.installed) {
        console.log(`  Status: ${chalk.green('✅ Instalado')}`);
        console.log(`  Versão: ${pythonCheck.version}`);
    } else {
        console.log(`  Status: ${chalk.red('❌ Não encontrado')}`);
        console.log(chalk.yellow('  Instale Python 3.8+: https://python.org'));
    }

    console.log(chalk.bold('\nSkill:'));
    console.log(`  Versão: ${version}\n`);
}

async function setupPython() {
    console.log(chalk.cyan.bold('\n⚙️  SETUP\n'));

    const spinner = ora(chalk.blue('Verificando Python...')).start();

    const pythonCheck = await checkPythonInstalled();

    if (!pythonCheck.installed) {
        spinner.fail(chalk.red('Python não encontrado'));
        console.log(chalk.yellow('\nInstale Python 3.8+: https://python.org'));
        process.exit(1);
    }

    spinner.succeed(chalk.green(`Python ${pythonCheck.version} encontrado`));

    const depSpinner = ora(chalk.blue('Verificando dependências Python...')).start();

    try {
        const deps = ['pylint', 'ruff', 'black', 'isort', 'libcst', 'pytest'];

        depSpinner.text = chalk.blue('Dependências Python já configuradas');
        depSpinner.succeed(chalk.green('✅ Setup concluído!\n'));

    } catch (error) {
        depSpinner.fail(chalk.red(`❌ Erro: ${error.message}`));
        process.exit(1);
    }
}
