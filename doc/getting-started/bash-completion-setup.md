# Bash Completion Setup

This page explains how to set up bash completion for kde-builder with all features including menu-complete (cycling through options with TAB).

## Features

### Tab Completion
- Complete kde-builder options with TAB
- Complete project and group names
- Complete installed projects for `--run` option
- File path completion for `--rc-file` option

### Menu-Complete (Cycling)
Press TAB repeatedly to cycle through options:
```bash
kde-builder --a<TAB><TAB><TAB>
# Cycles: --after → --all-config-projects → --all-kde-projects → --async
```

### Mutual Exclusion
Once you use an option, its conflicting options won't be suggested:
```bash
kde-builder --async --<TAB>
# Will NOT show --no-async

kde-builder --build-only --<TAB>
# Will NOT show --no-build, --install-only, or --src-only
```

### Cached Completions
- Project/group names: Cached for 1 hour
- Installed projects: Cached for 5 minutes
- Cache location: `~/.cache/kde-builder/bash-completion/`

To clear cache:
```bash
rm -rf ~/.cache/kde-builder/bash-completion/
```

## Installation and Configuration

Create symlink to the completion file:

```bash
# Create the directory if it doesn't exist
mkdir -p ~/.local/share/bash-completion/completions/

# Link to the completion file
ln -s ~/.local/share/kde-builder/data/completions/bash/kde-builder ~/.local/share/bash-completion/completions/kde-builder
```

Add the following lines to your `~/.bashrc` file:

```bash
# Load kde-builder bash completion
if [ -e ~/.local/share/bash-completion/completions/kde-builder ]; then
  source ~/.local/share/bash-completion/completions/kde-builder
fi
```

Optional: For Menu-Complete Feature (options would be autofilled inline in a cyclic fashion from the menu).

Create or edit `~/.inputrc` and add these lines:

```bash
# Menu-complete: Cycle through completions with TAB
TAB: menu-complete

# Shift+TAB: Cycle backwards through completions
"\e[Z": menu-complete-backward

# Show all options immediately before cycling
set show-all-if-ambiguous on

# Show common prefix before cycling
set menu-complete-display-prefix on

# Case-insensitive completion
set completion-ignore-case on

# Treat hyphens and underscores as equivalent
set completion-map-case on
```

**What this does:**
- First TAB: Shows all matching options
- Second TAB: Fills in the first option
- Third TAB: Cycles to the next option
- Shift+TAB: Cycles backwards

**Example behavior:**
```bash
$ kde-builder --a<TAB>
--after  --all-config-projects  --all-kde-projects  --async

$ kde-builder --a<TAB><TAB>
$ kde-builder --after

$ kde-builder --after <TAB>
$ kde-builder --after --all-config-projects

$ kde-builder --after --all-config-projects <Shift+TAB>
$ kde-builder --after --async
```

## Reload Configuration

After making these changes, reload your configuration:

```bash
# Reload bashrc
source ~/.bashrc

# Reload inputrc (if you edited it)
bind -f ~/.inputrc
```

Or simply restart your terminal.

## Troubleshooting

### Completion not working?

1. **Check if the file is sourced:**
   ```bash
   type _kde_builder
   ```
   Should output: `_kde_builder is a function`.

2. **Reload completion:**
   ```bash
   complete -r kde-builder
   source ~/.local/share/bash-completion/completions/kde-builder
   ```

3. **Check file permissions:**
   ```bash
   ls -l ~/.local/share/bash-completion/completions/kde-builder
   ```
   Should be readable (at least `-rw-r--r--`).

### Menu-complete not working?

1. **Check if inputrc is loaded:**
   ```bash
   bind -v | grep menu-complete
   ```
   Should show: `menu-complete can be found on "\C-i"`.

2. **Reload inputrc:**
   ```bash
   bind -f ~/.inputrc
   ```

3. **Test manually:**
   ```bash
   bind 'TAB: menu-complete'
   ```

### Mutual exclusion not working?

1. **Clear bash functions and reload:**
   ```bash
   unset -f _kde_builder _kde_builder_filter_options _kde_builder_remove_option
   source ~/.local/share/bash-completion/completions/kde-builder
   ```

2. **Verify filter function exists:**
   ```bash
   type _kde_builder_filter_options
   ```

3. **Test manually:**
   ```bash
   COMP_WORDS=(kde-builder --async)
   _kde_builder_filter_options "--async --no-async" | grep "no-async"
   ```
   Should output nothing (--no-async should be filtered).

## Optional: System-Wide Installation

To install for all users (requires root):

```bash
sudo ln -s ~/.local/share/kde-builder/data/completions/bash/kde-builder /usr/share/bash-completion/completions/kde-builder
```

Then each user only needs to configure `~/.inputrc` for menu-complete feature.

## Uninstallation

```bash
# Remove completion file
rm ~/.local/share/bash-completion/completions/kde-builder

# Remove from .bashrc
# (manually edit and remove the kde-builder completion lines)

# Remove from .inputrc
# (manually edit and remove the menu-complete configuration)

# Clear cache
rm -rf ~/.cache/kde-builder/bash-completion/

# Restart terminal or run:
complete -r kde-builder
```

## Comparison with Zsh Completion

Both bash and zsh completions for kde-builder offer similar features:

| Feature | Bash | Zsh |
|---|---|---|
| Option completion | ✅ | ✅ |
| Project/group completion | ✅ | ✅ |
| Mutual exclusion | ️✅ | ✅ |
| Option descriptions | ❌ | ✅ |
| Menu-complete | Via `~/.inputrc` | Built-in |
| Caching | ✅ | ✅ |

**Zsh advantage:** Descriptions appear inline when you press TAB.  
**Bash advantage:** Works everywhere bash is available.  
