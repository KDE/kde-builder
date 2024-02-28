# Here you can enable type_enforced decorator for specified classes


enabled_classes = [
    "BuildSystem_Autotools",
    "BuildSystem",
    "BuildSystem_CMakeBootstrap",
    "BuildSystem_KDECMake",
    "BuildSystem_Meson",
    "BuildSystem_QMake",
    "BuildSystem_QMake6",
    "BuildSystem_Qt4",
    "BuildSystem_Qt5",
    "BuildSystem_Qt6",
    "IPC",
    "IPC_Null",
    "IPC_Pipe",
    "Module_BranchGroupResolver",
    "Module",
    "ModuleSet_KDEProjects",
    "ModuleSet",
    "ModuleSet_Null",
    "ModuleSet_Qt",
    "Updater_Git",
    "Updater_KDEProject",
    "Updater_KDEProjectMetadata",
    "Updater_Qt5",
    "Updater",
    "Util_LoggedSubprocess",
    "Util",
    "Application",
    "BuildContext",
    "BuildException",
    "BuildException_Config",
    "Cmdline",
    "DBus",
    "Debug",
    "DebugOrderHints",
    "DependencyResolver",
    "FirstRun",
    "KDEProjectsReader",
    "ModuleResolver",
    "OptionsBase",
    "OSSupport",
    "PhaseList",
    "RecursiveFH",
    "StartProgram",
    "StatusView",
    "TaskManager",
    "Version",
    ]  # For development

enabled_classes.clear()  # For production. Comment this line when developing.


def conditional_type_enforced(cls):
    if cls.__name__ in enabled_classes:
        import type_enforced  # do not import it in the beginning of file, because users may not have this package installed
        return type_enforced.Enforcer(cls)
    else:
        return cls


# Copy of type_enforced.utils::WithSubclasses, so I (Andrew Shark) can still leave it in code, but users are not required to install type_enforced package
def WithSubclasses(obj):
    """
    A special helper function to allow a class type to be passed and also allow all subclasses of that type.

    Requires:

    - `obj`:
        - What: An uninitialized class that should also be considered type correct if a subclass is passed.
        - Type: Any Uninitialized class

    Returns:

    - `out`:
        - What: A list of all of the subclasses (recursively parsed)
        - Type: list of strs


    Notes:

    - From a functional perspective, this recursively get the subclasses for an uninitialised class (type).
    """
    out = [obj]
    for i in obj.__subclasses__():
        out += WithSubclasses(i)
    return out
