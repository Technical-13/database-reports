#! /usr/bin/env python
# Public domain; MZMcBride; 2011

import datetime
import codecs
import re
import MySQLdb
import wikitools
import settings

def get_target_templates_list():
    return ['Infobox_officeholder']

def get_template_parameters_from_template(template):
    template_parameters = set()
    template_text = wikitools.Page(wiki, 'Template:'+template).getWikiText()
    legal_chars = r'[ %!"$&\'()*,\-.0-9:;?@A-Z^_`a-z~\x80-\xFF]'
    legal_chars_spaceless = r'[%!"$&\'()*,\-.0-9:;?@A-Z^_`a-z~\x80-\xFF]'
    dynamic_parameter_re = re.compile(r'('+
                                      legal_chars_spaceless + '+' +
                                      r')\{\{#if:\{\{\{(' +
                                      legal_chars + '+' +
                                      r')\|\}\}\}\|(' +
                                      legal_chars + '*' +
                                      r')\|(' +
                                      legal_chars + '*' +
                                      r')\}\}(' +
                                      legal_chars + '+' +
                                      r')')
    for match in dynamic_parameter_re.finditer(template_text):
        parameter_name_1 = match.group(1)+match.group(3)+match.group(5)
        parameter_name_2 = match.group(1)+match.group(4)+match.group(5)
        template_parameters.add(parameter_name_1)
        template_parameters.add(parameter_name_2)
    parameter_re = re.compile(r'\{\{\{([ %!"$&\'()*,\-.0-9:;?@A-Z^_`a-z~\x80-\xFF]+)(\||\})', re.I|re.MULTILINE)
    for match in parameter_re.finditer(template_text):
        template_parameters.add(match.group(1).strip())
    return template_parameters

def get_articles_list(cursor, template):
    articles_list = []
    cursor.execute('''
                   /* bullshitparams.py SLOW_OK */
                   SELECT
                     page_title
                   FROM page
                   JOIN templatelinks
                   ON tl_from = page_id
                   WHERE tl_namespace = 10
                   AND tl_title = %s
                   AND page_namespace = 0
                   AND page_is_redirect = 0;
                   ''' , template)
    for row in cursor.fetchall():
        article = unicode(row[0], 'utf-8')
        articles_list.append(article)
    return articles_list

def get_template_parameters_from_article(article, templates):
    article_parameters = set()
    inner_template_re = re.compile(r'\{\{[^}]+\}\}', re.I|re.MULTILINE)
    parameter_re = re.compile(r'\|\s*([ %!"$&\'()*,\-.0-9:;?@A-Z^_`a-z~\x80-\xFF]+)\s*=', re.I|re.MULTILINE)
    article_text = wikitools.Page(wiki, article).getWikiText()
    for template in templates:
        template_re = re.compile(r'\{\{\s*%s\s*(.*?)\}\}' % template.replace('_', r'[\s_]*'), re.I|re.MULTILINE|re.DOTALL)
        if not template_re.search(article_text):
            continue
        string_start_position = template_re.search(article_text).start()
        shit_re = re.compile(r'(\{\{|\{\{\{|\}\}|\}\}\})')
        start_shit_re = re.compile(r'(\{\{|\{\{\{)')
        end_shit_re = re.compile(r'(\}\}|\}\}\})')
        start_matches = 0
        end_matches = 0
        for match in shit_re.finditer(article_text[string_start_position:]):
            if start_shit_re.search(match.group(0)):
                start_matches += 1
            elif end_shit_re.search(match.group(0)):
                string_end_position = match.end()
                end_matches += 1
            if start_matches == end_matches:
                template_content = article_text[string_start_position:string_end_position+string_start_position]
                for match in inner_template_re.finditer(template_content[2:]):
                    template_content = re.sub(re.escape(match.group(0)), '', template_content)
                break
        for match in parameter_re.finditer(template_content):
            article_parameter = match.group(1).strip()
            article_parameters.add(article_parameter)
    return article_parameters

report_title = settings.rootpage + 'Articles containing bullshit template parameters'

report_template = u'''\
Articles containing bullshit template parameters (limited to approximately \
the first 1000 entries); data as of <onlyinclude>%s</onlyinclude>.

{| class="wikitable sortable plainlinks" style="width:100%%; margin:auto;"
|- style="white-space:nowrap;"
! No.
! Page
! Parameter
|-
%s
|}
'''

wiki = wikitools.Wiki(settings.apiurl); wiki.setMaxlag(-1)
wiki.login(settings.username, settings.password)

conn = MySQLdb.connect(host=settings.host,
                       db=settings.dbname,
                       read_default_file='~/.my.cnf')
cursor = conn.cursor()

target_templates = get_target_templates_list()

bullshit_parameters = []

f = codecs.open('%sbullshit-reviewed-page-titles.txt' % settings.path, 'r', 'utf-8')
reviewed_page_titles = f.read()
reviewed_page_titles_list = reviewed_page_titles.split('\n')
f.close()

g = codecs.open('%sbullshit-reviewed-page-titles.txt' % settings.path, 'a', 'utf-8')

count = 1
for template in target_templates:
    if count > 1000:
        break
    articles_list = get_articles_list(cursor, template)
    template_parameters = get_template_parameters_from_template(template)
    for article in articles_list:
        if count > 1000:
            break
        if article in reviewed_page_titles:
            continue
        article_parameters = get_template_parameters_from_article(article, target_templates)
        bullshit_parameters_count = 0
        for i in article_parameters-template_parameters:
            bullshit_parameters.append([article, i])
            count += 1
            bullshit_parameters_count += 1
        if bullshit_parameters_count == 0:
            g.write(article+'\n')
g.close()

i = 1
output = []
for bullshit_parameter in bullshit_parameters:
    page_title = u'{{dbr link|1='+bullshit_parameter[0].replace('_', ' ')+u'}}'
    parameter = bullshit_parameter[1]
    table_row = u'''| %d
| %s
| %s
|-''' % (i, page_title, parameter)
    output.append(table_row)
    i += 1

cursor.execute('''
               SELECT
                 UNIX_TIMESTAMP() - UNIX_TIMESTAMP(rc_timestamp)
               FROM recentchanges
               ORDER BY rc_timestamp DESC
               LIMIT 1;
               ''')
rep_lag = cursor.fetchone()[0]
time_diff = datetime.datetime.utcnow() - datetime.timedelta(seconds=rep_lag)
current_of = time_diff.strftime('%H:%M, %d %B %Y (UTC)')

report = wikitools.Page(wiki, report_title)
report_text = report_template % (current_of, '\n'.join(output))
report_text = report_text.encode('utf-8')
report.edit(report_text, summary=settings.editsumm, bot=1)

cursor.close()
conn.close()
