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
from .util.textwrap_mod import dedent

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
        self.ksb_app = app
        self.DO_STOP = 0

    def run_all_tasks(self) -> int:
        """
        Return shell-style result code.

        This function is running only in main kde-builder process (kde-builder-build).
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

        This function could be run by both: main kde-builder process (kde-builder-build), and updater process (kde-builder-updater).

        Returns:
             0 on success, non-zero on error.
        """
        update_list: list[Module] = ctx.modules_in_phase("update")

        # No reason to print out the text if we're not doing anything.
        if not update_list:
            ipc.send_ipc_message(IPC.ALL_UPDATING, "update-list-empty")
            ipc.send_ipc_message(IPC.ALL_DONE, "update-list-empty")
            return 0

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
    def _build_single_module(ipc: IPC, ctx: BuildContext, module: Module) -> str:
        """
        Build the given module.

        This function is running only in main kde-builder process (kde-builder-build).

        Returns:
             The failure phase, or empty string on success.
        """
        module.reset_environment()

        # Cache module directories, e.g. to be consumed in kde-builder --run
        module.set_persistent_option("source-dir", module.fullpath("source"))
        module.set_persistent_option("build-dir", module.fullpath("build"))
        module.set_persistent_option("install-dir", module.installation_path())

        fail_count: int = module.get_persistent_option("failure-count") or 0
        result_status_of_update: str
        message: str
        result_status_of_update, message = ipc.wait_for_module(module)
        ipc.forget_module(module)

        module.set_build_system()  # After we downloaded source code, we can determine build system
        module.setup_environment()

        if result_status_of_update == "failed":
            logger_taskmanager.error(f"\tUnable to update r[{module}], build canceled.")
            fail_count += 1
            module.set_persistent_option("failure-count", fail_count)
            return "update"
        elif result_status_of_update == "success":
            logger_taskmanager.warning(f"\tSource update complete for g[{module}]: {message}")
        elif result_status_of_update == "skipped":
            logger_taskmanager.warning(f"\tNo changes to g[{module}] source code.")
            refresh_reason = module.build_system.needs_refreshed()

            if refresh_reason:
                logger_taskmanager.info(f"\tRebuilding because {refresh_reason}.")
            elif fail_count != 0:
                refresh_reason = "failed to build or update last time"
                logger_taskmanager.info(f"\tRebuilding because {refresh_reason}.")
            else:
                logger_taskmanager.warning(f"\tProceeding to build g[{module}].")

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

        This function is running only in main kde-builder process (kde-builder-build).

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

        logdir_latest = ctx.get_absolute_path("log-dir") + "/latest"
        logdir_timestamped = ctx.get_log_dir()

        status_list_log_timestamped = f"{logdir_timestamped}/status-list.log"
        status_list_log_latest = f"{logdir_latest}/status-list.log"

        screen_log_timestamped = f"{logdir_timestamped}/screen.log"
        screen_log_latest = f"{logdir_latest}/screen.log"

        successfully_built_log_timestamped = f"{logdir_timestamped}/successfully-built.log"
        successfully_built_log_latest = f"{logdir_latest}/successfully-built.log"
        failed_to_build_log_timestamped = f"{logdir_timestamped}/failed-to-build.log"
        failed_to_build_log_latest = f"{logdir_latest}/failed-to-build.log"
        failed_to_update_log_timestamped = f"{logdir_timestamped}/failed-to-update.log"
        failed_to_update_log_latest = f"{logdir_latest}/failed-to-update.log"

        if Debug().pretending():
            status_list_log_timestamped = "/dev/null"
            failed_to_build_log_timestamped = "/dev/null"
            failed_to_update_log_timestamped = "/dev/null"
            successfully_built_log_timestamped = "/dev/null"

        status_list_fh = open(status_list_log_timestamped, "w")
        failed_to_build_fh = open(failed_to_build_log_timestamped, "w")
        failed_to_update_fh = open(failed_to_update_log_timestamped, "w")
        successfully_build_fh = open(successfully_built_log_timestamped, "w")

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

            failed_phase: str = TaskManager._build_single_module(ipc, ctx, module)

            if failed_phase:
                # FAILURE
                ctx.mark_module_phase_failed(failed_phase, module)
                print(f"{module.name}: Failed to {failed_phase}.", file=status_list_fh)
                if failed_phase == "build":
                    print(module.name, file=failed_to_build_fh)
                if failed_phase == "update":
                    print(module.name, file=failed_to_update_fh)

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
                print(f"{module.name}: Succeeded.", file=status_list_fh)
                print(f"{module.name}", file=successfully_build_fh)
                build_done.append(module_name)  # Make it show up as a success
                status_viewer.number_modules_succeeded(1 + status_viewer.number_modules_succeeded())
            cur_module += 1
            print()  # Space things out

        status_list_fh.close()
        failed_to_build_fh.close()
        failed_to_update_fh.close()
        successfully_build_fh.close()

        if not Debug().pretending():
            if os.path.exists(status_list_log_latest):
                os.remove(status_list_log_latest)
            os.symlink(status_list_log_timestamped, status_list_log_latest)

            if os.path.exists(screen_log_latest):
                os.remove(screen_log_latest)
            os.symlink(screen_log_timestamped, screen_log_latest)

            if os.path.exists(failed_to_build_log_latest):
                os.remove(failed_to_build_log_latest)
            os.symlink(failed_to_build_log_timestamped, failed_to_build_log_latest)

            if os.path.exists(failed_to_update_log_latest):
                os.remove(failed_to_update_log_latest)
            os.symlink(failed_to_update_log_timestamped, failed_to_update_log_latest)

            if os.path.exists(successfully_built_log_latest):
                os.remove(successfully_built_log_latest)
            os.symlink(successfully_built_log_timestamped, successfully_built_log_latest)

        if len(build_done) > 0:
            logger_taskmanager.info("g[<<<  PROJECTS SUCCESSFULLY BUILT  >>>]")
            logger_taskmanager.info("g[" + "]\ng[".join(build_done) + "]")

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

        This function is running only in main kde-builder process (kde-builder-build).

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
    def _handle_monitoring(ipc_to_build: IPCPipe, ipc_from_updater: IPCPipe) -> int:
        """
        Handle monitoring process when using :class:`IPCPipe`.

        It reads in all status reports from the source update process and then holds
        on to them. When the build process is ready to read information we send what
        we have. Otherwise, we're waiting on the update process to send us something.

        This convoluted arrangement is required to allow the source update
        process to go from start to finish without undue interruption on it waiting
        to write out its status to the build process (which is usually busy).

        This function is running only in monitor kde-builder process (kde-builder-monitor).

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
            mod_output = "g[" + invent_path_list[0] + "]/g[" + invent_path_list[1] + "]"
        else:
            mod_output = "g[third-party]/g[" + module.name + "]"

        return mod_output
