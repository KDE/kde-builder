# Installation

The preferred installation method is using `uv`.

However, you can choose [alternative installation](#alternative-installation) methods if needed.

(install-with-uv)=
## Install with uv

1. Install the `uv` utility using your preferred method. See the [official documentation](https://docs.astral.sh/uv/getting-started/installation/) for available options.

   You do not need to install Python manually. `uv` will automatically manage the required Python version inside the virtual environment.

2. Install `kde-builder` as a global tool. Choose one of the following versions:

    **Master version** (latest development changes):
    ```bash
    uv tool install "git+https://invent.kde.org/sdk/kde-builder.git"
    ```

    **Specific tag version** (stable release):
    ```bash
    uv tool install "git+https://invent.kde.org/sdk/kde-builder.git@v26.10"
    ```

3. Verify the installation by running:
    ```bash
    kde-builder --version
    ```

## Upgrading

To upgrade `kde-builder` to the latest version, run the appropriate command depending on your installation method:

**If installed with `uv`:**
```bash
uv tool upgrade kde-builder
```

**If installed with `pipx`:**
```bash
pipx upgrade kde-builder
```

(alternative-installation)=
## Alternative Installation

### Using pipx

If `uv` is unavailable on your system, you can fall back to `pipx`. For example:
```bash
pipx install "git+https://invent.kde.org/sdk/kde-builder.git"
```

### Developer Installation

If you plan to develop `kde-builder` itself or test changes, please see [](#editable-installation) in the Developer Documentation chapter.
