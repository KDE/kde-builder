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
#   optdepends:
#   - dep: akonadi-calendar-tools
#     reason: tools for managing akonadi calendars
# akonadi-calendar-tools:
#   depends:
#   - gcc-libs
#   - glibc
#   - libakonadi
#   - qt6-base
#   makedepends: []
#   optdepends: []
dependencies = yaml.safe_load(open("./deps.yaml", "r"))

dep_count = {}

for name, deps in dependencies.items():
    all_deps = (
        deps["depends"] + deps["makedepends"] + [d["dep"] for d in deps["optdepends"]]
    )
    for dep in all_deps:
        dep_count[dep] = dep_count.get(dep, 0) + 1

total_targets = len(dependencies)
for dep, count in sorted(dep_count.items(), key=lambda x: x[1], reverse=True):
    percentage = count / total_targets * 100
    print(f"{dep}: {count} ({percentage:.2f}%)")
