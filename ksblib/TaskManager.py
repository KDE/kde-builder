import os.path
import sys
from urllib.parse import urlparse
import textwrap
import time
import signal
import setproctitle
from .Util.Conditional_Type_Enforced import conditional_type_enforced
import selectors
from .Debug import Debug
from .IPC.IPC import IPC
from .IPC.Pipe import IPC_Pipe
from .IPC.Null import IPC_Null
from .Util.Util import Util
from .BuildException import BuildException


@conditional_type_enforced
class TaskManager:
    """
    =head1 SYNOPSIS
    
     assert_isa($app, 'ksb::Application');
     my $mgr = ksb::TaskManager->new($app);
    
     # build context must be setup first
     my $result = eval { $mgr->runAllTasks(); }
    
     # all module updates/builds/etc. complete
    
    =head1 DESCRIPTION
    
    This module consolidates the actual orchestration of all the module update,
    buildsystem setup, configure, build, and install jobs once the
    L<ksb::Application> has setup the L<ksb::BuildContext> for the current build.
    
    In particular, the concurrent portion of the build is concentrated more-or-less
    entirely within "runAllTasks", although other parts of the script have to be
    aware of concurrency.
    """
    
    def __init__(self, app):
        from .Application import Application
        Util.assert_isa(app, Application)
        
        self.ksb_app = app
        self.DO_STOP = 0
    
    def runAllTasks(self):
        """
        returns shell-style result code
        """
        # What we're going to do is fork another child to perform the source
        # updates while we build.  Setup for this first by initializing some
        # shared memory.
        ctx = self.ksb_app.context
        result = 0
        ipc = None
        
        def updateOptsSub(modName, k, v):
            ctx.setPersistentOption(modName, k, v)
        
        if ctx.usesConcurrentPhases() and ctx.getOption("async"):
            ipc = IPC_Pipe()
        else:
            ipc = IPC_Null()
        
        ipc.setPersistentOptionHandler(updateOptsSub)
        
        if ipc.supportsConcurrency():
            result = self._handle_async_build(ipc, ctx)
            if Debug().debugging():
                ipc.outputPendingLoggedMessages()
        else:
            Debug().whisper("Using no IPC mechanism\n")
            
            # If the user sends SIGHUP during the build, we should allow the
            # current module to complete and then exit early.
            def handle_sighup(signum, frame):
                print("[noasync] recv SIGHUP, will end after this module")
                global DO_STOP
                DO_STOP = 1
            
            signal.signal(signal.SIGHUP, handle_sighup)
            
            Debug().note("\n b[<<<  Update Process  >>>]\n")
            result = self._handle_updates(ipc, ctx)
            
            Debug().note(" b[<<<  Build Process  >>>]\n")
            result = self._handle_build(ipc, ctx) or result
        
        return result
    
    # Internal API
    
    def _handle_updates(self, ipc, ctx) -> int:
        """
        Subroutine to update a list of modules.
        
        Parameters:
        1. IPC module to pass results to.
        2. Build Context, which will be used to determine the module update list.
        
        The ipc parameter contains an object that is responsible for communicating
        the status of building the modules.  This function must account for every
        module in $ctx's update phase to the ipc object before returning.
        
        Returns 0 on success, non-zero on error.
        """
        update_list = ctx.modulesInPhase("update")
        
        # No reason to print out the text if we're not doing anything.
        if not update_list:
            ipc.sendIPCMessage(IPC.ALL_UPDATING, "update-list-empty")
            ipc.sendIPCMessage(IPC.ALL_DONE, "update-list-empty")
            return 0
        
        if not self._check_for_ssh_agent(ctx):
            ipc.sendIPCMessage(IPC.ALL_FAILURE, "ssh-failure")
            return 1
        
        kdesrc = ctx.getSourceDir()
        if not os.path.exists(kdesrc):
            Debug().whisper("KDE source download directory doesn't exist, creating.\n")
            
            if not Util.super_mkdir(kdesrc):
                Debug().error(f"Unable to make directory r[{kdesrc}]!")
                ipc.sendIPCMessage(IPC.ALL_FAILURE, "no-source-dir")
                return 1
        
        # Once at this point, any errors we get should be limited to a module,
        # which means we can tell the build thread to start.
        ipc.sendIPCMessage(IPC.ALL_UPDATING, "starting-updates")
        
        hadError = 0
        for module in update_list:
            if self.DO_STOP:
                Debug().note(" y[b[* * *] Early exit requested, aborting updates.")
                break
            
            ipc.setLoggedModule(module.name)
            
            # Note that this must be in this order to avoid accidentally not
            # running ->update() from short-circuiting if an error is noted.
            hadError = not module.update(ipc, ctx) or hadError
            
            # Cache module directories, e.g. to be consumed in kde-builder --run
            # This is needed for --no-async mode where the buildSingleModule won't run
            # But the other one is needed for --async mode since persistent options
            # only work from within the build process
            module.setPersistentOption("source-dir", module.fullpath("source"))
        
        ipc.sendIPCMessage(IPC.ALL_DONE, f"had_errors: {hadError}")
        return hadError
    
    @staticmethod
    def _buildSingleModule(ipc, ctx, module, startTimeRef):
        """
        Builds the given module.
        
        Return value is the failure phase, or 0 on success.
        """
        ctx.resetEnvironment()
        module.setupEnvironment()
        
        # Cache module directories, e.g. to be consumed in kde-builder --run
        module.setPersistentOption("source-dir", module.fullpath("source"))
        module.setPersistentOption("build-dir", module.fullpath("build"))
        module.setPersistentOption("install-dir", module.installationPath())
        
        fail_count = module.getPersistentOption("failure-count") or 0
        resultStatus, message = ipc.waitForModule(module)
        ipc.forgetModule(module)
        
        if resultStatus == "failed":
            Debug().error(f"\tUnable to update r[{module}], build canceled.")
            fail_count += 1
            module.setPersistentOption("failure-count", fail_count)
            return "update"
        elif resultStatus == "success":
            Debug().note(f"\tSource update complete for g[{module}]: {message}")
            whyRefresh = ipc.refreshReasonFor(module.name)
            if whyRefresh:
                Debug().info(f"\t  Rebuilding because {whyRefresh}")
        
        # Skip actually building a module if the user has selected to skip
        # builds when the source code was not actually updated. But, don't skip
        # if we didn't successfully build last time.
        elif resultStatus == "skipped" and not module.getOption("build-when-unchanged") and fail_count == 0:
            Debug().note(f"\tSkipping g[{module}] because its source code has not changed.")
            return 0
        elif resultStatus == "skipped":
            Debug().note(f"\tNo changes to g[{module}] source code, but proceeding to build anyway.")
        
        # If the build gets interrupted, ensure the persistent options that are
        # written reflect that the build failed by preemptively setting the future
        # value to write. If the build succeeds we'll reset to 0 then.
        module.setPersistentOption("failure-count", fail_count + 1)
        
        startTimeRef = time.time()
        if module.build():
            module.setPersistentOption("failure-count", 0)
            return 0
        return "build"  # phase failed at
    
    def _handle_build(self, ipc, ctx) -> int:
        """
        Subroutine to handle the build process.
        
        Parameters:
        1. IPC object to receive results from.
        2. Build Context, which is used to determine list of modules to build.
        
        If the packages are not already checked-out and/or updated, this
        subroutine WILL NOT do so for you.
        
        This subroutine assumes that the source directory has already been set up.
        It will create the build directory if it doesn't already exist.
        
        If $builddir/$module/.refresh-me exists, the subroutine will
        completely rebuild the module (as if --refresh-build were passed for that
        module).
        
        Returns 0 for success, non-zero for failure.
        """
        modules = ctx.modulesInPhase("build")
        
        # No reason to print building messages if we're not building.
        if not modules:
            return 0
        
        # IPC queue should have a message saying whether or not to bother with the
        # build.
        ipc.waitForStreamStart()
        ctx.unsetPersistentOption("global", "resume-list")
        
        if Debug().pretending():
            outfile = "/dev/null"
        else:
            outfile = ctx.getLogDir() + "/build-status"
        
        try:
            status_fh = open(outfile, "w")
        except OSError:
            Debug().error(textwrap.dedent(f"""\
             r[b[*] Unable to open output status file r[b[{outfile}]
             r[b[*] You won't be able to use the g[--resume] switch next run.
            """))
            outfile = None
        
        build_done = []
        result = 0
        
        cur_module = 1
        num_modules = len(modules)
        
        statusViewer = ctx.statusViewer()
        statusViewer.numberModulesTotal(num_modules)
        
        while modules:
            module = modules.pop(0)
            if self.DO_STOP:
                Debug().note(" y[b[* * *] Early exit requested, aborting updates.")
                break
            
            moduleName = module.name
            moduleSet = module.moduleSet().name
            modOutput = moduleName
            
            if Debug().debugging(Debug.WHISPER):
                sysType = module.buildSystemType()
                modOutput += f" (build system {sysType})"
            
            if moduleSet:
                moduleSet = f" from g[{moduleSet}]"
            
            Debug().note(f"Building g[{modOutput}]{moduleSet} ({cur_module}/{num_modules})")
            
            start_time = int(time.time())
            failedPhase = TaskManager._buildSingleModule(ipc, ctx, module, start_time)
            elapsed = Util.prettify_seconds(int(time.time()) - start_time)
            
            if failedPhase:
                # FAILURE
                ctx.markModulePhaseFailed(failedPhase, module)
                print(f"{module}: Failed on {failedPhase} after {elapsed}.", file=status_fh)
                
                if result == 0:
                    # No failures yet, mark this as resume point
                    moduleList = ", ".join([f"{elem}" for elem in [module] + modules])
                    ctx.setPersistentOption("global", "resume-list", moduleList)
                result = 1
                
                if module.getOption("stop-on-failure"):
                    Debug().note(f"\n{module} didn't build, stopping here.")
                    return 1  # Error
                
                statusViewer.numberModulesFailed(1 + statusViewer.numberModulesFailed())
            else:
                # Success
                print(f"{module}: Succeeded after {elapsed}.", file=status_fh)
                build_done.append(moduleName)  # Make it show up as a success
                statusViewer.numberModulesSucceeded(1 + statusViewer.numberModulesSucceeded())
            cur_module += 1
            print()  # Space things out
        
        if outfile:
            status_fh.close()
            
            # Update the symlink in latest to point to this file.
            logdir = ctx.getSubdirPath("log-dir")
            statusFileLoc = f"{logdir}/latest/build-status"
            if os.path.islink(statusFileLoc):
                Util.safe_unlink(statusFileLoc)
            
            if not os.path.exists(statusFileLoc):  # pl2py: in perl the os.symlink does not overwrite the existing symlink and returns success
                try:
                    os.symlink(outfile, statusFileLoc)
                except FileNotFoundError:
                    # pl2py: In perl they just ignore the case when the symlink was not successfully created.
                    # This case may happen when you do not have a source directory (the log directory that will contain a symlink),
                    # and do pretending. In pretending, the real log file is /dev/null.
                    # So os.symlink will try to symlink "/home/username/kde/src/log/latest/build-status" to "/dev/null" when "/home/username/kde" dir does not exist.
                    # We also will ignore that.
                    pass
        
        if len(build_done) > 0:
            Debug().info("<<<  g[PACKAGES SUCCESSFULLY BUILT]  >>>")
        
        successes = len(build_done)
        if successes == 1:
            mods = "module"
        else:
            mods = "modules"
        
        if not Debug().pretending():
            # Print out results, and output to a file
            kdesrc = ctx.getSourceDir()
            
            built = open(f"{kdesrc}/successfully-built", "w")
            for module in build_done:
                if successes <= 10:
                    Debug().info(f"{module}")
                print(f"{module}", file=built)
            built.close()
            
            if successes > 10:
                Debug().info(f"Built g[{successes}] {mods}")
        else:
            # Just print out the results
            if successes <= 10:
                Debug().info("g[", "]\ng[".join(build_done), "]")
            else:
                if successes > 10:
                    Debug().info(f"Built g[{successes}] {mods}")
        return result
    
    def _handle_async_build(self, ipc, ctx) -> int:
        """
        This subroutine special-cases the handling of the update and build phases, by
        performing them concurrently (where possible), using forked processes.
        
        Only one thread or process of execution will return from this procedure. Any
        other processes will be forced to exit after running their assigned module
        phase(s).
        
        We also redirect ksb::Debug output messages to be sent to a single process
        for display on the terminal instead of allowing them all to interrupt each
        other.
        
        Parameters:
        1. IPC Object to use for sending/receiving update/build status. It must be
        an object type that supports IPC concurrency (e.g. IPC::Pipe).
        2. Build Context to use, from which the module lists will be determined.
        
        Returns 0 on success, non-zero on failure.
        """
        # The exact method for async is that two children are forked.  One child
        # is a source update process.  The other child is a monitor process which will
        # hold status updates from the update process so that the updates may
        # happen without waiting for us to be ready to read.
        
        print()  # Space out from metadata messages.
        
        # Before we fork we should pre-calculate where the logs will go so that the
        # children do not try to do the same calculation independently because they
        # didn't know it's already been figured out.
        for module in ctx.moduleList():
            module.getLogDir()
        
        result = 0
        monitorPid = os.fork()
        updaterPid = None
        
        if monitorPid == 0:
            # child
            updaterToMonitorIPC = IPC_Pipe()
            updaterPid = os.fork()
            
            def sigint_handler(sig, frame):
                sys.exit(signal.SIGINT)
            
            signal.signal(signal.SIGINT, sigint_handler)
            
            if updaterPid == 0:
                # child of monitor
                # If the user sends SIGHUP during the build, we should allow the
                # current module to complete and then exit early.
                def sighup_handler(signum, frame):
                    print("[updater] recv SIGHUP, will end after this module")
                    self.DO_STOP = 1
                
                signal.signal(signal.SIGHUP, sighup_handler)
                
                setproctitle.setproctitle("kde-builder-updater")
                updaterToMonitorIPC.setSender()
                Debug().setIPC(updaterToMonitorIPC)
                
                sys.exit(self._handle_updates(updaterToMonitorIPC, ctx))
            else:
                # still monitor
                # If the user sends SIGHUP during the build, we should allow the
                # current module to complete and then exit early.
                def sighup_handler(signum, frame):
                    print("[monitor] recv SIGHUP, will end after this module")
                    
                    # If we haven't recv'd yet, forward to monitor in case user didn't
                    # send to process group
                    if not self.DO_STOP:
                        os.kill(updaterPid, signal.SIGHUP)
                    self.DO_STOP = 1
                
                signal.signal(signal.SIGHUP, sighup_handler)
                
                setproctitle.setproctitle("kde-builder-monitor")
                ipc.setSender()
                updaterToMonitorIPC.setReceiver()
                
                ipc.setLoggedModule("#monitor#")  # This /should/ never be used...
                Debug().setIPC(ipc)
                
                exitcode = self._handle_monitoring(ipc, updaterToMonitorIPC)
                time.sleep(5)  # pl2py give some time to be sure updater pid will be finished, otherwise we could falsely write error message
                pid, status = os.waitpid(updaterPid, os.WNOHANG)
                if pid == 0:
                    Debug().error(" r[b[***] updater thread is finished but hasn't exited?!?")
                
                sys.exit(exitcode)
        else:
            # Still the parent, let's do the build.
            
            # If the user sends SIGHUP during the build, we should allow the current
            # module to complete and then exit early.
            def signal_handler(signum, frame):
                print("[ build ] recv SIGHUP, will end after this module")
                
                # If we haven't recv'd yet, forward to monitor in case user didn't
                # send to process group
                if not self.DO_STOP:
                    os.kill(monitorPid, signal.SIGHUP)
                self.DO_STOP = 1
            
            signal.signal(signal.SIGHUP, signal_handler)
            
            setproctitle.setproctitle("kde-builder-build")
            ipc.setReceiver()
            result = self._handle_build(ipc, ctx)
        
        ipc.waitForEnd()
        ipc.close()
        
        # Display a message for updated modules not listed because they were not
        # built.
        unseenModulesRef = ipc.unacknowledgedModules()
        if unseenModulesRef:
            # The only current way we should get unacknowledged modules is if the
            # build thread manages to end earlier than the update thread.  This
            # should only happen under --stop-on-failure if an early build fails.
            #
            # If an update fails the message will still be printed to the user, so
            # we don't need to note it separately here, and there's no need to list
            # one-by-one the modules that successfully updated.
            Debug().whisper("Some modules were updated but not built")
        
        # It's possible if build fails on first module that git is still
        # running. Make it stop too.
        pid, status = os.waitpid(monitorPid, os.WNOHANG)
        if pid == 0:
            os.kill(monitorPid, signal.SIGINT)
            
            # Exit code is in $?.
            pid, status = os.waitpid(monitorPid, 0)
            result = 1 if os.WEXITSTATUS(status) != 0 else 0
        return result
    
    @staticmethod
    def _check_for_ssh_agent(ctx):
        """
        Checks if we are supposed to use ssh agent by examining the environment, and
        if so checks if ssh-agent has a list of identities.  If it doesn't, we run
        ssh-add (with no arguments) and inform the user.  This can be controlled with
        the disable-agent-check parameter.
        
        Parameters:
        1. Build context
        """
        # Don't bother with all this if the user isn't even using SSH.
        if Debug().pretending():
            return True
        if ctx.getOption("disable-agent-check"):
            return True
        
        gitServers = [module for module in ctx.modulesInPhase("update") if module.scmType() == "git"]
        
        sshServers = []
        for gitserver in gitServers:
            if url := urlparse(gitserver.getOption("repository")):  # Check for git+ssh:// or git@git.kde.org:/path/etc.
                if url.scheme == "git+ssh" or url.username == "git" and url.hostname == "git.kde.org":
                    sshServers.append(gitserver)
        
        if not sshServers:
            return True
        Debug().whisper("\tChecking for SSH Agent")
        
        # We're using ssh to download, see if ssh-agent is running.
        if "SSH_AGENT_PID" not in os.environ:
            return True
        
        pid = os.environ.get("SSH_AGENT_PID")
        
        # It's supposed to be running, let's see if there exists the program with
        # that pid (this check is linux-specific at the moment).
        if os.path.isdir("/proc") and not os.path.exists(f"/proc/{pid}"):
            # local $" = ', '; # override list interpolation separator
            
            Debug().warning(textwrap.dedent(f"""\
                y[b[ *] SSH Agent is enabled, but y[doesn't seem to be running].
                y[b[ *] The agent is needed for these modules:
                y[b[ *]   b[{sshServers}]
                y[b[ *] Please check that the agent is running and its environment variables defined
                """))
            return False
        
        # The agent is running, but does it have any keys?  We can't be more specific
        # with this check because we don't know what key is required.
        noKeys = 0
        
        def noKeys_filter(_):
            nonlocal noKeys
            if not noKeys:
                noKeys = "no identities"
        
        Util.filter_program_output(noKeys_filter, "ssh-add", "-l")
        
        if not noKeys:
            return True
        
        print(Debug().colorize(textwrap.dedent("""\
            b[y[*] SSH Agent does not appear to be managing any keys.  This will lead to you
            being prompted for every module update for your SSH passphrase.  So, we're
            running g[ssh-add] for you.  Please type your passphrase at the prompt when
            requested, (or simply Ctrl-C to abort the script).
            """)))
        commandLine = ["ssh-add"]
        identFile = ctx.getOption("ssh-identity-file")
        if identFile:
            commandLine.append(identFile)
        result = os.system(commandLine)
        
        # Run this code for both death-by-signal and nonzero return
        if result:
            rcfile = ctx.rcFile()
            print(Debug().colorize(textwrap.dedent(f"""

                y[b[*] Unable to add SSH identity, aborting.
                y[b[*] If you don't want kde-builder to check in the future,
                y[b[*] Set the g[disable-agent-check] option to g[true] in your {rcfile}.
            
                """)))
            return False
        return True
    
    @staticmethod
    def _handle_monitoring(ipcToBuild, ipcFromUpdater) -> int:
        """
        This is the main subroutine for the monitoring process when using IPC::Pipe.
        It reads in all status reports from the source update process and then holds
        on to them.  When the build process is ready to read information we send what
        we have.  Otherwise we're waiting on the update process to send us something.
        
        This convoluted arrangement is required to allow the source update
        process to go from start to finish without undue interruption on it waiting
        to write out its status to the build process (which is usually busy).
        
        Parameters:
        1. the IPC object to use to send to build process.
        2. the IPC object to use to receive from update process.
        
        Returns 0 on success, non-zero on failure.
        """
        msgs = []  # Message queue.
        
        # We will write to the build process and read from the update process.
        
        sendFH = ipcToBuild.fh or BuildException.croak_runtime('??? missing pipe to build proc')
        recvFH = ipcFromUpdater.fh or BuildException.croak_runtime('??? missing pipe from monitor')
        
        sel = selectors.DefaultSelector()
        sel.register(recvFH, selectors.EVENT_READ)
        sel.register(sendFH, selectors.EVENT_WRITE)
        
        # Start the loop.  We will be waiting on either read or write ends.
        # Whenever select() returns we must check both sets.
        while len(sel.get_map()) == 2:  # the number of watched pipes is 2, when we unregister the read pipe, then we will write all the rest messages after the loop
            events = sel.select()
            
            for key, _ in events:  # events is a list of tuples
                # Check for source updates first.
                if key.fileobj == recvFH:
                    try:
                        msg = ipcFromUpdater.receiveMessage()
                    except Exception as e:
                        raise e
                    
                    if msg == b"":  # means the other side is presumably done
                        sel.unregister(recvFH)  # Select no longer needed, just output to build.
                        break
                    else:
                        msgs.append(msg)
                
                # Now check for build updates.
                if key.fileobj == sendFH:
                    # If we're here the update is still going.  If we have no messages
                    # to send wait for that first.
                    if not msgs:
                        pass
                    else:
                        # Send the message (if we got one).
                        while msgs:
                            if not ipcToBuild.sendMessage(msgs.pop(0)):
                                Debug().error("r[mon]: Build process stopped too soon!")
                                return 1
        
        sel.unregister(sendFH)  # stop watching the write pipe
        # Send all remaining messages.
        for msg in msgs:
            if not ipcToBuild.sendMessage(msg):
                Debug().error("r[mon]: Build process stopped too soon!")
                return 1
        ipcToBuild.close()
        return 0
