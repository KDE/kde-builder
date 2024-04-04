import os
# from overrides import override
import struct
from .IPC import IPC
from ..BuildException import BuildException


class IPC_Pipe(IPC):
    """
    IPC class that uses pipes in addition to forking for IPC.
    """
    
    def __init__(self):
        IPC.__init__(self)
        
        # Define file handles.
        self.pipe_read, self.pipe_write = os.pipe()
        self.fh = None
    
    def setSender(self):
        """
        Call this to let the object know it will be the update process.
        """
        os.close(self.pipe_read)
        self.fh = os.fdopen(self.pipe_write, "wb", 0)  # Disable buffering and any possibility of IO 'interpretation' of the bytes
    
    def setReceiver(self):
        os.close(self.pipe_write)
        self.fh = os.fdopen(self.pipe_read, "rb", 0)  # Disable buffering and any possibility of IO 'interpretation' of the bytes
    
    @staticmethod
    # @override
    def supportsConcurrency() -> bool:
        """
        Reimplementation of ksb::IPC::supportsConcurrency
        """
        return True
    
    # @override(check_signature=False)
    def sendMessage(self, msg: bytes) -> bool:
        """
        Required reimplementation of ksb::IPC::sendMessage
        First parameter is the (encoded) message to send.
        """
        
        # Since streaming does not provide message boundaries, we will insert
        # ourselves, by sending a 2-byte unsigned length, then the message.
        encodedMsg = struct.pack("H", len(msg)) + msg
        written_length = self.fh.write(encodedMsg)
        
        if not written_length or len(encodedMsg) != written_length:
            BuildException.croak_runtime(f"Unable to write full msg to pipe")
        
        return True
    
    def _readNumberOfBytes(self, length: int) -> bytes:
        fh = self.fh
        result = fh.read(length)
        return result
    
    # @override(check_signature=False)
    def receiveMessage(self) -> bytes:
        """
        Required reimplementation of ksb::IPC::receiveMessage
        """
        # Read unsigned short with msg length, then the message
        msgLength = self._readNumberOfBytes(2)
        if not msgLength:
            return b""
        
        msgLength = struct.unpack("H", msgLength)[0]  # Decode to Perl type
        if not msgLength:
            BuildException.croak_internal(f"Failed to read {msgLength} bytes as needed by earlier message!")
        
        return self._readNumberOfBytes(msgLength)
    
    # @override
    def close(self):
        self.fh.close()
