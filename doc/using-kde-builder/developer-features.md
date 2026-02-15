(developer-features)=
# Features for KDE developers

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
