# SPDX-FileCopyrightText: 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import logging
import os.path
import selectors
import signal
import sys
import time
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import setproctitle

from .kb_exception import KBRuntimeError
from .debug import Debug
from .debug import KBLogger
from .ipc.ipc import IPC
from .ipc.null import IPCNull
from .ipc.pipe import IPCPipe
from .util.util import Util
from .util.textwrap_mod import textwrap

if TYPE_CHECKING:
    from build_context import BuildContext
    from .application import Application
    from .module.module import Module

logger_ipc = KBLogger.getLogger("ipc")
logger_taskmanager = KBLogger.getLogger("taskmanager")


class TaskManager:
    """
    Consolidates the actual orchestration of all the module update, build_system setup, configure, build, and install jobs once the :class:`Application` has set up the :class:`BuildContext` for the current build.

    In particular, the concurrent portion of the build is concentrated more-or-less
    entirely within "run_all_tasks", although other parts of the script have to be
    aware of concurrency.

    Examples:
    ::

        Util.assert_isa(app, Application)
        mgr = TaskManager(app)

        # build context must be setup first
        result = mgr.run_all_tasks()

        # all module updates/builds/etc. complete
    """

    def __init__(self, app: Application):
        from .application import Application
        Util.assert_isa(app, Application)

        self.ksb_app = app
        self.DO_STOP = 0

    def run_all_tasks(self) -> int:
        """
        Return shell-style result code.
        """
        # What we're going to do is fork another child to perform the source
        # updates while we build.  Setup for this first by initializing some
        # shared memory.
        ctx = self.ksb_app.context
        result = 0
        ipc = None

        def update_opts_sub(mod_name, k, v):
            ctx.set_persistent_option(mod_name, k, v)

        if sys.platform == "darwin":
            # There were reports that macOS does not play well with async mode. See https://invent.kde.org/sdk/kde-builder/-/issues/79
            if ctx.get_option("async"):
                logger_ipc.warning("Disabling async mode due to macOS detected.")
                ctx.set_option("async", False)

        if ctx.uses_concurrent_phases() and ctx.get_option("async"):
            ipc = IPCPipe()
        else:
            ipc = IPCNull()

        ipc.set_persistent_option_handler(update_opts_sub)

        if ipc.supports_concurrency():
            result = self._handle_async_build(ipc, ctx)
            if logger_ipc.level == logging.DEBUG:
                ipc.output_pending_logged_messages()
        else:
            logger_taskmanager.debug("Using no IPC mechanism\n")

            # If the user sends SIGHUP during the build, we should allow the
            # current module to complete and then exit early.
            def handle_sighup(signum, frame):
                print("[noasync] recv SIGHUP, will end after this project")
                self.DO_STOP = 1

            signal.signal(signal.SIGHUP, handle_sighup)

            logger_taskmanager.warning("\n b[<<<  Update Process  >>>]\n")
            result: int = self._handle_updates(ipc, ctx)

            logger_taskmanager.warning(" b[<<<  Build Process  >>>]\n")
            result: int = self._handle_build(ipc, ctx) or result

        return result

    # Internal API

    def _handle_updates(self, ipc: IPC, ctx: BuildContext) -> int:
        """
        Update a list of modules.

        Args:
            ipc: IPC module to pass results to.
            ctx: Build Context, which will be used to determine the module update list.

        The ipc parameter contains an object that is responsible for communicating
        the status of building the modules. This function must account for every
        module in ctx's update phase to the ipc object before returning.

        Returns:
             0 on success, non-zero on error.
        """
        update_list: list[Module] = ctx.modules_in_phase("update")

        # No reason to print out the text if we're not doing anything.
        if not update_list:
            ipc.send_ipc_message(IPC.ALL_UPDATING, "update-list-empty")
            ipc.send_ipc_message(IPC.ALL_DONE, "update-list-empty")
            return 0

        if not self._check_for_ssh_agent(ctx):
            ipc.send_ipc_message(IPC.ALL_FAILURE, "ssh-failure")
            return 1

        kdesrc = ctx.get_source_dir()
        if not os.path.exists(kdesrc):
            if not ipc.supports_concurrency():
                logger_taskmanager.warning(f"Creating global source directory")

            logger_taskmanager.debug("\tKDE source download directory doesn't exist, creating.\n")

            if not Util.super_mkdir(kdesrc):
                logger_taskmanager.error(f"\tUnable to make directory r[{kdesrc}]!")
                ipc.send_ipc_message(IPC.ALL_FAILURE, "no-source-dir")
                return 1

        # Once at this point, any errors we get should be limited to a module,
        # which means we can tell the build thread to start.
        ipc.send_ipc_message(IPC.ALL_UPDATING, "starting-updates")

        had_error = 0
        cur_module = 1
        num_modules = len(update_list)

        for module in update_list:
            if self.DO_STOP:
                logger_taskmanager.warning(" y[b[* * *] Early exit requested, aborting updates.")
                break

            ipc.set_logged_module(module.name)

            if not ipc.supports_concurrency():
                block_substr = self._form_block_substring(module)
                logger_taskmanager.warning(f"Updating {block_substr} ({cur_module}/{num_modules})")

            # Note that this must be in this order to avoid accidentally not
            # running update() from short-circuiting if an error is noted.
            had_error = not module.update(ipc, ctx) or had_error

            # Cache module directories, e.g. to be consumed in kde-builder --run
            # This is needed for --no-async mode where the buildSingleModule won't run
            # But the other one is needed for --async mode since persistent options
            # only work from within the build process
            module.set_persistent_option("source-dir", module.fullpath("source"))
            cur_module += 1

        ipc.send_ipc_message(IPC.ALL_DONE, f"had_errors: {had_error}")
        return had_error

    @staticmethod
    def _build_single_module(ipc: IPC, ctx: BuildContext, module: Module, start_time: int) -> str:
        """
        Build the given module.

        Returns:
             The failure phase, or empty string on success.
        """
        module.reset_environment()
        module.setup_environment()

        # Cache module directories, e.g. to be consumed in kde-builder --run
        module.set_persistent_option("source-dir", module.fullpath("source"))
        module.set_persistent_option("build-dir", module.fullpath("build"))
        module.set_persistent_option("install-dir", module.installation_path())

        fail_count: int = module.get_persistent_option("failure-count") or 0
        result_status: str
        message: str
        result_status, message = ipc.wait_for_module(module)
        ipc.forget_module(module)

        if result_status == "failed":
            logger_taskmanager.error(f"\tUnable to update r[{module}], build canceled.")
            fail_count += 1
            module.set_persistent_option("failure-count", fail_count)
            return "update"
        elif result_status == "success":
            logger_taskmanager.warning(f"\tSource update complete for g[{module}]: {message}")
            why_refresh = ipc.refresh_reason_for(module.name)
            if why_refresh:
                logger_taskmanager.info(f"\t  Rebuilding because {why_refresh}")
        elif result_status == "skipped":
            # Skip actually building a module if the user has selected to skip
            # builds when the source code was not actually updated. But, don't skip
            # if we didn't successfully build last time.
            if not module.get_option("build-when-unchanged") and fail_count == 0:
                logger_taskmanager.warning(f"\tSkipping g[{module}] because its source code has not changed.")
                return ""
            logger_taskmanager.warning(f"\tNo changes to g[{module}] source code, but proceeding to build anyway.")

        # If the build gets interrupted, ensure the persistent options that are
        # written reflect that the build failed by preemptively setting the future
        # value to write. If the build succeeds we'll reset to 0 then.
        module.set_persistent_option("failure-count", fail_count + 1)

        if module.build():
            module.set_persistent_option("failure-count", 0)
            return ""
        return "build"  # phase failed at

    def _handle_build(self, ipc: IPC, ctx: BuildContext) -> int:
        """
        Handle the build process.

        Args:
            ipc: IPC object to receive results from.
            ctx: Build Context, which is used to determine list of modules to build.

        If projects are not already checked-out and/or updated, this
        function WILL NOT do so for you.

        This function assumes that the source directory has already been set up.
        It will create the build directory if it doesn't already exist.

        If builddir/module/.refresh-me exists, the function will
        completely rebuild the module (as if --refresh-build were passed for that
        module).

        Returns:
             0 for success, non-zero for failure.
        """
        modules: list[Module] = ctx.modules_in_phase("build")

        # No reason to print building messages if we're not building.
        if not modules:
            return 0

        if ctx.get_option("refresh-build-first"):
            modules[0].set_option("refresh-build", True)

        # IPC queue should have a message saying whether or not to bother with the
        # build.
        ipc.wait_for_stream_start()
        ctx.unset_persistent_option("global", "resume-list")
        ctx_logdir = ctx.get_log_dir()

        if Debug().pretending():
            outfile = "/dev/null"
        else:
            outfile = ctx_logdir + "/status-list.log"

        try:
            status_fh = open(outfile, "w")
        except OSError:
            logger_taskmanager.error(textwrap.dedent(f"""\
             r[b[*] Unable to open output status file r[b[{outfile}]
             r[b[*] You won't be able to use the g[--resume] switch next run.
            """))
            outfile = None

        build_done: list[str] = []
        result = 0

        cur_module = 1
        num_modules = len(modules)

        status_viewer = ctx.status_view
        status_viewer.number_modules_total(num_modules)

        while modules:
            module = modules.pop(0)
            if self.DO_STOP:
                logger_taskmanager.warning(" y[b[* * *] Early exit requested, cancelling build of further projects.")
                break

            module_name = module.name
            block_substr = self._form_block_substring(module)
            logger_taskmanager.warning(f"Building {block_substr} ({cur_module}/{num_modules})")

            start_time = int(time.time())
            failed_phase: str = TaskManager._build_single_module(ipc, ctx, module, start_time)
            elapsed: str = Util.prettify_seconds(int(time.time()) - start_time)

            if failed_phase:
                # FAILURE
                ctx.mark_module_phase_failed(failed_phase, module)
                print(f"{module}: Failed on {failed_phase} after {elapsed}.", file=status_fh)

                if result == 0:
                    # No failures yet, mark this as resume point
                    module_list = ", ".join([f"{elem}" for elem in [module] + modules])
                    ctx.set_persistent_option("global", "resume-list", module_list)
                result = 1

                if module.get_option("stop-on-failure"):
                    logger_taskmanager.warning(f"\n{module} didn't build, stopping here.")
                    return 1  # Error

                logfile = module.get_option("#error-log-file")
                logger_taskmanager.info("\tError log: r[" + logfile)
                status_viewer.number_modules_failed(1 + status_viewer.number_modules_failed())
            else:
                # Success
                print(f"{module}: Succeeded after {elapsed}.", file=status_fh)
                build_done.append(module_name)  # Make it show up as a success
                status_viewer.number_modules_succeeded(1 + status_viewer.number_modules_succeeded())
            cur_module += 1
            print()  # Space things out

        if outfile:
            status_fh.close()

            # Update the symlink in latest to point to this file.
            logdir = ctx.get_absolute_path("log-dir")
            status_file_loc = f"{logdir}/latest/status-list.log"
            if os.path.islink(status_file_loc):
                Util.safe_unlink(status_file_loc)

            if not os.path.exists(status_file_loc):  # pl2py: in perl the os.symlink does not overwrite the existing symlink and returns success
                try:
                    os.symlink(outfile, status_file_loc)
                except FileNotFoundError:
                    # pl2py: In perl they just ignore the case when the symlink was not successfully created.
                    # This case may happen when you do not have a source directory (the log directory that will contain a symlink),
                    # and do pretending. In pretending, the real log file is /dev/null.
                    # So os.symlink will try to symlink "/home/username/kde/src/log/latest/status-list.log" to "/dev/null" when "/home/username/kde" dir does not exist.
                    # We also will ignore that.
                    pass

            screenlog_file_loc = f"{logdir}/latest/screen.log"
            if os.path.islink(screenlog_file_loc):
                Util.safe_unlink(screenlog_file_loc)

            if not os.path.exists(screenlog_file_loc):
                try:
                    realfile = ctx_logdir + "/screen.log"
                    # After first launching in pretending mode, the symlink becomes broken (points to the log dir, which is not actually created).
                    # And at second launching in pretending mode, we get here (because os.path.exists returns False in case of broken symlink).
                    # And this causes a FileAlreadyExists exception.
                    # So, we will only symlink if not pretending.
                    if not Debug().pretending():
                        os.symlink(realfile, screenlog_file_loc)
                except FileNotFoundError:
                    pass

        if len(build_done) > 0:
            logger_taskmanager.info("<<<  g[PROJECTS SUCCESSFULLY BUILT]  >>>")

        successes = len(build_done)
        if successes == 1:
            mods = "project"
        else:
            mods = "projects"

        if not Debug().pretending():
            # Print out results, and output to a file
            logdir = ctx.get_log_dir()

            with open(f"{logdir}/successfully-built", "w") as built:
                for module in build_done:
                    if successes <= 10:
                        logger_taskmanager.info(f"{module}")
                    print(f"{module}", file=built)

            if successes > 10:
                logger_taskmanager.info(f"Built g[{successes}] {mods}")
        else:
            # Just print out the results
            if successes <= 10:
                logger_taskmanager.info("g[" + "]\ng[".join(build_done) + "]")
            else:
                if successes > 10:
                    logger_taskmanager.info(f"Built g[{successes}] {mods}")
        return result

    def _handle_async_build(self, monitor_to_build_ipc: IPCPipe, ctx: BuildContext) -> int:
        """
        Special-cases the handling of the update and build phases, by performing them concurrently (where possible), using forked processes.

        Only one thread or process of execution will return from this procedure. Any
        other processes will be forced to exit after running their assigned module
        phase(s).

        We also redirect :class:`Debug` output messages to be sent to a single process
        for display on the terminal instead of allowing them all to interrupt each
        other.

        Args:
            monitor_to_build_ipc: IPC Object to use for sending/receiving update/build status. It must be
                an object type that supports IPC concurrency (e.g. IPCPipe).
            ctx: Build Context to use, from which the module lists will be determined.

        Returns:
             0 on success, non-zero on failure.
        """
        # The exact method for async is that two children are forked.  One child
        # is a source update process.  The other child is a monitor process which will
        # hold status updates from the update process so that the updates may
        # happen without waiting for us to be ready to read.

        print()  # Space out from metadata messages.

        # Before we fork we should pre-calculate where the logs will go so that the
        # children do not try to do the same calculation independently because they
        # didn't know it's already been figured out.
        for module in ctx.modules:
            module.get_log_dir()

        result = 0
        monitor_pid = os.fork()
        updater_pid = None

        if monitor_pid == 0:
            # child of build (i.e. monitor and updater)
            updater_to_monitor_ipc = IPCPipe()
            updater_pid = os.fork()

            if updater_pid == 0:
                # child of monitor (i.e. updater)

                def sigint_handler(sig, frame):
                    # print("[updater process] received SIGINT.")
                    def unraisable_hook(unraisable):
                        pass

                    sys.unraisablehook = unraisable_hook  # To prevent printing error "Exception ignored in".
                    sys.exit(signal.SIGINT)

                signal.signal(signal.SIGINT, sigint_handler)

                # If the user sends SIGHUP during the build, we should allow the
                # current module to complete and then exit early.
                def sighup_handler(signum, frame):
                    print(f"[updater process] recv SIGHUP, will end after updating {updater_to_monitor_ipc.logged_module} project.")
                    self.DO_STOP = 1

                signal.signal(signal.SIGHUP, sighup_handler)

                setproctitle.setproctitle("kde-builder-updater")
                updater_to_monitor_ipc.set_sender()
                Debug().set_ipc(updater_to_monitor_ipc)

                exitcode = self._handle_updates(updater_to_monitor_ipc, ctx)
                # print("Updater process exiting with code", exitcode)
                sys.exit(exitcode)
            else:
                # still monitor

                def sigint_handler(sig, frame):
                    # print("[monitor process] received SIGINT.")

                    def unraisable_hook(unraisable):
                        pass

                    sys.unraisablehook = unraisable_hook  # To prevent printing error "Exception ignored in".
                    sys.exit(signal.SIGINT)

                signal.signal(signal.SIGINT, sigint_handler)

                # If the user sends SIGHUP during the build, we should allow the
                # current module to complete and then exit early.
                def sighup_handler(signum, frame):
                    print("[monitor process] recv SIGHUP, will end after updater process finishes.")

                    # If we haven't recv'd yet, forward to monitor in case user didn't
                    # send to process group
                    if not self.DO_STOP:
                        os.kill(updater_pid, signal.SIGHUP)
                    self.DO_STOP = 1

                signal.signal(signal.SIGHUP, sighup_handler)

                setproctitle.setproctitle("kde-builder-monitor")
                monitor_to_build_ipc.set_sender()
                updater_to_monitor_ipc.set_receiver()

                monitor_to_build_ipc.set_logged_module("#monitor#")  # This /should/ never be used...
                Debug().set_ipc(monitor_to_build_ipc)

                exitcode = self._handle_monitoring(monitor_to_build_ipc, updater_to_monitor_ipc)
                os.waitpid(updater_pid, 0)
                # print("Monitor process exiting with code", exitcode)
                sys.exit(exitcode)
        else:
            # Still the parent, let's do the build.

            # If the user sends SIGHUP during the build, we should allow the current
            # module to complete and then exit early.
            def signal_handler(signum, frame):
                print("[build process] recv SIGHUP, will end after this project")

                # If we haven't recv'd yet, forward to monitor in case user didn't
                # send to process group
                if not self.DO_STOP:
                    os.kill(monitor_pid, signal.SIGHUP)
                self.DO_STOP = 1

            signal.signal(signal.SIGHUP, signal_handler)

            setproctitle.setproctitle("kde-builder-build")
            monitor_to_build_ipc.set_receiver()
            result: int = self._handle_build(monitor_to_build_ipc, ctx)

            if result and ctx.get_option("stop-on-failure"):
                # It's possible if build fails on some near-first module, and returned because of stop-on-failure option, the git update process may still be running.
                # We will ask monitor to ask updater to finish gracefully.
                # If the monitor process already finished (in Zombie state), sending signal is not harmful (i.e. obviously has no effect, but will not raise exception).

                # print("Asking to stop updates gracefully")
                os.kill(monitor_pid, signal.SIGHUP)

        monitor_to_build_ipc.wait_for_end()

        # Display a message for updated modules not listed because they were not
        # built.
        unseen_modules: dict[str, str] = monitor_to_build_ipc.unacknowledged_modules()
        if unseen_modules:
            # The only current way we should get unacknowledged modules is if the
            # build thread manages to end earlier than the update thread.  This
            # should only happen under --stop-on-failure if an early build fails.
            #
            # If an update fails the message will still be printed to the user, so
            # we don't need to note it separately here, and there's no need to list
            # one-by-one the modules that successfully updated.
            logger_taskmanager.debug("Some projects were updated but not built")

        pid, status = os.waitpid(monitor_pid, 0)
        if os.WEXITSTATUS(status) != 0:
            result = 1

        monitor_to_build_ipc.close()
        return result

    @staticmethod
    def _check_for_ssh_agent(ctx: BuildContext) -> bool:
        """
        Check if we are supposed to use ssh agent by examining the environment, and if so, checks if ssh-agent has a list of identities.

        If it doesn't, we run
        ssh-add (with no arguments) and inform the user. This can be controlled with
        the disable-agent-check parameter.

        Args:
            ctx: Build context
        """
        # Don't bother with all this if the user isn't even using SSH.
        if Debug().pretending():
            return True
        if ctx.get_option("disable-agent-check"):
            return True

        git_servers: list[Module] = [module for module in ctx.modules_in_phase("update") if module.scm_type() == "git"]

        ssh_servers: list[Module] = []
        for gitserver in git_servers:
            if url := urlparse(gitserver.get_option("#resolved-repository")):  # Check for git+ssh:// or git@git.kde.org:/path/etc.
                if url.scheme == "git+ssh" or url.username == "git" and url.hostname == "git.kde.org":
                    ssh_servers.append(gitserver)

        if not ssh_servers:
            return True
        logger_taskmanager.debug("\tChecking for SSH Agent")

        # We're using ssh to download, see if ssh-agent is running.
        if "SSH_AGENT_PID" not in os.environ:
            return True

        pid = os.environ.get("SSH_AGENT_PID")

        # It's supposed to be running, let's see if there exists the program with
        # that pid (this check is linux-specific at the moment).
        if os.path.isdir("/proc") and not os.path.exists(f"/proc/{pid}"):
            # local $" = ", "; # override list interpolation separator

            logger_taskmanager.warning(textwrap.dedent(f"""\
                y[b[ *] SSH Agent is enabled, but y[doesn't seem to be running].
                y[b[ *] The agent is needed for these projects:
                y[b[ *]   b[{ssh_servers}]
                y[b[ *] Please check that the agent is running and its environment variables defined
                """))
            return False

        # The agent is running, but does it have any keys?  We can't be more specific
        # with this check because we don't know what key is required.
        no_keys = 0

        def no_keys_filter(_):
            nonlocal no_keys
            if not no_keys:
                no_keys = "no identities"

        Util.filter_program_output(no_keys_filter, "ssh-add", "-l")

        if not no_keys:
            return True

        print(Debug().colorize(textwrap.dedent("""\
            b[y[*] SSH Agent does not appear to be managing any keys.  This will lead to you
            being prompted for every project update for your SSH passphrase.  So, we're
            running g[ssh-add] for you.  Please type your passphrase at the prompt when
            requested, (or simply Ctrl-C to abort the script).
            """)))
        command_line = ["ssh-add"]
        ident_file = ctx.get_option("ssh-identity-file")
        if ident_file:
            command_line.append(ident_file)
        result = os.system(command_line)

        # Run this code for both death-by-signal and nonzero return
        if result:
            rcfile = ctx.rc_file()
            print(Debug().colorize(textwrap.dedent(f"""

                y[b[*] Unable to add SSH identity, aborting.
                y[b[*] If you don't want kde-builder to check in the future,
                y[b[*] Set the g[disable-agent-check] option to g[true] in your {rcfile}.

                """)))
            return False
        return True

    @staticmethod
    def _handle_monitoring(ipc_to_build: IPCPipe, ipc_from_updater: IPCPipe) -> int:
        """
        Handle monitoring process when using :class:`IPCPipe`.

        It reads in all status reports from the source update process and then holds
        on to them. When the build process is ready to read information we send what
        we have. Otherwise, we're waiting on the update process to send us something.

        This convoluted arrangement is required to allow the source update
        process to go from start to finish without undue interruption on it waiting
        to write out its status to the build process (which is usually busy).

        Args:
            ipc_to_build: the IPC object to use to send to build process.
            ipc_from_updater: the IPC object to use to receive from update process.

        Returns:
             0 on success, non-zero on failure.
        """
        msgs: list[bytes] = []  # Message queue.

        # We will write to the build process and read from the update process.

        send_fh = ipc_to_build.fh
        if not send_fh:
            raise KBRuntimeError("??? missing pipe to build proc")
        recv_fh = ipc_from_updater.fh
        if not recv_fh:
            raise KBRuntimeError("??? missing pipe from monitor")

        sel = selectors.DefaultSelector()
        sel.register(recv_fh, selectors.EVENT_READ)
        sel.register(send_fh, selectors.EVENT_WRITE)

        # Start the loop.  We will be waiting on either read or write ends.
        # Whenever select() returns we must check both sets.
        while len(sel.get_map()) == 2:  # the number of watched pipes is 2, when we unregister the read pipe, then we will write all the rest messages after the loop
            events = sel.select()

            for key, _ in events:  # events is a list of tuples
                # Check for source updates first.
                if key.fileobj == recv_fh:
                    try:
                        msg = ipc_from_updater.receive_message()
                    except Exception as e:
                        raise e

                    if msg == b"":  # means the other side is presumably done
                        sel.unregister(recv_fh)  # Select no longer needed, just output to build.
                        break
                    else:
                        msgs.append(msg)

                # Now check for build updates.
                if key.fileobj == send_fh:
                    # If we're here the update is still going.  If we have no messages
                    # to send wait for that first.
                    if not msgs:
                        pass
                    else:
                        # Send the message (if we got one).
                        while msgs:
                            if not ipc_to_build.send_message(msgs.pop(0)):
                                logger_taskmanager.error("r[mon]: Build process stopped too soon!")
                                return 1

        sel.unregister(send_fh)  # stop watching the write pipe
        # Send all remaining messages.
        for msg in msgs:
            if not ipc_to_build.send_message(msg):
                logger_taskmanager.error("r[mon]: Build process stopped too soon!")
                return 1
        return 0

    @staticmethod
    def _form_block_substring(module: Module) -> str:
        if module.is_kde_project():
            proj_metadata = module.context.projects_db.repositories[module.name]
            invent_path_list = proj_metadata["invent_name"].split("/")
            legacy_path = proj_metadata["full_name"]
            mod_output = "g[" + invent_path_list[0] + "]/g[" + invent_path_list[1] + "]" + f" ({legacy_path})"
        else:
            mod_output = "g[third-party]/g[" + module.name + "]"

        return mod_output
