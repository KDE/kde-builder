import os
import re
import subprocess
import textwrap
import time
from .Util.Conditional_Type_Enforced import conditional_type_enforced
from typing import NoReturn

from .OSSupport import OSSupport
from .BuildException import BuildException
from .BuildContext import BuildContext
from .Debug import Debug


@conditional_type_enforced
class FirstRun:
    """
    DESCRIPTION
    
    Performs initial-install setup, implementing the ``--initial-setup`` option.
    
    SYNOPSIS
    ::
    
        exitcode = ksblib.FirstRun.setupUserSystem()
        exit(exitcode)
    """
    
    def __init__(self):
        self.oss = OSSupport()
        self.baseDir = None
        self.supportedDistros = ["alpine", "arch", "debian", "fedora", "gentoo", "mageia", "opensuse"]  # Debian handles Ubuntu also
        self.supportedOtherOS = ["freebsd"]
    
    def setupUserSystem(self, baseDir, setup_steps: list) -> NoReturn:
        self.baseDir = baseDir
        
        try:
            if "install-distro-packages" in setup_steps:
                print(Debug().colorize("=== install-distro-packages ==="))
                
                # The distro dependencies are listed in sysadmin/repo-metadata repository
                # First, we need to download metadata with Application.
                
                from .Application import Application
                Application(["--metadata-only", "--metadata-only"])  # invokes _downloadKDEProjectMetadata internally
                # We use a hack to catch exactly this command line to make the app not exit. This way we do not influence the normal behavior, and we
                # do not create a normal instance of Application, because it will create a lockfile.
                # todo remove this hack after moving takeLock to another place before actual work from the Application::new
                
                metadata_distro_deps_path = os.environ.get("XDG_STATE_HOME", os.environ["HOME"] + "/.local/state") + "/sysadmin-repo-metadata/distro-dependencies"
                self._installSystemPackages(metadata_distro_deps_path)
            if "generate-config" in setup_steps:
                print(Debug().colorize("=== generate-config ==="))
                self._setupBaseConfiguration()
        except BuildException as e:
            msg = e.message
            print(Debug().colorize(f"  b[r[*] r[{msg}]"))
            exit(1)
        
        exit(0)
    
    # Internal functions
    
    @staticmethod
    def _readPackages(vendor, version, deps_data_path) -> dict:
        """
        Reads from the files from data/pkg and dumps the contents in a hash keyed by filename (the "[pkg/vendor/version]" part between each resource)
        """
        packages = {}
        cur_key = ""
        with open(f"{deps_data_path}/{vendor}.ini", "r") as file:
            while line := file.readline():
                line = line.removesuffix("\n")
                if match := re.match(r"^\[ *([^ ]+) *]$", line):
                    cur_key = match.group(1)
                    packages[cur_key] = []
                    continue
                if line.startswith("#") or line == "":
                    continue
                packages[cur_key].append(line)
        return packages
    
    @staticmethod
    def _throw(msg: str) -> NoReturn:
        raise BuildException.make_exception("Setup", msg)
    
    def _installSystemPackages(self, deps_data_path) -> None:
        
        vendor = self.oss.vendorID()
        osVersion = self.oss.vendorVersion()
        
        print(Debug().colorize(f" b[-] Installing b[system packages] for b[{vendor}]..."))
        
        packages = self._findBestVendorPackageList(deps_data_path)
        if not packages:
            print(Debug().colorize(f" r[b[*] Packages could not be installed, because kde-builder does not know your distribution ({vendor})"))
            return
        
        installCmd = self._findBestInstallCmd()
        
        # Remake the command for Arch Linux to not require running sudo command when not needed (https://bugs.kde.org/show_bug.cgi?id=471542)
        if self.oss.vendorID() == "arch":
            required_packages_and_required_groups = packages
            missing_packages_and_required_groups = subprocess.run("pacman -T " + " ".join(required_packages_and_required_groups), shell=True, capture_output=True, check=False).stdout.decode("utf-8").removesuffix("\n").split("\n")
            all_possible_groups = subprocess.run("pacman -Sg", shell=True, capture_output=True, check=False).stdout.decode("utf-8").removesuffix("\n").split("\n")
            required_groups = [el for el in missing_packages_and_required_groups if el in all_possible_groups]
            missing_packages_not_grouped = [el for el in missing_packages_and_required_groups if el not in required_groups]
            missing_packages_from_required_groups = []
            if required_groups:
                for required_group in required_groups:
                    missing_packages_from_required_group = subprocess.run(f"pacman -Sqg {required_group} | xargs pacman -T", shell=True, capture_output=True, check=False).stdout.decode("utf-8").removesuffix("\n").split("\n")
                    missing_packages_from_required_group = list(filter(None, missing_packages_from_required_group))  # Remove empty string element. It appears if there is no any unresolved package from the group
                    missing_packages_from_required_groups += missing_packages_from_required_group
            packages = missing_packages_not_grouped + missing_packages_from_required_groups
        
        if packages:
            print(Debug().colorize(f""" b[*] Running 'b[{" ".join(installCmd + packages)}]'"""))
            result = subprocess.run(installCmd + packages, shell=False, check=True)
            exitStatus = result.returncode
        else:
            print(Debug().colorize(" b[*] All dependencies are already installed. No need to run installer. b[:)]"))
            exitStatus = 0
        
        # Install one at a time if we can, but check if sudo is present
        hasSudo = subprocess.call("type " + "sudo", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0
        everFailed = False
        if exitStatus != 0 and self.oss.isDebianBased() and hasSudo:
            for onePackage in packages:
                commandLine = f"sudo apt-get -q -y --no-install-recommends install {onePackage}".split(" ")
                print(Debug().colorize(f""" b[*] Running 'b[{" ".join(commandLine)}]'"""))
                # Allow for Ctrl+C.
                time.sleep(250 / 1000)
                result = subprocess.run(commandLine, shell=False, capture_output=True, check=True)
                if not everFailed:
                    everFailed = result.returncode != 0
        
        exitStatus = 0  # It is normal if some packages are not available.
        if everFailed:
            print(Debug().colorize(" y[b[*] Some packages failed to install, continuing to build."))
        
        if exitStatus == 0:
            print(Debug().colorize(" b[*] b[g[Looks like the necessary packages were successfully installed!]"))
        else:
            print(Debug().colorize(f" r[b[*] Failed with exit status {exitStatus}. Ran into an error with the installer!"))
    
    def suggestedNumCoresForLowMemory(self) -> int:
        """
        Returns the suggested number of cores to use for make jobs for build jobs where
        memory is a bottleneck, such as qtwebengine.
        ::
        
            num_cores = ksb.FirstRun.suggestedNumCoresForLowMemory()
        """
        
        # Try to detect the amount of total memory for a corresponding option for
        # heavyweight modules
        
        # 4 GiB is assumed if no info on memory is available, as this will
        # calculate to 2 cores.
        mem_total = self.oss.detectTotalMemory()
        if not mem_total:
            mem_total = 4 * 1024 * 1024
        
        rounded_mem = int(mem_total / 1024000.0)
        return max(1, int(rounded_mem / 2))  # Assume 2 GiB per core
    
    # Return the highest number of cores we can use based on available memory, but
    # without exceeding the base number of cores available.
    def _getNumCoresForLowMemory(self, num_cores) -> int:
        return min(self.suggestedNumCoresForLowMemory(), num_cores)
    
    def _setupBaseConfiguration(self) -> None:
        # According to XDG spec, if $XDG_CONFIG_HOME is not set, then we should
        # default to ~/.config
        xdgConfigHome = os.environ.get("XDG_CONFIG_HOME", os.environ.get("HOME") + "/.config")
        xdgConfigHomeShort = xdgConfigHome.replace(os.environ.get("HOME"), "~")  # Replace $HOME with ~
        knownLocations = [os.getcwd() + "/kdesrc-buildrc",
                          f"{xdgConfigHome}/kdesrc-buildrc",
                          os.environ.get("HOME") + "/.kdesrc-buildrc"]
        locatedFile = None
        for knownLocation in knownLocations:
            if os.path.isfile(knownLocation):
                locatedFile = knownLocation
                break
        
        if locatedFile:
            printableLocatedFile = locatedFile.replace(os.environ.get("HOME"), "~")
            print(Debug().colorize(f"b[*] You already have a configuration file: b[y[{printableLocatedFile}]"))
            return
        
        print(Debug().colorize(f"b[*] Creating b[sample configuration file]: b[y[\"{xdgConfigHomeShort}/kdesrc-buildrc\"]..."))
        
        with open(os.path.dirname(os.path.realpath(__file__)) + "/../data/kdesrc-buildrc.in", "r") as data_file:
            sampleRc = data_file.read()
        
        numCores = None
        if self.oss.vendorID() in [*self.supportedDistros, "linux"]:
            numCores = int(subprocess.run(["nproc"], shell=False, capture_output=True, check=True).stdout.decode("utf-8").removesuffix("\n"))
        elif self.oss.vendorID() == "freebsd":
            numCores = int(subprocess.run(["sysctl", "-n", "hw.ncpu"], shell=False, capture_output=True, check=True).stdout.decode("utf-8").removesuffix("\n"))
        
        if not numCores:
            numCores = 4
        
        numCoresLow = self._getNumCoresForLowMemory(numCores)
        
        sampleRc = sampleRc.replace("%{num_cores}", str(numCores))
        sampleRc = sampleRc.replace("%{num_cores_low}", str(numCoresLow))
        
        gl = BuildContext().build_options["global"]  # real global defaults
        
        def fill_placeholder(option_name, mode=""):
            value = gl[option_name]
            if mode == "bool_to_str":
                # Perl doesn't have native boolean types, so config internally operates on 0 and 1.
                # But it will be convenient to users to use "true"/"false" strings in their config files.
                value = "true" if value else "false"
            elif mode == "home_to_tilde":
                value = re.sub(rf"""^{os.environ.get("HOME")}""", "~", value)
            nonlocal sampleRc
            sampleRc = sampleRc.replace(f"%{{{option_name}}}", value)
        
        fill_placeholder("include-dependencies", "bool_to_str")
        fill_placeholder("install-dir", "home_to_tilde")
        fill_placeholder("source-dir", "home_to_tilde")
        fill_placeholder("build-dir", "home_to_tilde")
        fill_placeholder("install-session-driver", "bool_to_str")
        fill_placeholder("install-environment-driver", "bool_to_str")
        fill_placeholder("stop-on-failure", "bool_to_str")
        fill_placeholder("directory-layout")
        fill_placeholder("compile-commands-linking", "bool_to_str")
        fill_placeholder("compile-commands-export", "bool_to_str")
        fill_placeholder("generate-vscode-project-config", "bool_to_str")
        
        os.makedirs(xdgConfigHome, exist_ok=True)
        with open(f"{xdgConfigHome}/kdesrc-buildrc", "w") as sampleFh:
            sampleFh.write(sampleRc)
        print()
    
    def _findBestInstallCmd(self) -> list:
        cmdsRef = {
            "cmd/install/alpine/unknown": "apk add --virtual .makedeps-kde-builder",
            "cmd/install/arch/unknown": "pacman -S --noconfirm",
            "cmd/install/debian/unknown": "apt-get -q -y --no-install-recommends install",
            "cmd/install/fedora/unknown": "dnf -y install",
            "cmd/install/freebsd/unknown": "pkg install -y",
            "cmd/install/gentoo/unknown": "emerge -v --noreplace",
            "cmd/install/opensuse/unknown": "zypper install -y --no-recommends",
        }
        
        supportedDistros = [cmddist.removeprefix("cmd/install/").removesuffix("/unknown") for cmddist in cmdsRef.keys()]
        
        bestVendor = self.oss.bestDistroMatch(supportedDistros)
        print(Debug().colorize(f"    Using installer for b[{bestVendor}]"))
        
        version = self.oss.vendorVersion()
        cmd = []
        
        for opt in [f"{bestVendor}/{version}", f"{bestVendor}/unknown"]:
            key = f"cmd/install/{opt}"
            if key in cmdsRef.keys():
                cmd = cmdsRef[key].split(" ")
                break
        
        if not cmd:
            self._throw(f"No installer for {bestVendor}!")
        
        # If not running as root already, add sudo
        if os.geteuid() != 0:
            cmd.insert(0, "sudo")
        
        return cmd
    
    def _findBestVendorPackageList(self, deps_data_path) -> list:
        bestVendor = self.oss.bestDistroMatch(self.supportedDistros + self.supportedOtherOS)
        version = self.oss.vendorVersion()
        print(Debug().colorize(f"    Installing packages for b[{bestVendor}]/b[{version}]"))
        return self._packagesForVendor(bestVendor, version, deps_data_path)
    
    def _packagesForVendor(self, vendor, version, deps_data_path) -> list:
        packages = self._readPackages(vendor, version, deps_data_path)
        for opt in [f"pkg/{vendor}/{version}", f"pkg/{vendor}/unknown"]:
            if opt in packages.keys():
                return packages[opt]
        return []
