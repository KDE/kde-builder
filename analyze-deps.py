#!/usr/bin/python

import yaml


## Example of deps.yaml
# akonadi-calendar:
#   depends:
#   - gcc-libs
#   - glibc
#   - gpgme
#   - libakonadi
#   - qgpgme-qt6
#   - qt6-base
#   makedepends:
#   - doxygen
#   - qt6-doc
#   - qt6-tools
#   optdepends: []
# akonadi-calendar-tools:
#   depends:
#   - gcc-libs
#   - glibc
#   - libakonadi
#   - qt6-base
#   makedepends: []
#   optdepends: []
deps_info = yaml.safe_load(open("./deps.yaml", "r"))

dep_count = {}

for name, deps in deps_info.items():
    all_deps = deps["depends"] + deps["makedepends"] + deps["optdepends"]
    for dep in all_deps:
        dep_count[dep] = dep_count.get(dep, 0) + 1

total_targets = len(deps_info)
for dep, count in sorted(dep_count.items(), key=lambda x: x[1], reverse=True):
    percentage = count / total_targets * 100
    print(f"{dep}: {count} ({percentage:.2f}%)")
