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

```yaml
global:
  disable-agent-check: true
```

(git-user-setup)=
## Using separate git credentials

If you are using several user identities, for example, one for your work, and another for
KDE development, you would want to make local config in the repositories. KDE Builder lets
you automate this with [git-user](#conf-git-user) config option.

```{code-block} yaml
:name: example-git-user
:caption: Example of specifying user name and user email for all projects
global:
  git-user: "John Smith <johnsmith@example.com>"
```

Now, when KDE Builder clones some project, it will automatically create local git config
(for example, `~/kde/src/kcalc/.git/config`) with specified credentials, that overrides your global
git config (`~/.gitconfig`) credentials.
