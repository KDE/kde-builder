(kde-builder-logging)=
# Build logging

(logging-overview)=
## Logging overview

Logging is a KDE Builder feature whereby the output from every command
that kde-builder runs is saved to a file for examination later, if
necessary. This is done because it is often necessary to have the output
of these programs when there is a build failure, because there are so
many reasons why a build can fail in the first place.

(log-directory-layout)=
### Logging directory layout

The logs are always stored under the log directory. The destination of
the log directory is controlled by the [log-dir](#conf-log-dir) option,
which defaults to `~/kde/log`. In the rest of this section, this value will be referred to as `${log-dir}`.

Under `${log-dir}`, there is a set of directories, one for every time that
kde-builder was run. Each directory is named with the date, and the run
number. For instance, the second time that kde-builder is run on
31 July 2024, it would create a directory named `2024-07-31_02`, where the
2024-07-31 is for the date, and the 02 is the run number.

Now, each such directory will itself contain a set of
directories, one for every KDE project that kde-builder tries to build.
Also, a file called `status-list.log` will be contained in the directory,
which will allow you to determine which projects built and which failed.

```{note}
If a project itself has a subproject (such as extragear/multimedia,
playground/utils), then there would actually be a
matching layout in the log directory. For example, the logs for
playground/utils after the last kde-builder run would be found in
`${log-dir}/latest/playground/utils`, and not under `${log-dir}/latest/utils`.
```

In each project log directory, you will find a set of files for each
operation that kde-builder performs. If kde-builder updates a project,
you may see filenames such as `git-checkout-update.log` (for a project
checkout or when updating a project that has already been checked out).
If the `configure` command was run, then you would expect to see a
`configure.log` in that directory.

If an error occurred, you should be able to see an explanation of why in
one of the files. To help you determine which file contains the error,
kde-builder will create a link from the file containing the error (such
as `build-1.log` to a file called `error.log`).

For your convenience, kde-builder will also create a link to the logs
for your latest run, called `latest`. So the logs for the most recent
kde-builder run should always be under `${log-dir}/latest`.

The upshot to all of this is that to see why a project failed to build
after your last kde-builder invocation, the file you should look at first is
`${log-dir}/latest/project-name/error.log`.

```{tip}
If the file `error.log` is empty (especially after an installation),
then perhaps there was no error. Some of the tools used by the KDE build
system will sometimes mistakenly report an error when there was none.

Also, some commands will evade kde-builder's output redirection and
bypass the log file in certain circumstances (normally when performing
the first git checkout), and the error output in that case is not in the
log file but is instead at the Konsole or terminal where you ran
kde-builder.
```
