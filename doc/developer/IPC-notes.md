# IPC Notes

To support the [async](https://kde-builder.kde.org/en/configuration/conf-options-table.html#conf-async)
parameter, which permits network updates to be run in parallel with the build process, kde-builder implements
some limited inter-process communication (IPC).

In reality there are 3 separate long-term processes during an async build:

                 +-----------------+     +---------------+        +------------+
                 |                 |     |               |        |            |
                 |  main / build   <------    monitor    <---------    update  |
                 |                 |  ^  |               |   ^    |            |
                 +--------^--------+  |  +---------------+   |    +------------+
                          |           |                      |
                          |         $ipc            $updaterToMonitorIPC
                          |
                          |
                 +--------v--------+
                 |                 |
    user ------->|       TTY       |
                 |                 |
                 +-----------------+

- 1. The main (build) process
- 2. The update process, normally squelched
- 3. A "monitor" process, connected to the other two

## Why IPC is necessary

IPC is used to carry information about the status of build updates back to the main process.

Over the years this has evolved to include, using a custom app-specific protocol:

- 1. Success/failure codes (per-project)
- 2. Whether the project was even attempted to be updated at all
- 3. Failure codes (overall)
- 4. Log messages for a project (normally squelched during update)
- 5. Changes to persistent options (must be forwarded to main proc to be persisted)
- 6. "Post build" messages, which must be shown by the main thread just before exit.

You could in principle do most of this by doing something like serializing
changes into a file after each project update and then reading the results from
the file in the main thread using file locking or similar. However, it seemed
simpler to ferry the information over IPC pipes instead.

## How it works, today

At this stage, the IPC data flow is mediated by IPC, which is an
interface class with a couple of methods meant to be reimplemented by
subclasses, and which implements the IPC API on top of those subclass-defined
methods.

The user code in kde-builder is required to create the IPC object before
forking using "fork". The parent then declares that it will be the
receiver and the child declared that it will be the sender.

### Monitor process

Early experiments used only the two build (main) and update processes. However,
this quickly ran into issues trying to keep the main process U/I in sync.
During a build there was no easy way to monitor the build child's output along
with the update child's, and the update child would block if it tried to write
too much output to the build process if the build process was itself blocked
waiting for a build.

The solution was to reinvent a message queue, poorly, for much the same reason
you would use a message queue today in a distributed architecture. It
simplified the problem for build and update and allowed the update process to
send at will without blocking, and likewise the build thread did not have to
worry about blocking by trying to read from the child unless it was safe to
wait.

The monitor simply uses a second `IPC` object to connect to the update
child process, and feeds messages it receives from the child to the parent, in
the order received and exactly once.

### Ordering the update and build

To keep the build from proceeding before the update has completed, the IPC
class supports methods to wait for the project to complete if it hasn't already.
By their nature these are blocking methods, ultimately these block waiting on
I/O from the monitor.

This means that the build process will block forever if the update thread
forgets to send the right message. The update process should build projects in
the same order the build process will expect them, though this won't cause the
build to block forever if it does not.

### Squelching log messages

The various logging methods all output the message immediately. This is
problematic in the context of concurrent build and update processes, especially
since most log messages do not duplicate the name of the project (since it's
normally nearby in the U/I output).

We resolve this tension by having the update process pass the IPC object into
`Debug`, which will then feed the output to the IPC handle instead of
STDOUT/STDERR. In the build process, as log messages are read in from the
update process, they are stored and then printed out once it comes time to
build the project.

This system only works because the update and build processes are separate
processes.  The "modern" scheme I'm building towards does not require the
existence of a separate update process at all, but we may still retain it to
make squelching work.

### Commands that do not require IPC

The log\_command() call in `Util` also uses a fork-based construct to read
I/O from a child (to redirect output to the log file and/or to a callback).

It is safe to use this function from the update thread, as long as we are
disciplined about using unique names for each log-file. The update process will
set the `latest` and `error.log` symlinks as necessary, and the main process
will find `error.log` where it expects to when making the report at the end.

Note that this works only if the base log directory for the project is created
in `BuildContext` before the fork occurs!
