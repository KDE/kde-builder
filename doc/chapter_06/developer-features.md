(developer-features)=
# Features for KDE developers

(ssh-agent-reminder)=
## SSH Agent checks

kdesrc-build can ensure that KDE developers that use SSH to access the
KDE source repository do not accidentally forget to leave the SSH Agent
tool enabled. This can cause kdesrc-build to hang indefinitely waiting
for the developer to type in their SSH password, so by default
kdesrc-build will check if the Agent is running before performing source
updates.

```{note}
This is only done for KDE developers using SSH.
```

You may wish to disable the SSH Agent check, in case of situations where
kdesrc-build is mis-detecting the presence of an agent. To disable the
agent check, set the `disable-agent-check` option to `true`.

Disabling the SSH agent check:

```
global
  disable-agent-check true
end global
```
