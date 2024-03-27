# Adding new options

Defaults for options are made in `BuildContext.py`.

This table will help you determine where you should add new options or where to move them when editing them.

```{list-table} Determining where to place options
:header-rows: 1
:align: center

*   - Is context <br>
        option
    - Available <br>
        from <br>
        cmdline
    - Has <br>
        synonimic <br>
        names \*
    - Has <br>
        negatable <br>
        form
    - Has <br>
        parameter
    - Where to add the option

*   - No
    - Yes
    - \*
    - \*
    - \*
    - In `Cmdline.py` to `non_context_options`

*   - Yes
    - No
    - No
    - No
    - Yes
    - In `BuildContext.py` to `GlobalOptions_private`

*   - Yes
    - Yes
    - Yes
    - \*
    - \*
    - In `BuildContext.py` to `GlobalOptions_with_extra_specifier` <br>
        and in `Cmdline.py` to `context_options_with_extra_specifier`

*   - Yes
    - Yes
    - No
    - Yes
    - No
    - In `BuildContext.py` to `GlobalOptions_with_negatable_form`

*   - Yes
    - Yes
    - No
    - No
    - Yes
    - In `BuildContext.py` to `GlobalOptions_with_parameter`

*   - Yes
    - Yes
    - No
    - No
    - No
    - In `BuildContext.py` to `GlobalOptions_without_parameter`

*   - \*
    - Yes
    - Yes
    - \*
    - \*
    - Specially treated synonims of other options. <br>
        In `Cmdline.py` to `options_converted_to_canonical`
```

\* Note that for "Has synonimic names" field, even if "No" is specified,
    the option still may have synonimic name, if the synonim is specified in
    `options_converted_to_canonical` and is handles specifically.

Do not forget to regenerate zsh autocompletion script. For this, run `gen_zsh_completions.py` script:

```bash
./scripts/gen_zsh_completions.py > data/completions/zsh/_kde-builder
```
