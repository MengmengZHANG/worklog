#!/usr/bin/env python

# pre
import site
import os.path
ROOT = os.path.abspath(os.path.dirname(__file__))
path = lambda *a: os.path.join(ROOT,*a)
site.addsitedir(path('vendor'))

# python
import re
from mongokit import Connection, Document as mongokit_Document
import logging
import redis

# tornado
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado.options import define, options

# app
import settings
from tornado_utils.routes import route
from utils.git import get_git_revision

################################################################################
# original
# define("debug", default=False, help="run in debug mode", type=bool)
# define("port", default=8080, help="run on the given port", type=int)
# define("database_name", default=settings.DATABASE_NAME, help="mongodb database name")
# define("prefork", default=False, help="pre-fork across all CPUs", type=bool)
# define("showurls", default=False, help="Show all routed URLs", type=bool)
# define("dont_combine", default=False, help="Don't combine static resources", type=bool)
# define("dont_embed_static_url", default=False,
#        help="Don't put embed the static URL in static_url()", type=bool)

define("debug", default=True, help="run in debug mode", type=bool)
define("port", default=8080, help="run on the given port", type=int)
define("database_name", default=settings.DATABASE_NAME, help="mongodb database name")
define("prefork", default=False, help="pre-fork across all CPUs", type=bool)
define("showurls", default=False, help="Show all routed URLs", type=bool)
define("dont_combine", default=True, help="Don't combine static resources", type=bool)
define("dont_embed_static_url", default=True,
       help="Don't put embed the static URL in static_url()", type=bool)


class Application(tornado.web.Application):
    def __init__(self,
                 database_name=None,
                 xsrf_cookies=True,
                 optimize_static_content=None):
        ui_modules_map = {}
        for app_name in settings.APPS:
            # XXX consider replacing this with use of tornado.util.import_object
            _ui_modules = __import__('apps.%s' % app_name, globals(), locals(),
                                     ['ui_modules'], -1)
            try:
                ui_modules = _ui_modules.ui_modules
            except AttributeError:
                # this app simply doesn't have a ui_modules.py file
                continue

            for name in [x for x in dir(ui_modules) if re.findall('[A-Z]\w+', x)]:
                thing = getattr(ui_modules, name)
                try:
                    if issubclass(thing, tornado.web.UIModule):
                        ui_modules_map[name] = thing
                except TypeError:
                    # most likely a builtin class or something
                    pass

        if options.dont_combine:
            ui_modules_map['Static'] = ui_modules_map['PlainStatic']
            ui_modules_map['StaticURL'] = ui_modules_map['PlainStaticURL']

        try:
            cdn_prefix = [x.strip() for x in file('cdn_prefix.conf')
                             if x.strip() and not x.strip().startswith('#')][0]
            #logging.info("Using %r as static URL prefix" % cdn_prefix)
        except (IOError, IndexError):
            cdn_prefix = None

        # unless explicitly set, then if in debug mode, disable optimization
        # of static content
        if optimize_static_content is None:
            optimize_static_content = not options.debug

        handlers = route.get_routes()
        app_settings = dict(
            title=settings.TITLE,
            template_path=os.path.join(os.path.dirname(__file__), "apps", "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            embed_static_url_timestamp=True and not options.dont_embed_static_url,
            ui_modules=ui_modules_map,
            xsrf_cookies=xsrf_cookies,
            cookie_secret=settings.COOKIE_SECRET,
            login_url=settings.LOGIN_URL,
            debug=options.debug,
            optimize_static_content=optimize_static_content,
            git_revision=get_git_revision(),
            email_backend=options.debug and \
                 'utils.send_mail.backends.console.EmailBackend' \
              or 'utils.send_mail.backends.smtp.EmailBackend',
            webmaster=settings.WEBMASTER,
            admin_emails=settings.ADMIN_EMAILS,
            CLOSURE_LOCATION=os.path.join(os.path.dirname(__file__),
                                      "static", "compiler.jar"),
            YUI_LOCATION=os.path.join(os.path.dirname(__file__),
                                      "static", "yuicompressor-2.4.2.jar"),
            UNDOER_GUID=u'UNDOER', # must be a unicode string
            cdn_prefix=cdn_prefix,
        )
        tornado.web.Application.__init__(self, handlers, **app_settings)

        # Have one global connection to the blog DB across all handlers
        self.database_name = database_name and database_name or options.database_name
        self.con = Connection()
        self.redis = redis.client.Redis(settings.REDIS_HOST,
                                        settings.REDIS_PORT)

        model_classes = []
        for app_name in settings.APPS:
            _models = __import__('apps.%s' % app_name, globals(), locals(),
                                     ['models'], -1)
            try:
                models = _models.models
            except AttributeError:
                # this app simply doesn't have a models.py file
                continue
            for name in [x for x in dir(models) if re.findall('[A-Z]\w+', x)]:
                thing = getattr(models, name)
                if issubclass(thing, mongokit_Document):
                    model_classes.append(thing)

        self.con.register(model_classes)

for app_name in settings.APPS:
    __import__('apps.%s' % app_name, globals(), locals(), ['handlers'], -1)

def main(): # pragma: no cover
    tornado.options.parse_command_line()
    if options.showurls:
        for each in route.get_routes():
            path = each[0]
            if len(each) == 3 and 'url' in each[2]:
                print path, '-->', each[2]['url']
            else:
                print path
        return

    if os.path.isfile('static_index.html'):
        import warnings
        warnings.warn("Running with static_index.html")
    http_server = tornado.httpserver.HTTPServer(Application())
    print "Starting tornado on port", options.port
    if options.prefork:
        print "\tpre-forking"
        http_server.bind(options.port)
        http_server.start()
    else:
        http_server.listen(options.port)

    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
