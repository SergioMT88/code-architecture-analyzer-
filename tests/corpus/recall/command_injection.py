"""Recall fixture: command injection via subprocess(shell=True) with a dynamic command.

The command string is built by joining tokens and passed to a shell. The first
arg is a plain Name (not an f-string), so the old detector missed it — the
danger signal is shell=True combined with a non-literal command.
"""
import subprocess


def run_command(parts):
    linha = " ".join(parts)
    return subprocess.run(linha, shell=True, capture_output=True)  # EXPECT: InjectionRisk


def safe_command(name):
    # argument vector, shell=False — must NOT be flagged
    return subprocess.run(["rm", "-rf", name], shell=False)
