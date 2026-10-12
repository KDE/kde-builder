# SPDX-FileCopyrightText: 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import logging
import multiprocessing
import os.path
import signal
import sys
from typing import TYPE_CHECKING

import kde_builder
from kde_builder.ipc.ipc import IPC
from kde_builder.ipc.null import IPCNull
from kde_builder.ipc.pipe import IPCPipe
from kde_builder.kb_logging import IPCQueueLoggingHandler
from kde_builder.util.setproctitle_mod import setproctitle
from kde_builder.util.util import Util

if TYPE_CHECKING:
    from kde_builder.application import Application
    from kde_builder.build_context import BuildContext
    from kde_builder.module.module import Module

logger_ipc = logging.getLogger("ipc")
logger_taskmanager = logging.getLogger("taskmanager")


class TaskManager:
    """
    Orchestrates source update, build, and install tasks described in :class:`BuildContext`.

    The detailed list of tasks includes module update, build_system setup, configure, build, and
    install jobs. The :class:`Application` sets up a :class:`BuildContext` for the current build.
    """

    DO_STOP = 0

    def __init__(self, app: Application):
        self.ksb_app = app

    def run_all_tasks(self) -> int:
        """
        Return shell-style result code.

        This function is running only in main kde-builder process (kde-builder-build).
        """
        ctx = self.ksb_app.context
        result = 0
        ipc = None

        if ctx.uses_concurrent_phases() and ctx.get_option("async"):
            ipc = IPCPipe()
        else:
            ipc = IPCNull()

        if ipc.supports_concurrency():
            result = self._handle_async_build(ipc, ctx)
            if logger_ipc.level == logging.DEBUG:
                ipc.output_pending_logged_messages()
        else:
            result = self._handle_noasync_build(ipc, ctx)

        for ipc_module_name in ipc.persistent_opts:
            for item in ipc.persistent_opts[ipc_module_name]:
                ctx.set_persistent_option(ipc_module_name, item[0], item[1])

        ctx.status_view.progress_bar_disable()
        return result

    # Internal API

    @staticmethod
    def _handle_updates(ipc: IPC, ctx: BuildContext) -> int:
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
            if TaskManager.DO_STOP:
                logger_taskmanager.warning(" y[b[* * *] Early exit requested, aborting updates.")
                break

            ipc.set_logged_module(module.name)

            if not ipc.supports_concurrency():
                block_substr = TaskManager._form_block_substring(module)
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
    def _build_single_module(ipc: IPC, module: Module) -> str:
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

        if not module.build():
            return "build"  # phase failed at

        has_custom_targets = module.get_option("targets")
        if has_custom_targets:
            module.set_persistent_option("failure-count", 0)
            return ""  # Do not continue with normal installation.

        if not module.phases.has("install"):
            logger_taskmanager.info("\tSkipping install due to disabled install phase.")
            module.set_persistent_option("failure-count", 0)
            return ""

        # Clear the progress values after build process, so they do not influence on initial progress of install process.
        # This is needed because the install() is invoked after build().
        module.context.status_view.reset_progress()

        if not module.install():
            return "install"  # phase failed at

        module.set_persistent_option("failure-count", 0)
        return ""

    @staticmethod
    def _handle_build(ipc: IPC, ctx: BuildContext) -> int:
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
        completely rebuild the module (as if --clean-build were passed for that
        module).

        This function is running only in main kde-builder process (kde-builder-build).

        Returns:
             0 for success, non-zero for failure.
        """
        modules: list[Module] = ctx.modules_in_phase("build")

        # No reason to print building messages if we're not building.
        if not modules:
            return 0

        if ctx.get_option("clean-build-first"):
            modules[0].set_option("clean-build", True)

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

        if kde_builder.is_pretending:
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
        status_viewer.mod_total = num_modules

        while modules:
            module = modules.pop(0)
            if TaskManager.DO_STOP:
                logger_taskmanager.warning(" y[b[* * *] Early exit requested, cancelling build of further projects.")
                break

            module_name = module.name
            block_substr = TaskManager._form_block_substring(module)
            logger_taskmanager.warning(f"Building {block_substr} ({cur_module}/{num_modules})")
            status_viewer.mod_current = cur_module
            status_viewer.reset_progress()  # Resetting previous project's progress
            status_viewer.progress_bar_update()

            failed_phase: str = TaskManager._build_single_module(ipc, module)

            if failed_phase:
                # FAILURE
                ctx.mark_module_phase_failed(failed_phase, module)
                print(f"{module.name}: Failed to {failed_phase}.", file=status_list_fh)
                if failed_phase == "build" or failed_phase == "install":
                    print(module.name, file=failed_to_build_fh)
                if failed_phase == "update":
                    print(module.name, file=failed_to_update_fh)

                if result == 0:
                    # No failures yet, mark this as resume point
                    module_list: list[str] = [str(elem) for elem in (module, *modules)]
                    ctx.set_persistent_option("global", "resume-list", module_list)
                result = 1

                if module.get_option("stop-on-failure"):
                    logger_taskmanager.warning(f"\n{module} didn't build, stopping here.")
                    result = 1
                    break

                logfile = module.get_option("#error-log-file")

                # Async updates do not send setting "#error-log-file" option over IPC.
                # But if the failed command was run via run_logged() (that is not always),
                # then the set_error_logfile() was invoked, which created error.log symlink.
                if not logfile:
                    error_log = module.get_log_dir() + "/error.log"
                    if os.path.exists(error_log):
                        logfile = os.path.realpath(error_log)
                    else:
                        logfile = "No log file"
                logger_taskmanager.info("\tError log: r[" + logfile)
                status_viewer.mod_failed += 1
            else:
                # Success
                print(f"{module.name}: Succeeded.", file=status_list_fh)
                print(f"{module.name}", file=successfully_build_fh)
                build_done.append(module_name)  # Make it show up as a success
                status_viewer.mod_success += 1
            cur_module += 1
            logger_taskmanager.warning("")  # Space between "Building project/name (n/n)" blocks

        status_list_fh.close()
        failed_to_build_fh.close()
        failed_to_update_fh.close()
        successfully_build_fh.close()

        if not kde_builder.is_pretending:
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

    def _handle_noasync_build(self, ipc: IPCNull, ctx) -> int:
        logger_taskmanager.debug("Using no IPC mechanism\n")

        # If the user sends SIGHUP during the build, we should allow the
        # current module to complete and then exit early.
        def handle_sighup(signum, frame):
            print("[noasync] recv SIGHUP, will end after this project")
            TaskManager.DO_STOP = 1

        signal.signal(signal.SIGHUP, handle_sighup)

        logger_taskmanager.warning("\n b[<<<  Update Process  >>>]\n")
        result: int = TaskManager._handle_updates(ipc, ctx)

        logger_taskmanager.warning(" b[<<<  Build Process  >>>]\n")
        result: int = TaskManager._handle_build(ipc, ctx) or result

        return result

    def _handle_async_build(self, ipc: IPCPipe, ctx: BuildContext) -> int:
        """
        Special-cases the handling of the update and build phases, by performing them concurrently (where possible).

        Only one thread or process of execution will return from this procedure. Any
        other processes will be forced to exit after running their assigned module
        phase(s).

        This function is running only in main kde-builder process (kde-builder-build).

        Args:
            ipc: IPC Object to use for sending/receiving update/build status. It must be
                an object type that supports IPC concurrency (e.g. IPCPipe).
            ctx: Build Context to use, from which the module lists will be determined.

        Returns:
             0 on success, non-zero on failure.
        """
        print()  # Space out from metadata messages.

        # Before we run updater subprocess, we should pre-calculate where the logs will go so that the
        # children do not try to do the same calculation independently because they
        # didn't know it's already been figured out.
        for module in ctx.modules:
            module.get_log_dir()

        result = 0

        def updater_entrypoint(ipc_obj, ctx_obj):
            setproctitle("kde-builder-updater")

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
                print(f"[updater process] recv SIGHUP, will end after updating {ipc_obj.logged_module} project.")
                TaskManager.DO_STOP = 1

            signal.signal(signal.SIGHUP, sighup_handler)

            root_logger = logging.getLogger()
            root_logger.handlers.clear()
            root_logger.addHandler(IPCQueueLoggingHandler(ipc_obj))

            exitcode = TaskManager._handle_updates(ipc_obj, ctx)
            # print("Updater process exiting with code", exitcode)
            sys.exit(exitcode)

        updater_process = multiprocessing.Process(
            target=updater_entrypoint,
            args=(ipc, ctx)
        )
        updater_process.start()

        setproctitle("kde-builder-build")

        # If the user sends SIGHUP during the build, we should allow the current
        # module to complete and then exit early.
        def signal_handler(signum, frame):
            print("[build process] recv SIGHUP, will end after this project")

            # If we haven't received yet, forward to updater in case user didn't
            # send to process group
            if not TaskManager.DO_STOP:
                os.kill(updater_process.pid, signal.SIGHUP)
            TaskManager.DO_STOP = 1

        signal.signal(signal.SIGHUP, signal_handler)

        result: int = TaskManager._handle_build(ipc, ctx)

        if result and ctx.get_option("stop-on-failure"):
            # It's possible if build fails on some near-first module, and returned because of stop-on-failure option, the git update process may still be running.
            # We will ask updater to finish gracefully.

            # print("Asking to stop updates gracefully")
            os.kill(updater_process.pid, signal.SIGHUP)

        ipc.wait_for_end()

        # Display a message for updated modules not listed because they were not
        # built.
        unseen_modules: dict[str, str] = ipc.unacknowledged_modules()
        if unseen_modules:
            # The only current way we should get unacknowledged modules is if the
            # build thread manages to end earlier than the update thread.  This
            # should only happen under --stop-on-failure if an early build fails.
            #
            # If an update fails the message will still be printed to the user, so
            # we don't need to note it separately here, and there's no need to list
            # one-by-one the modules that successfully updated.
            logger_taskmanager.debug("Some projects were updated but not built")

        updater_process.join()
        if updater_process.exitcode != 0:
            result = 1

        ipc.close()
        return result

    @staticmethod
    def _form_block_substring(module: Module) -> str:
        if module.is_kde_project():
            proj_metadata = module.context.projects_db.repositories[module.name]
            invent_path_list = proj_metadata["invent_name"].split("/")
            mod_output = "g[" + invent_path_list[0] + "]/g[" + invent_path_list[1] + "]"
        else:
            mod_output = "g[third-party]/g[" + module.name + "]"

        return mod_output
