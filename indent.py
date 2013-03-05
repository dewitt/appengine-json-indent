#!/usr/bin/python2.5

import os
import sys

APP_DIR = os.path.abspath(os.path.dirname(__file__))
THIRD_PARTY = os.path.join(APP_DIR, 'third_party')
sys.path.insert(0, THIRD_PARTY)

import httplib2
import logging
import re
import simplejson

from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

TEMPLATE_DIR = 'templates'

EXAMPLE_JSON_URL = 'http://search.yahooapis.com/WebSearchService/V1/webSearch?appid=YahooDemo&query=madonna&results=2&output=json'

# Enable a caching HTTP client
MEMCACHE_CLIENT = memcache.Client()
HTTP_CLIENT = httplib2.Http(MEMCACHE_CLIENT)

UNSAFE_JSON_CHARS = re.compile(r'[^\w\d\-\_]')

class ReportableError(Exception):
  """A class of exceptions that should be shown to the user."""
  message = None

  def __init__(self, message):
    """Constructs a new ReportableError.

    Args:
      message: The message to be logged and displayed to the user.
    """
    self.message = message


class UserError(ReportableError):
  """An 400 error caused by user behavior."""


class ServerError(ReportableError):
  """An 500 error caused by the server."""


class Usage(webapp.RequestHandler):
  """Prints usage information in response to requests to '/'."""
  def get(self):
    self.response.headers['Content-Type'] = 'text/html'
    path = os.path.join(os.path.dirname(__file__), TEMPLATE_DIR, 'usage.tmpl')
    template_vars = {'example_json_url': EXAMPLE_JSON_URL}
    self.response.out.write(template.render(path, template_vars))


class JsonIndent(webapp.RequestHandler):
  """A request handler that indents arbitrary JSON strings."""

  def get(self):
    """Indents the content referred to by the 'content' or 'url' param."""
    content = self.request.get('content', default_value=None)
    if not content:
      url = self.request.get('url', default_value=None)
      if not url:
        raise UserError("Either a 'content' or 'url' parameter is required.")
      content = self._get_url(url)
    content = self._indent(content)
    if self.request.get('color'):
      self._print_color(content)
    else:
      callback = self._sanitize_callback(self.request.get('callback'))
      if callback:
        content = '%s(%s)' % (callback, simplejson.dumps(content))
      self._print(content)

  def post(self):
    """Whitelists the content included in the post body."""
    # If a 'content' element is present in either 'multipart/form-data'
    # or 'application/x-www-form-urlencoded' encodings, use that as the content
    # to be sanitized, otherwise use the entire body
    body = self.request.body
    content = self.request.get('content', default_value=None)
    if content is None:
      content = body
    content = self._indent(content)
    if self.request.get('color'):
      self._print_color(content)
    else:
      callback = self._sanitize_callback(self.request.get('callback'))
      if callback:
        content = '%s(%s)' % (callback, simplejson.dumps(content))
      self._print(content)

  def handle_exception(self, exception, debug_mode):
    if isinstance(exception, UserError):
      logging.error('ServerError: %s' % exception.message)
      self.error(400)
      self._print_error(exception.message)
    elif isinstance(exception, ServerError):
      logging.error('SeverError: %s' % exception.message)
      self.error(500)
      self._print_error(exception.message)
    else:
      super(JsonIndent, self).handle_exception(exception, debug_mode)

  def _print(self, content):
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write(content)
    self.response.out.write("\n")
    
  def _print_color(self, content):
    self.response.headers['Content-Type'] = 'text/html'
    path = os.path.join(os.path.dirname(__file__), TEMPLATE_DIR, 'color.tmpl')
    self.response.out.write(template.render(path, {'content': content}))

  def _print_error(self, message):
    """Prints an error message as type text/plain.

    Args:
      error: The plain text error message.
    """
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write(message)
    self.response.out.write("\n")

  def _indent(self, content):
    """Runs the content through an HTML parser and filter.

    Args:
      content: The JSON string to be indented.
    """
    json = simplejson.loads(content)
    return simplejson.dumps(json, sort_keys=True, indent=2)

  def _get_url(self, url):
    """Retrieves a URL and caches the results.

    Args:
      url: A url to be fetched
    """
    try:
      response, content = HTTP_CLIENT.request(url)
    except Exception, e:  # This is hackish
      raise ServerError('Could not fetch %s. Host down?' % url)
    if response.status != 200:
      raise ServerError(
        "Could not fetch url '%s': %s." % (url, response.status))
    return content

  def _sanitize_callback(self, string):
    """Only allow valid json function identifiers through"""
    if UNSAFE_JSON_CHARS.search(string):
      return None
    else:
      return string

application = webapp.WSGIApplication([('/indent/?', JsonIndent),
                                      ('/', Usage)],
                                     debug=True)


def main():
  run_wsgi_app(application)


if __name__ == "__main__":
  main()
