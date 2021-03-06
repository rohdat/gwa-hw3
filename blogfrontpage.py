#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import webapp2
import cgi
import jinja2 
import time
from google.appengine.ext import db
from google.appengine.ext import ndb
from google.appengine.api import memcache
import datetime
import logging
import json
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# What is the directory where the templates (aka HTML) is stored?
# that's template_dir. the RHS joins the /templates to the current working directory returned by path_dirname

template_dir = os.path.join(os.path.dirname(__file__), 'templates')

# tell the jinja environment where this template directory is when instantiating it
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape=True)


class Handler (webapp2.RequestHandler):
    def write (self, *a, **kw):
        self.response.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def render_json(self, template, **kw):
    	template = json.dumps(template)
        self.write(template)
        self.response.headers['Content-Type'] = 'application/json; charset=utf-8'



class Blogs (ndb.Model):
	title = ndb.StringProperty(required=True)
	content = ndb.TextProperty(required=True)
	json_repr = ndb.JsonProperty()
	created = ndb.DateTimeProperty(auto_now_add=True)

	def write_json(self):
		self.json_repr = {'title': self.title, 'content' : self.content, 'created' : self.created}

def get_time():
	return time.strftime('%a %b %c')


def get_posts(update = False):
	key = 'top'
	posts = memcache.get(key)
	if posts is None or update:
		posts = Blogs.query().order(-Blogs.created)
		posts = posts.fetch(3)
		logging.error("NDB QUERY")
		posts = list(posts)
		memcache.set(key, posts)
		memcache.set('last_q', 0)
	return posts	


class BlogFrontPageHandler(Handler):

	_use_json = False
	def render_front(self):
		# blogs = db.GqlQuery("SELECT * FROM Blogs "
		# 					"ORDER BY created DESC")
		# blogs = Blogs.query().order(-Blogs.title)
		# blogs = Blogs.query().order(-Blogs.created)
		update = memcache.get('stale')
		print "UPDATE = %s"%update
		if update == None:
			update = True
		blogs = get_posts(update=update)
		memcache.set('stale', False)
		blogs_json = []
		for blog in blogs:
			blogs_json.append(blog.json_repr)

		if blogs and not self._use_json:
			self.render('base.html', blogs=blogs)
		elif self._use_json:
			self.render_json(blogs_json)

	def render_timestamps(self):
		last_up = memcache.get('last_up')
		if not last_up:
			last_up = get_time()
			memcache.set('last_up',last_up)
		self.write("Last updated %s"%last_up)
		last_q = memcache.get('last_q')
		if not last_q:
			last_q = datetime.datetime.now()
			memcache.set('last_q', last_q)
		now = datetime.datetime.now()
		tdiff = now - last_q
		tdiff = tdiff.seconds
		self.write("\n")
		self.write("Queried %s seconds ago"%tdiff)

	def get(self, json_expr):
		if json_expr:
			self._use_json = True
		self.render_front()
		self.render_timestamps()
		

	def post(self):
		pass

class NewPostHandler(Handler):
	def render_front(self, error="", subject="", content=""):
		self.render('newpost.html', error=error, subject=subject, content=content)

	def get(self):
		self.render_front()

	def post(self):
		subject = self.request.get("subject")
		content = self.request.get("content")
		content = content.replace('\n', '<br>')
        #self._render_text = self.content.replace('\n', '<br>')

		if  subject and content:
			blog = Blogs(title=subject, content=content)
			blog.write_json()
			blog_post_id = blog.put().id()
			time.sleep(1)
			# blog_post_id = blog.key().id()
			# blog_post_id = int(blog_post_id)
			redir_addr = '/newpost/%s'%blog_post_id
			self.redirect(redir_addr)
		else:
			self.render_front(error="Needs subject and content", subject=subject, content=content)


class NewPostRenderHandler(Handler):
	_use_json = False
	def render_front(self, blog_id=""):
		blog_id = int(blog_id)

		# Huzzah! I figured this out
		# First get the key using id
		# Then get the titty using get() on the key
		blogs = ndb.Key("Blogs", blog_id)
		blogs = blogs.get()
		blogs = [blogs]
		blogs_json = []
		memcache.set('last_up', get_time())
		for blog in blogs:
			blogs_json.append(blog.json_repr)
		if blogs and not self._use_json:
			self.render('base.html', blogs=blogs)
		elif self._use_json:
			self.render_json(blogs_json)

	def get(self, blog_id, json_expr):
		if json_expr:
			self._use_json = True
		self.render_front(blog_id=blog_id)
		memcache.set('stale', True)
