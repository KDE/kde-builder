## Autocomplete for kde-builder --run

# SPDX-FileCopyrightText: 2021 Sebastian Engel <dev@sebastianengel.eu>
#
# SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL

function _comp_kde_builder_run
{
  local cur
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"

  # Complete only the first argument
  if [[ $COMP_CWORD != 1 ]]; then
    return 0
  fi

  # Retrieve build modules through kde-builder
  # If the exit status indicates failure, set the wordlist empty to avoid
  # unrelated messages.
  local modules
  if ! modules=$(kde-build --list-installed);
  then
      modules=""
  fi

  # Return completions that match the current word
  COMPREPLY=( $(compgen -W "${modules}" -- "$cur") )

  return 0
}

## Register autocomplete function
complete -o nospace -F _comp_kde_builder_run kde-builder
