(editable-installation)=
# Editable installation

If you want to develop `kde-builder` or test some changes from a merge request, you can use
an "editable installation". That type of installation keeps the tool available system-wide,
but points it directly to your local repository. You can modify the `kde-builder` code in
your IDE and test the updated behavior immediately without needing to reinstall the tool.

To perform an editable installation, run the following command:
```bash
uv tool install --editable "/home/user/Development/kde-builder"
```

In the example above, we assume that you cloned `kde-builder` into the
`/home/user/Development/kde-builder` directory. Replace it with the actual path to your
local repository.

If you have uncommited changes, running `--version` will append `.dYYYYMMDD` suffix to
the version string:
```text
$ kde-builder --version
kde-builder 26.10.post5+g123abc.d20261128
```
