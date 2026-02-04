import sys
import typing as tp

import nox

ARTIFACTS = (
    "build",
    "dist",
    "*.egg-info",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
)

# Make `nox` default to running tests if you just do `nox`
nox.options.sessions = ["test"]


def do_clean(session: nox.Session) -> None:
    for artifact in sorted(ARTIFACTS):
        session.run("rm", "-rf", artifact, external=True)


def do_test(session: nox.Session) -> None:

    fps = []
    fps.append("test/unit")

    warnings = "--warnings" in session.posargs
    w_flag = "--disable-pytest-warnings"
    cmd = f"pytest -s --tb=native {w_flag if warnings else ''} {' '.join(fps)}"

    session.run(
        *cmd.split(" "),
        external=True,
    )


def do_lint(session: nox.Session) -> None:
    session.run(
        "ruff",
        "check",
        external=True,
    )


def do_mypy(session: nox.Session) -> None:
    session.run(
        "mypy",
        "--strict",
        external=True,
    )


def do_format(session: nox.Session) -> None:
    for cmd in ("ruff check --select I --fix", "ruff format"):
        session.run(
            *cmd.split(" "),
            external=True,
        )


def do_format_check(session: nox.Session) -> None:
    for cmd in ("ruff check --select I", "ruff format --check"):
        session.run(
            *cmd.split(" "),
            external=True,
        )


@nox.session(python=False)  # use current environment
def clean(session):
    do_clean(session)


@nox.session(python=False)
def test(session):
    do_test(session)


@nox.session(python=False)
def test_typing(session):
    do_test_typing(session)


@nox.session(python=False)
def test_ex(session):
    do_test_ex(session)


@nox.session(python=False)
def lint(session):
    do_lint(session)


@nox.session(python=False)
def format(session):
    do_format(session)


@nox.session(python=False)
def mypy(session):
    do_mypy(session)


@nox.session(python=False)
def quality(session):
    do_lint(session)
    do_format_check(session)
    do_mypy(session)


@nox.session(python=False)  # use current environment
def build(session):
    do_clean(session)
    session.run(
        sys.executable,
        "setup.py",
        "sdist",
        "bdist_wheel",
        external=True,
    )
