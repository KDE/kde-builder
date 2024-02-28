from ..Util.Conditional_Type_Enforced import conditional_type_enforced
from typing import NoReturn

from ..BuildException import BuildException


@conditional_type_enforced
class Updater:
    """
    Base class for classes that handle updating the source code for a given
    L<ksb::Module>.  It should not be used directly.
    """
    
    def __init__(self, module):
        self.module = module
    
    @staticmethod
    def name() -> NoReturn:
        BuildException.croak_internal("This package should not be used directly.")
    
    def module(self):
        return self.module
