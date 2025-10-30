set --local kde_builder_installation (grep "install-dir" $HOME/.config/kde-builder.yaml | head -1 | sed 's/  #.*//' | sed 's/.*install-dir: //')

set --local kde_builder_options (echo -n "--all-config-projects --all-kde-projects --async --no-async --binpath --branch-group
     --branch --build-dir --build-only --no-build --build-system-only --build-when-unchanged
     --no-build-when-unchanged --force-build --no-force-build --check-self-updates
     --no-check-self-updates --cmake-generator --cmake-options --cmake-toolchain --color
     --no-color --colorful-output --no-colorful-output --compile-commands-export
     --no-compile-commands-export --compile-commands-linking --no-compile-commands-linking
     --configure-flags --custom-build-command --cxxflags --debug --dependency-tree
     --dependency-tree-fullpath --dest-dir --directory-layout --disable-agent-check
     --no-disable-agent-check --do-not-compile --generate-clion-project-config
     --no-generate-clion-project-config --generate-config --generate-qtcreator-project-config
     --no-generate-qtcreator-project-config --generate-vscode-project-config
     --no-generate-vscode-project-config --git-user --help -h --hold-work-branches
     --no-hold-work-branches --ignore-projects -! --include-dependencies
     --no-include-dependencies -D -d --initial-setup --install-dir --install-distro-packages
     --install-login-session --no-install-login-session --install-login-session-only
     --install-only --no-install --libname --libpath --list-installed --log-dir
     --make-install-prefix --make-options --meson-options --metadata-only --nice --niceness
     --ninja-options --no-metadata -M --no-src -S -s --num-cores-low-mem --num-cores
     --override-build-system --persistent-data-file --dry-run --pretend -p --purge-old-logs
     --no-purge-old-logs --qmake-options --qt-install-dir --query --rc-file --rebuild-failures
     --reconfigure --refresh-build-first --refresh-build -r --remove-after-install --resume
     --after --resume-after -a --from --resume-from -f --resume-refresh-build-first -R
     --revision --run-tests --no-run-tests --self-update --set-project-option-value --show-info
     --show-options-specifiers --source-dir --source-when-start-program --src-only
     --stop-after --to --stop-before --until --stop-on-failure --no-stop-on-failure --tag
     --taskset-cpu-list --uninstall --use-clean-install --no-use-clean-install
     --use-idle-io-priority --no-use-idle-io-priority --use-inactive-projects
     --no-use-inactive-projects --version -v --run" | tr ' ' '\n')

set --local options_count (seq 1 (count $kde_builder_options))

for i in $options_count
    complete --command "kde-builder" --no-files --arguments $kde_builder_options[$i]
end

set --local binaries (fish --command "find $kde_builder_installation/bin -type f -exec basename {} \;")
set --local bincount (seq 1 (count $binaries))

for j in $bincount
    complete --command "kde-builder" --exclusive --long run --arguments $binaries[$j]
end
