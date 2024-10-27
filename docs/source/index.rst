trac2markdown
=============

Description
-----------

Edgewall Trac is a simple open-source system for source control and project management. The simplicity of the system has its advantages, although organizations might decide to migrate their project to another system over the years, due to increased workload or the need for additional functionalities. However, the Markdown syntax used by Trac's wiki and ticket tracking systems is slightly different from the standard Markdown used on most project management systems, which complicates the migration process.

This is an open-source Python package that includes methods to format text from Trac's Markdown syntax to the standard Markdown format. The package enables extraction, formatting, and saving of all wiki pages from a Trac database into a new directory. Additionally, the formatting methods can be used independently to format ticket descriptions and comments, since there are available libraries for converting from Markdown to other markup languages if needed.

Installation
------------

To install this package, you can use *pip*:

.. code:: bash

   pip install trac2markdown

To import the package, use:

.. code:: python

   from trac2markdown.format_wikis import *

Prerequisites
-------------

This package requires some input parameters in order to function properly. The sample configuration file is saved under ``format_wikis_config.py.sample``.

Before running the script, ensure you save the configuration as a Python file with the following fields: 

- **new_wikis_folder**: The path to the folder where the formatted wikis will be saved. 
- **trac_link**: Your organization's base Trac link. 
- **docs_link**: Your organization's Trac docs link. 
- **code_link**: Your organization's Trac code log link. 
- **trac_db**: Name of your Trac database. 
- **trac_env_path**: Path to your Trac environment backup. 
- **ignored_wikis**: List of wiki pages to be ignored during the formatting and migration.

Usage
-----

From package
~~~~~~~~~~~~

The ``format_wikis`` script includes many methods to handle different aspects of the formatting process. If the script is installed as a package, the methods can be used directly within your Python code. 

These are all formatting methods included in the package:

- **preprocessing(text)**: Preprocesses the text to remove Trac-specific syntax. 
- **postprocessing(text)**: Replaces double backticks with single backticks after formatting. 
- **format_title_index(text, env_path, trac_link)**: Formats TitleIndex Trac references. 
- **format_log_links(text, code_link)**: Formats code log references. 
- **format_source_docs(text, docs_link)**: Formats source document references. 
- **format_source_links(text, trac_link)**: Formats source:/ style links. 
- **format_wiki_links(text, trac_link)**: Formats automatic Trac wiki links. 
- **format_report_links(text, trac_link)**: Formats automatic Trac report links. 
- **format_ticket_links(text, trac_link)**: Formats automatic Trac ticket links. 
- **format_attachments(wiki_attachments, attachment_path, wiki_name, text)**: Formats wiki attachments and copies them to the appropriate folder. 
- **format_unordered_lists(text)**: Formats unordered lists. 
- **format_tables(text)**: Formats tables. 
- **format_links(text)**: Formats hyperlinks. 
- **format_underline(text)**: Formats underlined text using HTML tags. 
- **format_bold(text)**: Formats bold text. 
- **format_italic(text)**: Formats italic text. 
- **format_code_blocks(text)**: Formats code blocks with or without language identifiers. 
- **format_horizontal_rule(text)**: Formats horizontal rules. 
- **format_headers(text)**: Formats headers from level 1 to level 4.

These are all the helper methods used for getting all necessary information, such as the Wiki objects and their metadata, and to call the formatting functions: 

- **get_specific_wiki(env_path, wiki_name)**: Returns the Wiki object with the specified name. 
- **get_all_wikis(env_path, date, ignored_wikis)**: Returns all Wiki objects to be formatted. 
- **get_attachments_and_paths(wikis, env)**: Returns all attachments per wiki and their respective paths in the database. 
- **format_all_wikis(env_path, wikis, wiki_attachments, attachment_path, new_wikis_folder, trac_link, docs_link, code_link**: Calls all format functions and then saves the formatted wikis to the specified folder.

The main function of the script orchestrates the entire process, calling the necessary methods to format all wikis and save them to the specified folder.

From repository
~~~~~~~~~~~~~~~

The script can be run with different options depending on the user's needs. Below are some examples of how to use the script:

1. **Run script if config file is created in ``trac_to_markdown/format_wikis_config.py``:**

   .. code:: bash

      python wikis_migration.py

2. **Specify date to include wikis from:**

   .. code:: bash

      python wikis_migration.py --date 2014-05-10

3. **Migrate only one wiki:**

   .. code:: bash

      python wikis_migration.py --wiki-name ExampleWikiName

4. **Run script with config file at a custom path:**

   .. code:: bash

      python wikis_migration.py --config path/to/config_file

5. **Run script without a config file:**

   .. code:: bash

      python wikis_migration.py path_to_trac_env path_to_new_wikis_folder

Next steps
----------

After using this package to format your wiki pages, their migration needs to be performed by the user.
 
For Azure DevOps, the entire directory created by the main script of this package can be uploaded as a repository and then the Wiki can be created from that repo.

For other systems, consult their help pages.