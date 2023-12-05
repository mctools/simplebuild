# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'simplebuild'
copyright = '2013-2024, ESS ERIC and simplebuild developers'
author = 'Thomas Kittelmann'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []
extensions += ['myst_parser']
extensions += ['sphinxarg.ext']

templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
#html_logo = 'icon/favicon-32x32.png'
html_favicon = 'icon/favicon-32x32.png'
#html_sidebars = { '**': ['globaltoc.html', 'searchbox.html'] }

html_theme_options = {
    'logo_only': False,
#    'collapse_navigation' : False,
    'sticky_navigation': True,


}

#html_theme_options = {
#    'logo': 'icon/android-chrome-192x192.png',
#    # etc.
#}
#

#html_sidebars = { '**': ['globaltoc.html', 'relations.html', 'sourcelink.html', 'searchbox.html'] }



#html_theme_options = {
#    ...
#    "home_page_in_toc": True
#    ...
#}
#
