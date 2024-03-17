(appendix-profile)=
# Superseded profile setup procedures

(old-profile-setup)=
## Setting up a KDE login profile

These instructions cover how to setup the profile required to ensure
your computer can login to your newly-built KDE Plasma desktop.
kdesrc-build will normally try to do this automatically (see the section called
[](#session-driver)). This appendix section can be useful for those
who cannot use kdesrc-build's support for login profile setup. However
the instructions may not always be up-to-date, it can also be useful to
consult the `kde-env-master.sh.in` file included with the kdesrc-build
source.

(changing-profile)=
### Changing your startup profile settings

```{important}
The `.bash_profile` is the login settings file for the popular bash
shell used by many Linux distributions. If you use a different shell,
then you may need to adjust the samples given in this section for your
particular shell.
```

Open or create the `.bash_profile` file in the home directory with your
favorite editor, and add to the end of the file: If you are building the
qt module (you are by default), add instead:

```
PATH=${install-dir}/bin:${qt-install-dir}/bin:$PATH
MANPATH=${qt-install-dir}/doc/man:$MANPATH

# Act appropriately if LD_LIBRARY_PATH is not already set.
if [ -z $LD_LIBRARY_PATH ]; then
  LD_LIBRARY_PATH=${install-dir}:/lib:${qt-install-dir}/lib
else
  LD_LIBRARY_PATH=${install-dir}:/lib:${qt-install-dir}/lib:$LD_LIBRARY_PATH
fi

export PATH MANPATH LD_LIBRARY_PATH
```

or, if you are not building qt (and are using your system Qt instead),
add this instead:

```
PATH=${install-dir}/bin:${qt-install-dir}/bin:$PATH

# Act appropriately if LD_LIBRARY_PATH is not already set.
if [ -z $LD_LIBRARY_PATH ]; then
  LD_LIBRARY_PATH=${install-dir}/lib
else
  LD_LIBRARY_PATH=${install-dir}/lib:$LD_LIBRARY_PATH
fi

export PATH LD_LIBRARY_PATH
```

If you are not using a dedicated user, set a different \$`KDEHOME` for
your new environment in your `.bash_profile`:

```
export KDEHOME="${HOME}/.kde-git"

# Create it if needed
[ ! -e ~/.kde-git ] && mkdir ~/.kde-git
```

```{note}
If later your K Menu is empty or too crowded with applications from your
distribution, you may have to set the XDG environment variables in your
`.bash_profile`:

    XDG_CONFIG_DIRS="/etc/xdg"
    XDG_DATA_DIRS="${install-dir}/share:/usr/share"
    export XDG_CONFIG_DIRS XDG_DATA_DIRS
```

(starting-kde)=
### Starting KDE

Now that you have adjusted your environment settings to use the correct
KDE, it is important to ensure that the correct `startkde` script is
used as well.

Open the `.xinitrc` text file from the home directory, or create it if
necessary. Add the line:

```
exec ${install-dir}/bin/startkde
```

```{important}
On some distributions, it may be necessary to perform the same steps
with the `.xsession` file, also in the home directory. This is
especially true when using graphical login managers such as sddm, gdm,
or xdm.
```

Now start your fresh KDE: in BSD and Linux systems with virtual terminal
support, Ctrl+Alt+F1 ...
Ctrl+Alt+F12 keystroke combinations are
used to switch to Virtual Console 1 through 12. This allows you to run
more than one desktop environment at the same time. The fist six are
text terminals and the following six are graphical displays.

If when you start your computer you are presented to the graphical
display manager instead, you can use the new KDE environment, even if it
is not listed as an option. Most display managers, including sddm, have
an option to use a “Custom Session” when you login. With this option,
your session settings are loaded from the `.xsession` file in your home
directory. If you have already modified this file as described above,
this option should load you into your new KDE installation.

If it does not, there is something else you can try that should normally
work: Press Ctrl+Alt+F2, and you will be
presented to a text terminal. Log in using the dedicated user and type:

```
startx -- :1
```

````{tip}
You can run the KDE from sources and the old KDE at the same time! Log
in using your regular user, start the stable KDE desktop. Press
Ctrl+Alt+F2 (or F1, F3, etc..), and you
will be presented with a text terminal. Log in using the dedicated KDE
Git user and type:

```
startx -- :1
```
You can go back to the KDE desktop of your regular user by pressing the
shortcut key for the already running desktop. This is normally
Ctrl+Alt+F7, you may need to use F6 or F8
instead. To return to your kdesrc-build-compiled KDE, you would use the
same sequence, except with the next function key. For example, if you
needed to enter Ctrl+Alt+F7 to switch to
your regular KDE, you would need to enter
Ctrl+Alt+F8 to go back to your
kdesrc-build KDE.
````
