"""
Script for formatting Trac markdown syntax to standard markdown.
The wikis are read from the latest backup of the Trac database,
which must be downloaded manually by the user who runs the script.

Example usage:
:: Run script if config file is created in trac_to_markdown/format_wikis_config.py:
wikis_migration.py

:: Specify date to include wikis from:
wikis_migration.py --date 2014-05-10

:: Migrate only 1 wiki
wikis_migration.py --wiki-name ExampleWikiName

:: Run script with config file at custom path:
wikis_migration.py --config path/to/config_file

:: Run script without config file:
wikis_migration.py path_to_trac_env path_to_new_wikis_folder
"""

import argparse
import datetime
import fnmatch
import importlib
import os
import re
import sqlite3
import shutil

import trac.attachment
import trac.env


def preprocessing(text):
    """
    Preprocesses the text before sending it to the format functions:
     - to avoid misinterpretation by the regex methods
     - to remove any Trac specific syntax not used in standard markdown.

    Single backticks are replaced with double backticks, to
    avoid bad escape errors caused by a backtick and a character.

    Removed syntax:
     - Quotation marks (") at the beginning and end of wikis
     - [[PageOutline]] at the beginning of wikis
     - [[BR]] and [[br]] line breaks
     - [[TicketQuery(...)]] referencing
     - [[Emails]] referencing

    Args:
        text (str): Text in Trac markdown

    Returns:
        text (str): Preprocessed text
    """
    text = text.replace('\\', '\\\\')

    text = text.replace('[[PageOutline]]', '')
    text = text.replace('[[Emails]]', '')
    
    if text[0] == '"' and text[-1] == '"':
        text = text[1:-1]

    text = text.replace('[[BR]]', '\n')
    text = text.replace('[[br]]', '\n')

    text = re.sub(r'\[\[TicketQuery\(.+?\)\]\]', '', text)

    return text


def postprocessing(text):
    """
    Replaces all double backtics with single backticks
    after all formatting is finished, to ensure proper
    display of links and file paths in standard markdown.

    Args:
        text (str): Text to be processed

    Returns:
        text (str): Text in standard markdown
    """
    text = text.replace('\\\\', '\\')
    return text
    

def format_title_index(text, env_path, trac_link):
    """
    Formats TitleIndex Trac referencing in provided
    text string by replacing it with hyperlinks
    to all subpages of the specified title.

    Trac markdown: [[TitleIndex(wiki_name)]]
    Standard markdown: [subwiki_name_1](link_to_subwiki_1)
                       [subwiki_name_2](link_to_subwiki_2)
                       ...
                       [subwiki_name_n](link_to_subwiki_n)

    Args:
        text (str): Text in Trac markdown to be formatted
        env_path (str): Path to Trac environment
        trac_link (str): Your organization's base Trac link

    Returns:
        text (str): Formatted text in standard markdown
    """
    title_index_pattern = r'\[\[TitleIndex\((.+?/?)\)\]\]'
    match = re.findall(title_index_pattern, text)

    base_link = f'https://{trac_link}/wiki/'

    database_connection = sqlite3.connect(f'{env_path}\\db\\trac.db')
    cursor = database_connection.cursor()

    for m in match:
        subpages = []
        subpages_query = f"""
            select distinct name
            from wiki
            where name like '{m}%'
        """
        result = cursor.execute(subpages_query).fetchall()

        for page in result:
            subpages.append(page[0])

        replacement = ''
        for page in subpages:
            page_link = base_link + page
            replacement += f'- [{page}]({page_link})\n'

        text = re.sub(title_index_pattern, replacement, text, 1)

    return text


def format_log_links(text, code_link):
    """
    Formats code log references from Trac source
    code browser using the base code log url.

    Trac markdown: [log:path_to_code log_text]
    Standard markdown: [log_text](link_to_code)

    Args:
        text (str): Text in Trac markdown to be formatted
        code_link (str): Your organization's Trac code link

    Returns:
        text (str): Formatted text in standard markdown
    """
    log_pattern = r'\[log:(.+?) (.+?)\]'
    match = re.findall(log_pattern, text)

    base_link = f'https://{code_link}/'

    for m in match:
        url = m[0]
        log_text = m[1]

        if ':' in url:
            url = url.replace('@', '?revs=')
            url = url.replace(':', '-')
            log_link = base_link + url
        else:
            url = url.replace('@', '?rev=')
            log_link = base_link + url

        replacement = f'[{log_text}]({log_link})'
        text = re.sub(log_pattern, replacement, text, 1)

    return text


def format_source_docs(text, docs_link):
    """
    Formats source document references from
    Trac docs broswer using the base docs url.

    Trac markdown: [source:docs/document_path document_text]
                   [source:"docs/document path with spaces" document_text]
                   source:docs/document_path
    Standard markdown: [document_text](link_to_document)
                       [document](link_to_document)

    Args:
        text (str): Text in Trac markdown to be formatted
        docs_link (str): Your organization's Trac docs link 

    Returns:
        text (str): Formatted text in standard markdown
    """
    source_pattern_brackets = r'\[source:docs/(.+?)\s(.+?)\]'
    source_pattern_quotes = r'\[source:"+docs/(.+?)"+\s(.+?)\]'
    source_pattern_no_brackets = r'source:docs/(.+?)(\.?\s)'

    match_quotes = re.findall(source_pattern_quotes, text, re.DOTALL)
    match_brackets = re.findall(source_pattern_brackets, text, re.DOTALL)
    match_no_brackets = re.findall(source_pattern_no_brackets, text)

    base_link = f'https://{docs_link}/'

    all_matches = match_brackets + match_no_brackets + match_quotes

    for m in all_matches:
        url = base_link + r'\1'
        docs_text = m[1]

        if docs_text not in ['', '. ', ' ', '.\r']:
            replacement = f'[{docs_text}]({url})'
        else:
            replacement = f'[document]({url})\\2'

        if m in match_brackets:
            text = re.sub(source_pattern_brackets, replacement, text, 1)
        elif m in match_quotes:
            text = re.sub(source_pattern_quotes, replacement, text, 1)
        elif m in match_no_brackets:
            text = re.sub(source_pattern_no_brackets, replacement, text, 1)

    return text


def format_source_links(text, trac_link):
    """
    Formats `source:/` style links to regular
    Markdown links to the Trac source code browser. 

    There are 3 versions of source code links:
        - [source:path/to/file Title] -> [Title](base_link/path/to/file)
        - [source:path/to/file] -> [path/to/file](base_link/path/to/file)
        - source:path/to/file Title -> [source:path/to/file](base_link/path/to/file)

    Args:
        text (str): Trac text to be formatted
        trac_link (str): Your organization's base Trac link

    Returns:
        text (str): Text with various versions of Trac source:/
                    format changed to standard Markdown URLs
    """
    base_link = f'https://{trac_link}/browser/'

    wiki_pattern_brackets_title = r'\[source:(.+?)\ (.+?)]'
    wiki_pattern_brackets_title_replace = rf"[\2]({base_link}\1)"

    wiki_pattern_brackets = r'\[source:(.+?)\]'
    wiki_pattern_brackets_replace = rf"[\1]({base_link}\1)"

    wiki_pattern_base = r'(?<!\[)source:(.+?)\s'
    wiki_pattern_base_replace = rf'[source:\1]({base_link}\1) '

    text = re.sub(wiki_pattern_brackets_title, wiki_pattern_brackets_title_replace, text)
    text = re.sub(wiki_pattern_brackets, wiki_pattern_brackets_replace, text)
    text = re.sub(wiki_pattern_base, wiki_pattern_base_replace, text)

    return text


def format_wiki_links(text, trac_link):
    """
    Formats automatic Trac wiki links as 
    regular links using the base wiki url.

    Trac markdown: wiki:wiki_name
                   [wiki:wiki_name]
    Standard markdown: [wiki_name](link_to_wiki)

    Args:
        text (str): Text in Trac markdown to be formatted
        trac_link (str): Your organization's base Trac link

    Returns:
        text (str): Formatted text in standard markdown
    """
    wiki_pattern_no_brackets = r'(?<!\[)wiki:([\w\d/]+)'
    wiki_pattern_brackets = r'\[wiki:([\w\d/]+?)\]'
    wiki_pattern_brackets_text = r'\[wiki:([\w\d/]+)\s(.+?)\]'

    match_brackets = re.findall(wiki_pattern_brackets, text)
    match_brackets_text = re.findall(wiki_pattern_brackets_text, text)
    match_no_brackets = re.findall(wiki_pattern_no_brackets, text)

    all_matches = match_brackets + match_no_brackets + match_brackets_text

    base_link = f'https://{trac_link}/wiki/'
    
    for m in all_matches:
        wiki_link = base_link + r'\1'
        if m in match_brackets:
            replacement = fr'[\1]({wiki_link})'
            text = re.sub(wiki_pattern_brackets, replacement, text, 1)
        elif m in match_no_brackets:
            replacement = fr'[\1]({wiki_link})'
            text = re.sub(wiki_pattern_no_brackets, replacement, text, 1)
        elif m in match_brackets_text:
            replacement = fr'[\2]({wiki_link})'
            text = re.sub(wiki_pattern_brackets_text, replacement, text, 1)

    return text


def format_report_links(text, trac_link):
    """
    Formats automatic Trac report links as 
    regular links using the base report url.

    Trac markdown: [report:report_number report_text]
    Standard markdown: [report_text](link_to_report)

    Args:
        text (str): Text in Trac markdown to be formatted
        trac_link (str): Your organization's base Trac link

    Returns:
        text (str): Formatted text in standard markdown
    """
    report_pattern = r'\[report:\d+ (.+?)\]'
    match = re.findall(report_pattern, text)

    base_link = f'https://{trac_link}/report/'

    for m in match:
        report_link = base_link + r'\1'
        replacement = fr'[\1]({report_link})'
        text = re.sub(report_pattern, replacement, text, 1)

    return text


def format_ticket_links(text, trac_link):
    """
    Formats automatic Trac ticket links as 
    regular links using the base ticket url.

    Trac markdown: ticket #ticket_number
    Standard markdown: [ticket](link_to_ticket)

    Args:
        text (str): Text in Trac markdown to be formatted
        trac_link (str): Your organization's base Trac link

    Returns:
        text (str): Formatted text in standard markdown
    """
    ticket_link_pattern = r'#(\d+)'
    match = re.findall(ticket_link_pattern, text)

    base_link = f'https://{trac_link}/ticket/'

    for ticket_number in match:
        new_link = base_link + ticket_number
        replacement = f'[ticket:{ticket_number}]({new_link})'
        text = re.sub(ticket_link_pattern, replacement, text, 1)

    return text


def format_attachments(wiki_attachments, attachment_path, wiki_name, text):
    """
    Formats wiki attachments in provided text string and
    copies each attachment to the wiki's subfolder.

    This function first matches an image regex and replaces
    all occurences with standard markdown syntax. Each
    attachment is also copied to the respective wiki's
    subfolder in the Attachments folder.

    Then the remaining non-image attachments are also copied
    to the respective wiki's subfolder in the Attachments folder.

    Trac markdown: [[Image(path)]]
    Standard markdown: ![alt text](path)

    Args:
        wiki_attachments (dict of {str : list}): List of all attachments for each wiki
        attachment_path (dict of {str : str}): Path to each attachment
        wiki_name (str): Name of wiki which is currently formatted
        text (str): Text in Trac markdown to be formatted

    Returns:
        text (str): Formatted text in standard markdown
        wiki_attachments (dict of {str : list}): Updated list of all attachments for each wiki
                                                 after they are moved to the Attachments folder
    """
    directory = f'C:\\Users\\v.trajkosk\\infoware-trac-wiki\\Attachments\\{wiki_name}\\'
    os.makedirs(os.path.dirname(directory), exist_ok=True)

    image_pattern = r'\[\[Image\((.+?\.\w+)(\,\w+)?\)\]\]'
    match = re.findall(image_pattern, text)

    for m in match:
        filename = m[0]

        if filename not in attachment_path.keys():
            print(f'File {filename} from wiki {wiki_name} not found in attachments')
            continue

        path = preprocessing(attachment_path[filename])

        # Removing whitespaces from filename because some systems
        # can't render attachments with whitespace in the name
        new_filename = ''.join(filename.split())

        new_location = f'{directory}{new_filename}'

        new_wiki_name = wiki_name.replace('\\', '/')
        new_location = f"/Attachments/{new_wiki_name}/{new_filename}"

        replacement = f'![{new_filename}]({new_location})'
        text = re.sub(image_pattern, replacement, text, 1)

        shutil.copy(path, new_location)

        if filename in wiki_attachments[wiki_name]:  
            wiki_attachments[wiki_name].remove(filename)

    if len(wiki_attachments[wiki_name]) != 0:
        for filename in wiki_attachments[wiki_name]:
            path = preprocessing(attachment_path[filename])

            # Removing whitespaces from filename because some systems
            # can't render attachments with whitespace in the name
            new_filename = ''.join(filename.split())

            new_location = f'{directory}{new_filename}'
            replacement = f'![{new_filename}]({path})'
            shutil.copy(path, new_location)

        del wiki_attachments[wiki_name]

    return text, wiki_attachments


def format_unordered_lists(text):
    """
    Formats unordered lists.

    Needs to be done before italic text formatting, 
    otherwise the asterix of italic text will be 
    falsely recognized as unordered list syntax.

    Trac markdown: * Item      - Item
                   * Item  or  - Item
                   * Item      - Item
    Standard markdown: - Item
                       - Item
                       - Item

    Args:
        text (str): Text in Trac markdown to be formatted

    Returns:
        text (str): Formatted text in standard markdown
    """
    unordered_list_pattern = r'(?<!\*)\* (.+)\n'

    match = re.findall(unordered_list_pattern, text)

    for m in match:
        replacement = r'- \1\n'
        text = re.sub(unordered_list_pattern, replacement, text, 1)

    return text


def format_tables(text):
    """
    Formats tables by first finding the table header and 
    inserting a horizontal rule after it, and then replacing
    all double || operators with a single | operator.

    The table headers written in bold are formatted 
    separately in the replace_bold function.

    Trac markdown: || '''Header 1''' || '''Header 2''' ||
                   ||    Column 1    ||    Column 2    ||

    Standard markdown: | **Header 1** | **Header 2** |
                       |    ----      |     ----     |
                       |   Column 1   |   Column 2   |

    Args:
        text (str): Text in Trac markdown to be formatted

    Returns:
        text (str): Formatted text in standard markdown
    """
    table_pattern = r"(\|\|\s*'''.+'''\s*\|\|)"

    new_string = ''
    rows = text.splitlines()

    for row in rows:
        new_string += row + '\n'
        if re.match(table_pattern, row, re.MULTILINE):
            columns_count = len(row.split('||')) - 2
            insert = '|'
            for i in range(0, columns_count):
                insert += ' ---- |'
            new_string += insert + '\n'

    new_string = new_string.replace('||', '|')

    return new_string


def format_links(text):
    """
    Formats hyperlinks.

    Must be done before formating other link references, 
    to avoid recursively formatting the link texts with square
    brackets into a new link. These references are: ticket, 
    wiki, report, source, log, title index, and attachments.

    Trac markdown: [link_url link_text]
    Standard markdown: [link text](link url)

    Args:
        text (str): Text in Trac markdown to be formatted

    Returns:
        text (str): Formatted text in standard markdown
    """
    link_pattern = r'\[((https?|www).+?)\s(.+?)\]'
    match = re.findall(link_pattern, text)

    for m in match:
        replacement = r'[\3](\1)'
        text = re.sub(link_pattern, replacement, text, 1)
    
    return text


def format_underline(text):
    """
    Formats underlined text using HTML u-tag.

    Underlined text is not supported in standard Markdown, 
    but this method works if the wiki will be migrated to
    a system which supports HTML text formatting.

    Trac markdown: __text__
    HTML syntax: <u>text</u>

    Args:
        text (str): Text in Trac markdown to be formatted

    Returns:
        text (str): Formatted text in HTML syntax
    """
    underlined_pattern = r'__(.+?)__'
    match = re.findall(underlined_pattern, text)

    for m in match:
        replacement = r'<u>\1</u>'
        text = re.sub(underlined_pattern, replacement, text, 1)

    return text


def format_bold(text):
    """
    Formats bold text.
    
    Must be done after formatting all tables. Table headers are
    usually in bold text and the regex in method format_tables 
    includes only the Trac syntax ('''). If done before tables, 
    ''' in the regex in format_tables should be replaced with **.

    Trac markdown: **text** or '''text'''
    Standard markdown: **text**

    Args:
        text (str): Text in Trac markdown to be formatted

    Returns:
        text (str): Formatted text in standard markdown
    """
    bold_header_pattern = r"'''\s*(.+?)\s*'''"
    replacement = r'**\1**'
    text = re.sub(bold_header_pattern, replacement, text)

    return text


def format_italic(text):
    """
    Formats italic text.

    Must be done after formatting bold text because there 
    is an overlap between the syntax that uses asterisks. 

    Trac markdown: ''text'' or //text//
    Standard markdown: _text_ or *text*

    Args:
        text (str): Text in Trac markdown to be formatted

    Returns:
        text (str): Formatted text in standard markdown
    """
    italics_pattern1 = r"''(.+?)''"
    # Matches only if : doesn't preceed //, to avoid formatting https:// as italic
    italics_pattern2 = r'(?<!:)//(.+?)//'
    match = re.findall(italics_pattern1, text) + re.findall(italics_pattern2, text)

    for m in match:
        replacement = r'*\1*'
        text = re.sub(italics_pattern1, replacement, text, 1)
        text = re.sub(italics_pattern2, replacement, text, 1)

    return text


def format_code_blocks(text):
    """
    Formats simple code blocks and code with language 
    identifiers for SQL, HTML, C#, Python, and XML.

    Without language identifier:
    Trac markdown: {{{ code }}} or ` code `
    Standard markdown: ``` code ``` or ` code `

    With language identifier:
    Trac markdown: {{{ #!language
                    code 
                   }}}
    Standard markdown: ``` language
                        code
                       ```

    Args:
        text (str): Text in Trac markdown to be formatted

    Returns:
        text (str): Formatted text in standard markdown
    """
    text = re.sub(r'\s*\{\{\{\s*#!sql', '\n``` sql', text)
    text = re.sub(r'\s*\{\{\{\s*#!html', '\n``` html', text)
    text = re.sub(r'\s*\{\{\{\s*#!c#', '\n``` c#', text)
    text = re.sub(r'\s*\{\{\{\s*#!python', '\n``` python', text)
    text = re.sub(r'\s*\{\{\{\s*#!xml', '\n``` xml', text)

    text = re.sub(r'\{\{\{', '```', text)
    text = re.sub(r'\}\}\}', '```', text)
        
    return text


def format_horizontal_rule(text):
    """
    Formats horizontal rule.

    Trac markdown: ----
    Standard markdown: \n----

    Args:
        text (str): Text in Trac markdown to be formatted

    Returns:etl
        text (str): Formatted text in standard markdown
    """
    horizontal_line_pattern = r'^\s*-----*\s*$'
    replacement = '\n----'
    text = re.sub(horizontal_line_pattern, replacement, text, re.MULTILINE)

    return text


def format_headers(text):
    """
    Formats headers 1 to header 4 in provided text string. 

    Trac markdown: = Header = or = Header
    Standard markdown: # Header

    Args:
        text (str): Text in Trac markdown to be formatted

    Returns:
        text (str): Formatted text in standard markdown
    """
    header_1_pattern = r'^= ([^=]+)\s?=?\s*(#.+)?$'
    header_2_pattern = r'^== ([^=]+)\s?={0,2}\s*(#.+)?$'
    header_3_pattern = r'^=== ([^=]+)\s?={0,3}\s*(#.+)?$'
    header_4_pattern = r'^==== ([^=]+)\s?={0,4}\s*(#.+)?$'

    match = re.findall(header_4_pattern, text, re.MULTILINE)
    for m in match:
        replacement = r'#### \1\n'
        text = re.sub(header_4_pattern, replacement, text, 1, re.MULTILINE)

    match = re.findall(header_3_pattern, text, re.MULTILINE)
    for m in match:
        replacement = r'### \1\n'
        text = re.sub(header_3_pattern, replacement, text, 1, re.MULTILINE)

    match = re.findall(header_2_pattern, text, re.MULTILINE)
    for m in match:
        replacement = r'## \1\n'
        text = re.sub(header_2_pattern, replacement, text, 1, re.MULTILINE)

    match = re.findall(header_1_pattern, text, re.MULTILINE)
    for m in match:
        replacement = r'# \1\n'
        text = re.sub(header_1_pattern, replacement, text, 1, re.MULTILINE)

    return text


def get_attachments_and_paths(wikis, env, format_only=False):
    """
    Helper method for keeping track of all attachments
    per wiki and their respective paths in the database.
    
    First gets all Attachment objects for each wiki and 
    stores them in wiki_attachments, which is used to 
    keep track of remaining non-image attachments.
    
    Then gets the path of each attachment and stores it in
    attachment_path, which is used to copy the attachment
    from the Trac environment to the new wikis folder.

    Args:
        wikis (list): List of all Wiki objects
        env (trac.env.Environment): Trac Environment object

    Returns:
        wiki_attachments (dict of {str : list}): List of all attachments for each wiki
        attachment_path (dict of {str : str}): Path to each attachment
    """
    wiki_attachments = {}
    attachment_path = {}

    for wiki in wikis:
        if format_only:
            wiki_name = wiki
        else:
            wiki_name = wiki[0]
            
        wiki_attachments[wiki_name] = []

        for a in trac.attachment.Attachment.select(env, 'wiki', wiki_name):
            filename = ' '.join(a.title.split(' ')[1:])
            wiki_attachments[wiki_name].append(filename)
            attachment_path[filename] = a.path

    return wiki_attachments, attachment_path


def get_specific_wiki(env_path, wiki_name):
    """
    Returns the Wiki object with the specified name
    as a tuple containing name, max version, and text.

    Args:
        env_path (str): Path to Trac environment
        wiki_name (str): Full name of the wiki page
    
    Returns:
        wiki (tuple(str, str, str)): Wiki object
    """
    database_connection = sqlite3.connect(f'{env_path}\\db\\trac.db')
    cursor = database_connection.cursor()

    wiki_query = f"""
        select name, max(version) as version, text
        from wiki
        where name = '{wiki_name}'
    """

    wiki = cursor.execute(wiki_query).fetchall()

    return wiki


def get_all_wikis(env_path, date, ignored_wikis):
    """
    Returns all Wiki objects after the specified date
    as tuples containing name, max version, and text. 
    Also returns a list of all wiki names, which is
    used by some of the formatting methods.

    Args:
        env_path (str): Path to Trac environment
        date (str): Date to include wikis from, in format %Y-%m-%d
        ignored_wikis (list of str): Wikis to ignore
    
    Returns:
        wikis (list of tuple(str, str, str)): List of Wiki objects
    """
    database_connection = sqlite3.connect(f'{env_path}\\db\\trac.db')
    cursor = database_connection.cursor()

    trac_timestamp = int(datetime.datetime.strptime(date, r'%Y-%m-%d').timestamp() * (10**6))

    wikis_query = f"""
        select
            name, max(version) as version, text
        from
            wiki
        where 
            time > {trac_timestamp}
        group by name
        order by name
    """

    wikis = cursor.execute(wikis_query).fetchall()

    print('Will handle ignoring of wiki pages.')
    for ignored_wiki in ignored_wikis:
        new_wikis = [wiki for wiki in wikis if not fnmatch.fnmatch(wiki[0], ignored_wiki)]
        ignored_wikis = set(wikis) - set(new_wikis)
        print(f'Will ignore following wiki pages because of pattern {ignored_wiki}:')
        print('\n'.join([f' - {x[0]}' for x in ignored_wikis]))
        wikis = new_wikis
    
    return wikis


def format_all_wikis(env_path, wikis, wiki_attachments, attachment_path, new_wikis_folder, trac_link, docs_link, code_link):
    """
    For each wiki, calls all format functions and then 
    saves the formatted wiki to the specified folder. 
    
    Args:
        env_path (str): Path to the Trac environment
        wikis (list of tuple(str, str, str)): List of Wiki objects containing
                                              name, max version, and text
        wiki_attachments (dict of {str : list}): List of all attachments 
                                                 for each wiki
        attachment_path (dict of {str : str}): Path to each attachment
        new_wikis_folder (str): Path to folder for formatted wikis
        trac_link (str): Your organization's base Trac link
        docs_link (str): Your organization's Trac docs link
        code_link (str): Your organization's Trac code link
    
    Returns:
        None
    """
    for wiki in wikis:
        text = wiki[2]

        text = preprocessing(text)

        # NOTE: Unordered lists must be called before italic
        text = format_unordered_lists(text)

        # NOTE: Regular links must be called before any other type of links
        text = format_links(text)

        text = format_title_index(text, env_path, trac_link)
        text = format_log_links(text, code_link)
        text = format_source_docs(text, docs_link)
        text = format_source_links(text, trac_link)
        text = format_ticket_links(text, trac_link)
        text = format_report_links(text, trac_link)
        text = format_wiki_links(text, trac_link)
        text = format_underline(text)
        text = format_code_blocks(text)
        text = format_horizontal_rule(text)
        text = format_headers(text)
        text = format_tables(text)

        # NOTE: Bold must be called after tables; if done before, ''' in the regex should be replaced with **
        text = format_bold(text)

        # NOTE: Italic must be called after bold
        text = format_italic(text)

        text, wiki_attachments = format_attachments(wiki_attachments, attachment_path, wiki_name, text)

        text = postprocessing(text)

        wiki_name = wiki_name.replace('/', '\\')
        
        file_path = new_wikis_folder + f'\\{wiki_name}.md'
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(text)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-e',
        '--environment',
        help='Path to the Trac environment.',
        nargs='?',
    )
    parser.add_argument(
        '-f',
        '--folder',
        help='Path to folder where the formatted wikis will be saved.',
        nargs='?',
    )
    parser.add_argument(
        '-d',
        '--date',
        help='Earliest date to include wikis from, in format %Y-%m-%d. Defaults to date of first Trac release.',
        required=False,
        default='2004-02-23'
    )
    parser.add_argument(
        '--config',
        default='trac_to_markdown.format_wikis_config',
        help="Path to python config containing `trac_env_path` and `new_wikis_folder`. Can be ignored if setting `environment` and `folder`."
    )
    parser.add_argument(
        '--wiki-name',
        help="Full name of the wiki, in the case of migrating an individual wiki page.",
        required=False
    )

    args = parser.parse_args()

    config = importlib.import_module(args.config)

    env_path = args.environment or config.trac_env_path
    env = trac.env.Environment(env_path, False)

    new_wikis_folder = args.folder or config.new_wikis_folder
    date = args.date

    ignored_wikis = getattr(config, 'ignored_wikis', [])
    
    trac_link = config.trac_link
    docs_link = config.docs_link
    code_link = config.code_link

    wiki_name = args.wiki_name
    
    if wiki_name is not None:
        wikis = get_specific_wiki(env_path, wiki_name)
    else:
        wikis = get_all_wikis(env_path, date, ignored_wikis)

    wiki_attachments, attachment_path = get_attachments_and_paths(wikis, env)

    format_all_wikis(env_path, wikis, wiki_attachments, attachment_path, new_wikis_folder, trac_link, docs_link, code_link)


if __name__ == '__main__':
    main()
