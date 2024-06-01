(developer-features)=
# Features for KDE developers

(ssh-agent-reminder)=
## SSH Agent checks

KDE Builder can ensure that KDE developers that use ssh to access the
KDE source repository do not accidentally forget to leave the SSH Agent
tool enabled. This can cause kde-builder to hang indefinitely waiting
for the developer to type in their ssh password, so by default
kde-builder will check if the Agent is running before performing source
updates.

```{note}
This is only done for KDE developers using ssh.
```

You may wish to disable the ssh Agent check, in case of situations where
kde-builder is mis-detecting the presence of an agent. To disable the
agent check, set the `disable-agent-check` option to `true`.

Disabling the SSH agent check:

```text
global
  disable-agent-check true
end global
```
