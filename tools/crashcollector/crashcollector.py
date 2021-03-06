#!/usr/bin/env python

from wsgiref.simple_server import make_server
import os, os.path, sys
import cgi, urlparse
import random, string
import subprocess
import time

site_name = 'http://crashes.sirikata.com'
id_file = 'data/__id'

def server_file(*args):
    return os.path.join( os.path.dirname(__file__), *args )

def load_file(path):
    f = open(server_file(path), 'rb')
    r = f.read()
    f.close()
    return r

def save_file(path, data):
    f = open(server_file(path), 'wb')
    f.write(data)
    f.close()

def get_id():
    """Get a unique id to assign to a report."""
    if not os.path.exists(server_file(id_file)):
        id = 0
    else:
        id = int( load_file(id_file) )

    save_file(id_file, str(id+1))

    return id

def random_key():
    """ Get a random key to store with a dump that will enable editing."""
    res = ''

    random.seed()
    for x in range(32):
        res += random.choice(string.hexdigits)

    return res

def id_exists(id):
    """Checks if we have state associated with an id."""
    id_dir = server_file('data/' + str(id))
    return os.path.exists(id_dir)

def id_date(id):
    return time.gmtime(os.path.getctime(server_file('data/' + str(id) + '/key')))

def id_lookup(id):
    """Lookup all the data associated with an id."""
    if not id_exists(id): return None
    res = { 'id' : id }

    id_dir = server_file('data/' + str(id))
    res['dumps'] = [x for x in os.listdir(id_dir) if x.endswith('.dmp')]
    if os.path.exists(id_dir + '/desc'):
        res['desc'] = load_file(id_dir + '/desc')
    else:
        res ['desc'] = ''
    res['key'] = load_file(id_dir + '/key')
    res['date'] = id_date(id)
    if os.path.exists(id_dir + '/version'):
        res['version'] = load_file(id_dir + '/version')
    else:
        res['version'] = ''
    if os.path.exists(id_dir + '/githash'):
        res['githash'] = load_file(id_dir + '/githash')
    else:
        res['githash'] = ''

    return res

def id_list():
    ids = os.listdir(server_file('data/'))
    ids = [int(x) for x in ids if x != '__id']
    return ids

def id_link(id, text=None):
    return '<a href="' + '/status/' + str(id) + '">' + (text or str(id)) + '</a>'

def id_get_stackwalk(id, dump, force=False):
    """Gets the stackwalk for a dump within a crash report. The report
    is cached, but can be forced to regenerate using force=True."""
    dump_file = server_file('data', str(id), dump)
    stackwalk_file = server_file('data', str(id), dump + '.stackwalk')
    if not force and os.path.exists(stackwalk_file):
        return load_file(stackwalk_file)
    bt = subprocess.Popen([server_file('minidump_stackwalk'), dump_file, server_file('symbols')], stdout=subprocess.PIPE).communicate()[0]
    if bt:
        save_file(stackwalk_file, bt)
        return bt
    return "Couldn't generate backtrace."

def is_post(environ):
    return environ['REQUEST_METHOD'].upper() == 'POST'

def decode_post(environ):
    if environ['REQUEST_METHOD'].upper() != 'POST':
        return None
    content_type = environ.get('CONTENT_TYPE', 'application/x-www-form-urlencoded')
    if not (content_type.startswith('application/x-www-form-urlencoded') or
            content_type.startswith('multipart/form-data')):
        return None

    post_form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ, keep_blank_values=True)
    return post_form

def report(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'text/plain')]
    start_response(status, headers)

    post_form = decode_post(environ)
    if not post_form or not 'dump' in post_form or not 'dumpname' in post_form:
        return ''

    dump = post_form['dump'].value
    dump_name = post_form['dumpname'].value
    siri_version = post_form['version'].value
    siri_githash = post_form['githash'].value

    id = get_id()
    # generate a magic key that allows editing
    magic = random_key()

    id_dir = 'data/' + str(id)
    os.makedirs(server_file(id_dir))
    save_file(id_dir + '/' + dump_name, dump)
    save_file(id_dir + '/' + 'key', magic)
    save_file(id_dir + '/' + 'version', siri_version)
    save_file(id_dir + '/' + 'githash', siri_githash)

    return [site_name + '/edit/' + str(id) + '?edit=' + magic]

def wrap_html(inner):
    """Wraps inner contents of an html page inside html and body tags."""
    res = ['<html><body>']
    if isinstance(inner, list):
        res += inner
    else:
        res += [inner]
    res += ['</body></html>']
    return res

def status_page(environ, start_response, id):
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    start_response(status, headers)

    # Very simple check -- if we used POST (hit button rather than
    # normal GETting the URL) then reanalyze.
    reanalyze = is_post(environ)

    dump = id_lookup(id)
    if not dump:
        return wrap_html('Report' + str(id) + ' not found.')

    result = []
    result += ['<h3>Report ', id_link(id), '</h3>']

    result += ['<form action="/status/', str(id), '" method="POST">']
    result += ['<input type="submit" value="Reanalyze"></input>']
    result += ['</form>']

    result += ['Date: ', time.strftime("%a, %d %b %Y %H:%M:%S", dump['date']), '<br>']
    if dump['version']:
        result += ['Version: ', dump['version'], '<br>']
    if dump['githash']:
        result += ['Git Revision: ', dump['githash'], '<br>']
    if dump['desc']:
        result += ['Description:<br><pre>', dump['desc'], '</pre>']
    for d in dump['dumps']:
        result += ['Dump: ', d, '<br>']
        bt = id_get_stackwalk(id, d, force=reanalyze)
        result += ['<pre>', bt, '</pre>', '<br>']

    return wrap_html(result)

def edit_page(environ, start_response, id):
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    start_response(status, headers)

    dump = id_lookup(id)
    if not dump:
        return wrap_html('Report' + str(id) + ' not found.')

    # Edit has 2 cases. If this is a post, then we need to check keys, update
    # the description, and then we give them the edit page again.
    posted = False
    post_form = decode_post(environ)
    print >>environ['wsgi.errors'], post_form, dump['key']
    if post_form and 'edit' in post_form and 'desc' in post_form:
        if post_form['edit'].value == dump['key']:
            posted = True
            save_file

            id_dir = server_file('data/' + str(id))
            save_file(id_dir + '/desc', post_form['desc'].value)
            dump['desc'] = post_form['desc'].value

    # Otherwise, we need to use a query string in order to get everything
    # in a URL when we direct the user to this page from the initial report.
    query_string = environ.get("QUERY_STRING","").strip()
    argset = urlparse.parse_qs(query_string, keep_blank_values=True, strict_parsing=False)
    if ('edit' in argset and argset['edit'][0] == dump['key']) or posted:
        result = []
        result += ['<h3>Edit Report ', id_link(id), '</h3>']
        if posted:
            result += ['<h4>Successfully updated!</h4>']
        result += ['<form action="/edit/', str(id), '" method="POST">']
        result += ['<h4>Description</h4>']
        result += ['<textarea name="desc" rows=30 cols=80>', dump['desc'] ,'</textarea><br>']
        result += ['<input type="hidden" name="edit" value="' + dump['key'] + '"></input>']
        result += ['<input type="submit" value="Update"></input>']
        result += ['</form>']
        return wrap_html(result)

    # And if nothing else, they just aren't authorized.
    return wrap_html('You can\'t edit report ' + str(id) + '.')

def listing(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    start_response(status, headers)

    listing = id_list()
    if not listing:
        return wrap_html('No reports found.')
    listing.sort()
    listing.reverse()
    listing = listing[:100] # Max 100 items to cap load

    result = []
    result += ['<h3>Report List</h3>']
    result += ['<ul>']
    for id in listing:
        dump = id_lookup(id)
        result += ['<li>', id_link(id), ' - ', time.strftime("%d %b %Y", dump['date'])]
        if dump['version']:
            result += [' Version: ', dump['version']]
        if dump['desc']:
            result += [': <pre>', dump['desc'], '</pre>']
        result += ['</li>']
    result += ['</ul>']

    return wrap_html(result)

def crashcollector_app(environ, start_response):
    url = environ.get("REDIRECT_TEMPLATEPAGE", environ.get("REDIRECT_URL", None))

    if url.startswith('/report'):
        return report(environ, start_response)
    elif url.startswith('/edit/'):
        url = url.replace('/edit/', '')
        return edit_page(environ, start_response, int(url))
    elif url.startswith('/status/'):
        url = url.replace('/status/', '')
        return status_page(environ, start_response, int(url))
    elif url.startswith('/listing') or url == '/':
        return listing(environ, start_response)

    status = '200 OK'
    headers = [('Content-type', 'text/plain')]
    start_response(status, headers)

    return ['']

application = crashcollector_app

if __name__ == "__main__":
    httpd = make_server('', 8000, crashcollector_app)
    httpd.serve_forever()
