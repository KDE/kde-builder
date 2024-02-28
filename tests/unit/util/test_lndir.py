import os.path
from ksblib.Util.Util import Util
import tempfile
from promise import Promise


def test_safe_lndir():
    """
    Test safe_lndir_p
    """
    tmpdir = tempfile.mkdtemp(prefix="kdesrc-build-testXXXXXX")
    assert tmpdir, "tempdir created"
    
    file = os.path.join(tmpdir, "a")
    open(file, "a").close()
    assert os.path.exists(file), "first file created"
    
    dir2 = os.path.join(tmpdir, "b/c")
    os.makedirs(dir2)
    assert os.path.isdir(f"{tmpdir}/b/c"), "dir created"
    
    file2 = os.path.join(tmpdir, "b", "c", "file2")
    open(file2, "a").close()
    assert os.path.exists(f"{tmpdir}/b/c/file2"), "second file created"
    
    to = tempfile.mkdtemp(prefix="kdesrc-build-test2")
    promise = Util.safe_lndir_p(os.path.abspath(tmpdir), os.path.abspath(to))
    
    # These shouldn't exist until we let the promise start!
    # assert not os.path.exists(f"{to}/b/c/file2"), "safe_lndir does not start until we let promise run"  # pl2py: the promises we use start right after we create them
    
    Promise.wait(promise)
    
    assert os.path.isdir(f"{to}/b/c"), "directory symlinked over"
    assert os.path.islink(f"{to}/a"), "file under directory is a symlink"
    assert os.path.exists(f"{to}/a"), "file under directory exists"
    assert not os.path.exists(f"{to}/b/d/file3"), "nonexistent file does not exist"
    assert os.path.islink(f"{to}/b/c/file2"), "file2 under directory is a symlink"
    assert os.path.exists(f"{to}/b/c/file2"), "file2 under directory exists"
