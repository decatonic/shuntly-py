import sys

import typing_extensions as tp
from invoke import task  # pyright: ignore


# -------------------------------------------------------------------------------
@task
def clean(context):
    """Clean doc and build artifacts"""
    context.run('rm -rf coverage.xml')
    context.run('rm -rf htmlcov')
    context.run('rm -rf doc/build')
    context.run('rm -rf build')
    context.run('rm -rf dist')
    context.run('rm -rf *.egg-info')
    context.run('rm -rf .coverage')
    context.run('rm -rf .mypy_cache')
    context.run('rm -rf .pytest_cache')
    context.run('rm -rf .hypothesis')
    context.run('rm -rf .ipynb_checkpoints')
    context.run('rm -rf .ruff_cache')

# -------------------------------------------------------------------------------


@task
def test(
    context,
    pty=False,
):
    """Run tests.
    """
    w_flag = '--disable-pytest-warnings'
    cmd = f'pytest -s --tb=native {"" if warnings else w_flag} tests'
    context.run(cmd, pty=pty)


@task
def mypy(
    context,
    pty=False,
):
    """Run mypy static analysis."""
    context.run('mypy --strict', pty=pty)


@task
def format_check(context):
    """Run formatting checks."""
    context.run('ruff check --select I')
    context.run('ruff format --check')


@task
def lint(context):
    """Run ruff static analysis."""
    context.run('ruff check')


@task(pre=(mypy, lint, format_check))  # pyright: ignore
def quality(context):
    """Perform all quality checks."""


@task
def format(context):
    """Apply ruff formatting."""
    context.run('ruff check --select I --fix')
    context.run('ruff format')


