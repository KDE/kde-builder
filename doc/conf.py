# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os

project = "KDE Builder"
copyright = "kde-builder documentation authors"
author = "Andrew Shark"
smartquotes = False  # to render double dashes in option names correctly

extensions = [
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "README.md"]
html_extra_path = ["404handler.php"]  # bring our 404 handler in

html_theme = "sphinx_book_theme"
html_static_path = ["_static"]
git_cmd = "git log --date=format:'%Y-%m-%d %H:%M:%S %z' --pretty='format:%ad, commit %h' -n1"
html_last_updated_fmt = os.popen(git_cmd).read()

html_theme_options = {
    "repository_provider": "gitlab",
    "repository_url": "https://invent.kde.org/sdk/kde-builder",
    "use_source_button": True,
    "repository_branch": "master",
    "path_to_docs": "doc",
    "use_edit_page_button": True,
    "use_repository_button": True,
    "use_issues_button": True,
    "use_download_button": True,
}

myst_enable_extensions = [
    "attrs_inline",
    "attrs_block",
    "deflist",
]
