(dev-env-setup)=
# Development Environment Setup

This section gives guidance on setting up a development environment suitable for
working on KDE Builder itself. For regular installation options for end users,
please consult the [](#getting-started) section instead.

```{note}
If you're new to KDE Development, and are looking for guidance on setting up a
development environment for working on KDE software in general, please read this
[tutorial][0] instead!
```

## Create an Editable Installation

If you want to develop KDE Builder or test some changes from a merge request,
you can use an [editable installation][1]. This kind of installation maps your
version of KDE Builder to the `kde-builder` command for your user, and allows
you to test your modifications immediately without having to reinstall the tool.

To create an editable installation, run the following command from your local
copy of the Git repository:

```console
uv tool install --editable .
```

To test that your local copy is now the active version, compare the version
string against the hash of the Git commit you were on when you performed the
installation. To have `kde-builder` print the version string, run

```console
$ kde-builder --version
26.10.post5+g123abc789
```

In this example, `.post5` indicates that you are 5 commits after the release
tagged as version `26.10`, while `+g123abc789` contains the abbreviated hash
of the corresponding commit.

If you had any uncommitted changes when you performed the installation, the date
is appended to the version string. For example:

```console
$ kde-builder --version
kde-builder 26.10.post5+g123abc789.d20261128
```

This version string remains unchanged until you reinstall KDE Builder, either as
a regular installation or as a fresh editable installation. Newly added commits
won't be reflected in the version string.

## Use Linters to Check for Issues

If you set up your development environment using the method described above, you
will automatically have access to some of the tools that are also used in the CI
pipeline.

```{important}
Please make use of these tools before submitting a new merge request or adding
more commits to an existing one. It is cheaper and quicker to run them locally
instead of triggering an entire CI pipeline.
```

### Ruff

We use [Ruff][2] as a linter for our Python sources. To check the entire project
for issues, use

```console
uv run ruff check
```

Ruff is very fast, so you may want to consider adding it to a `pre-commit` hook.
This will prevent you from committing Python sources that violate KDE Builder's
conventions.

### Reuse

We use [reuse][3] to ensure we comply with the [KDE Licensing Policy][4]. Check
your sources for policy violations such as missing SPDX annotations by running

```console
uv run reuse lint
```

This tool does not run as quickly as Ruff, so you may not want to add it to a
`pre-commit` hook. You may want to add it to a `pre-push` hook instead, since
you can always add missing license information with [`git history fixup`][5].

## Testing

```{warning}
**Do not run the tests inside of a Git hook!**

There is currently an unmitigated interaction between the environment as set up
by some Git hooks and the integration tests that **will break** the repository.
```

KDE Builder comes with unit tests and integration tests built on [pytest][6].
You can run the entire test suite using

```console
uv run pytest
```

To also generate a coverage report, run

```console
uv run pytest --cov --cov-report=term --cov-report=xml
```

## Building Documentation

The sources for the documentation you are currently reading are also included in
the Git repository. To build them locally, use the helper script:

```console
./scripts/build_docs.sh
```

If you intend to work on them, you can start a watcher that automatically builds
the documentation whenever the sources change and renders a live preview in your
browser:

```console
./scripts/build_docs.sh --watch
```

For more details, consult the `README.md` file in the `doc` folder.


[0]: https://develop.kde.org/docs/getting-started/building/kde-builder-setup/
[1]: https://pip.pypa.io/en/stable/topics/local-project-installs/#editable-installs
[2]: https://docs.astral.sh/ruff/
[3]: https://codeberg.org/fsfe/reuse-tool
[4]: https://community.kde.org/Policies/Licensing_Policy
[5]: https://git-scm.com/docs/git-history#Documentation/git-history.txt-fixupcommit
[6]: https://pytest.org
