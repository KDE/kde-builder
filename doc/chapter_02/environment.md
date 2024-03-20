(setting-environment)=
# Setting the Environment to Run Your KDE Plasma Desktop

Assuming you are using a dedicated user to build KDE Plasma, and you
already have an installed Plasma version, running your new Plasma may be
a bit tricky, as the new Plasma has to take precedence over the old. You
must change the environment variables of your login scripts to make sure
the newly-built desktop is used.

(session-driver)=
## Automatically installing a login driver

Starting from version 1.16, kde-builder will try to install an
appropriate login driver, that will allow you to login to your
kde-builder built KDE desktop from your login manager. This can be
disabled by using the `install-session-driver` configuration file
option.

```{note}
Session setup does not occur while kde-builder is running in pretend mode.
```

This driver works by setting up a custom “`xsession`” session type. This
type of session should work by default with the sddm login manager
(where it appears as a “Custom” session), but other login managers (such
as LightDM and gdm) may require additional files installed to enable
`xsession` support.

(xsession-distribution-setup)=
### Adding xsession support for distributions

The default login managers for some distributions may require additional
packages to be installed in order to support `xsession` logins.

- The [Fedora](https://getfedora.org/) Linux distribution requires the
  `xorg-x11-xinit-session` package to be installed for custom `xsession`
  login support.

- [Debian](https://www.debian.org/) and Debian-derived Linux
  distributions should support custom `xsession` logins, but require the
  `allow-user-xsession` option to be set in `/etc/X11/Xsession.options`.
  See also the Debian [documentation on customizing the X
  session.](https://www.debian.org/doc/manuals/debian-reference/ch07.en.html#_customizing_the_x_session_classic_method)

- For other distributions, go to the section called [Manually adding support for
  xsession](#xsession-manual-setup).

(xsession-manual-setup)=
### Manually adding support for xsession

If there were no distribution-specific directions for your distribution
in the section called [Adding xsession support for
distributions](#xsession-distribution-setup), you can manually add a
“Custom xsession login” entry to your distribution's list of session
types as follows:

(proc-adding-xsession-type)=
Procedure: Adding an .xsession login session type

1. Create the file `/usr/share/xsessions/kde-builder.desktop`.

2. Ensure the file just created has the following text:

```
Type=XSession
Exec=<1>$HOME/.xsession
Name=KDE Plasma Desktop (unstable; kde-builder)
```

(session-homedir)=
  \<1\>: The _\$HOME_ entry must be replaced by the full path to your home
    directory (example, `/home/user`). The desktop entry specification
    does not allow for user-generic files.

3. When the login manager is restarted, it should show a new session
  type, “KDE Plasma Desktop (unstable; kde-builder)” in its list of
  sessions, which should try to run the `.xsession` file installed by
  kde-builder if it is selected when you login.

```{note}
  It may be easiest to restart the computer to restart the login
  manager, if the login manager does not track updates to the
  `/usr/share/xsessions` directory.
```

(old-profile-instructions)=
## Setting up the environment manually

This documentation used to include instruction on which environment
variables to set in order to load up the newly-built desktop. These
instructions have been moved to an appendix (the section called [](#old-profile-setup)).

If you intend to setup your own login support you can consult that
appendix or view the `kde-env-master.sh.in` file included with the
kde-builder source.
