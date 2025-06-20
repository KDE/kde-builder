# Project list construction

An overview of the steps performed in constructing the project list:

There are two parallel flows performed for project list construction

1. Configuration file project list processing. The configuration file supports
projects of various types along with groups. Projects of the kde-project
type (available *only* from a group) can be converted later into 0, 1, or
more git projects. Projects are formed into the list in the order given in the
configuration file, but any projects implicitly pulled in from the kde-project
projects will be sorted appropriately by repo-metadata/dependencies.

2. Projects can be directly specified on the command line. kde-projects projects
can be forced by preceding the project name with a "+".

After processing command line project names, any projects that match a project
(or group) given from the configuration file will have the configuration
file version of that project spliced into the list to replace the command line
one.

So a graphical overview of configuration file projects

> git, setA/git, setA/git, setA/git, setB/proj

which is proj-expanded to form (for instance)

> git, setA/git, setA/git, setA/git, setB/git, setB/git

and is then filtered (respecting --resume-{from,after})

> setA/git, setA/git, setA/git, setB/git, setB/git

(and even this leaves out some details, e.g. l10n).

Command-line projects:

kde-builder also constructs a list of command-line-passed projects. Since the
project names are read before the configuration file is even named (let alone
read) kde-builder has to hold onto the list until much later in
initialization before it can really figure out what's going on with the
command line. So the sequence looks more like:

> nameA/??, nameB/??, +nameC/??, nameD/??

Then + names are forced to be proj-type

> nameA/??, nameB/??, nameC/proj, nameD/??

From here we "splice" in configuration file projects that have matching names
to projects from the command line.

> nameA/??, nameB/git, nameC/proj, nameD/??

Following this we run a filter pass to remove whole groups that we don't
care about (as the _apply_module_filters() function cares only about
`module.name`. In this example nameA happened to match a group name
only.

> nameB/git, nameC/proj, nameD/??

Finally, we match and expand potential groups

> nameB/git, nameC/proj, nameE/proj, nameF/proj

Not only does this expansion try to splice in projects under a named
group, but it forces each project that doesn't already have a type into
having a "proj" type but with a special "guessed name" annotation, which is
used later for proj-expansion.

At this point we should be at the same point as if there were no command-line
projects, just before we expand kde-projects projects (yes, this means that the
--resume-* flags are checked twice for this case). At this point there is a
separate pass to ensure that all projects respect the --no-{src,build,etc.}
options if they had been read from the command line, but that could probably
be done at any time and still work just fine.

One other nuance is that if _nameD/??_ above had *not* actually been part of a
group and was also not the name of an existing kde-project project, then
trying to proj-expand it would have resulted in an exception being thrown
(this is where the check for unknown projects occurs).
