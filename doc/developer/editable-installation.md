(editable-installation)=
# Editable installation

If you want to develop kde-builder, or test some changes from merge request to kde-builder,
you can make an "editable installation". That is a type of installation when the tool is
still available in your system, but the code it uses points to your local repository. You can
change the kde-builder code in the IDE, and test modified behavior right in your system, without
the need to reinstall the new version.

To make an editable installation, use the following command:
```shell
uv tool install --editable /home/user/Development/kde-builder
```

In the above example we assume that you cloned kde-builder into
`/home/user/Development/kde-builder` directory. Change it to the actual path that you use
for developing projects.

If you have uncommited changes, in the `--version` you will see ".dYYYYMMDD" suffix:
```text
kde-builder --version
kde-builder 0.0.post898+g42cb943fc.d20260928
```
