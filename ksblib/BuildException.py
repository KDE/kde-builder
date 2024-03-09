from __future__ import annotations

import textwrap
from .Util.Conditional_Type_Enforced import conditional_type_enforced
from typing import NoReturn


@conditional_type_enforced
class BuildException(Exception):
    """
    A class to wrap 'exception' messages for the script, allowing them to be
    dispatch based on type and automatically stringified.
    """
    
    def __init__(self, exception_type, msg):
        self.exception_type = exception_type
        self.message = msg
    
    def __str__(self) -> str:
        return self.exception_type + " Error: " + self.message
    
    def message(self):
        return self.message
    
    def setMessage(self, newMessage) -> None:
        self.message = newMessage
    
    # Exported utility functions
    
    @staticmethod
    def make_exception(exception_type: str, msg: str, levels=None):
        """
        Returns a Perl exception object to pass to 'die' function
        The returned reference will be an instance of ksb::BuildException.
        
        First parameter: Exception type, 'Exception' if undef
        Second parameter: Message to show to user
        """
        exception_type = exception_type if exception_type else "Exception"
        message = msg
        levels = levels if levels else 0  # Allow for more levels to be removed from bt
        
        # # Remove this subroutine from the backtrace
        # local $Carp::CarpLevel = 1 + $levels;
        
        # if exception_type == 'Internal':
        #     message = Carp::cluck(message)  # prints the backtrace
        return BuildException(exception_type, message)
    
    @staticmethod
    def had_an_exception(e):
        """
        Helper function to return $@ if $@ is a ksb::BuildException.
        
        This function assumes that an eval block had just been used in order to set
        or clear $@ as appropriate.
        """
        if e and isinstance(e, BuildException):
            return e
        return
    
    @staticmethod
    def croak_runtime(msg: str) -> NoReturn:
        """
        Should be used for "runtime errors" (i.e. unrecoverable runtime problems that
        don't indicate a bug in the program itself).
        """
        raise BuildException.make_exception("Runtime", msg, 1)
    
    @staticmethod
    def croak_internal(msg: str) -> NoReturn:
        """
        Should be used for "logic errors" (i.e. impossibilities in program state, things
        that shouldn't be possible no matter what input is fed at runtime)
        """
        raise BuildException.make_exception("Internal", msg, 1)


@conditional_type_enforced
class BuildException_Config(BuildException):
    """
    A small subclass to hold the option name that caused a config exception to
    be thrown.
    
    Typically, this will be caught by config-reading code in ksb::Application,
    which will add filename and line number information to the message.
    """
    
    def __init__(self, bad_option_name, msg):
        BuildException.__init__(self, "Config", msg)
        self.config_invalid_option_name = bad_option_name
    
    def problematicOptionName(self):
        return self.config_invalid_option_name
    
    @staticmethod
    def optionUsageExplanation(optionName) -> str | None:
        """
        Should return a lengthy explanation of how to use a given option for use in
        error messages, or undef if no explanation is unavailable.
        """
        result = None
        
        if isinstance(optionName, BuildException_Config):
            # Should only happen if called as method: i.e. $optionName == $self
            optionName = optionName.problematicOptionName()
        
        if optionName == "git-repository-base":
            result = textwrap.dedent("""\
            The y[git-repository-base] option requires a repository name and URL.
            
            e.g. git-repository base y[b[kde-sdk] g[b[https://invent.kde.org/sdk/]
            
            Use this in a "module-set" group:
            
            e.g.
            module-set kdesdk-set
                repository y[b[kde-sdk]
                use-modules kde-builder kde-dev-scripts clazy
            end module-set
            """)
        return result
