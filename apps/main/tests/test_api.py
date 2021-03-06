from bson.objectid import ObjectId
import datetime
import simplejson as json
from time import mktime
import base
from apps.main.config import MINIMUM_DAY_SECONDS

class APITestCase(base.BaseHTTPTestCase):

    def test_getting_events(self):
        response = self.get('/api/events.json')
        self.assertEqual(response.code, 404)
        self.assertTrue('guid not supplied' in response.body)
        self.assertTrue('text/plain' in response.headers['Content-type'])

        response = self.get('/api/events.json', dict(guid='xxx'))
        self.assertEqual(response.code, 403)
        self.assertTrue('guid not recognized' in response.body)

        peter = self.get_db().users.User()
        assert peter.guid
        peter.save()

        assert self.get_db().users.User.find().count()
        data = dict(guid=peter.guid)
        response = self.get('/api/events.json', data)
        self.assertEqual(response.code, 404)
        self.assertTrue('start timestamp not' in response.body)

        today = datetime.date.today()
        first = datetime.date(today.year, today.month, 1)

        data['start'] = int(mktime(first.timetuple()))
        response = self.get('/api/events.json', data)
        self.assertEqual(response.code, 404)
        self.assertTrue('end timestamp not' in response.body)

        if today.month == 12:
            last = datetime.datetime(today.year + 1, 1, 1)
        else:
            last = datetime.datetime(today.year, today.month + 1, 1)

        data['end'] = int(mktime(last.timetuple()))
        response = self.get('/api/events.json', data)
        self.assertEqual(response.code, 200)
        self.assertTrue('application/json' in response.headers['Content-Type'])
        self.assertTrue('UTF-8' in response.headers['Content-Type'])
        self.assertTrue('start timestamp not' not in response.body)
        self.assertTrue('end timestamp not' not in response.body)

        struct = json.loads(response.body)
        self.assertEqual(struct.get('events'), [])
        self.assertTrue('tags' not in struct)

        response = self.get('/api/events.json',
                            dict(data, include_tags='yes'))
        struct = json.loads(response.body)
        self.assertEqual(struct.get('tags'), None)

        response = self.get('/api/events.json',
                            dict(data, refresh=True, include_tags='yes'))
        struct = json.loads(response.body)
        self.assertEqual(struct.get('tags'), [])

        response = self.get('/api/events.txt', dict(data))
        self.assertEqual(response.code, 200)
        self.assertTrue('ENTRIES' in response.body)
        self.assertTrue('TAGS' not in response.body)

        response = self.get('/api/events.txt', dict(data, include_tags='yes'))
        self.assertEqual(response.code, 200)
        self.assertTrue('ENTRIES' in response.body)
        self.assertTrue('TAGS' in response.body)

        # post an event
        event1 = self.get_db().events.Event()
        event1.user = peter
        event1.title = u"Test1"
        event1.all_day = True
        event1.start = datetime.datetime.today()
        event1.end = datetime.datetime.today()
        event1.external_url = u'http://www.peterbe.com'
        event1.description = u'A longer description'
        event1.save()

        response = self.get('/api/events.json', dict(data, refresh=True))
        struct = json.loads(response.body)
        self.assertTrue(struct.get('events'))
        self.assertEqual(len(struct['events']), 1)
        self.assertEqual(struct['events'][0]['title'], event1.title)
        self.assertEqual(struct['events'][0]['id'], str(event1._id))
        self.assertEqual(struct['events'][0]['allDay'], True)
        self.assertEqual(struct['events'][0]['external_url'], event1.external_url)
        self.assertEqual(struct['events'][0]['description'], event1.description)
        self.assertTrue('tags' not in struct)
        #self.assertEqual(struct.get('tags'), [])

        # test the ultra-compact .js format which is a JSON type structure
        # but as a list instead of a hash table
        response = self.get('/api/events.js', data)
        self.assertEqual(response.code, 200)
        # the javascript format is a JSON format but instead of dict it's
        # returned as a tuple
        struct = json.loads(response.body)
        list1 = struct['events'][0]
        self.assertEqual(list1[0], event1.title)
        self.assertEqual(list1[1], mktime(event1.start.timetuple()))
        self.assertEqual(list1[2], mktime(event1.end.timetuple()))
        self.assertEqual(list1[3], True)
        self.assertEqual(list1[4], str(event1._id))
        self.assertEqual(list1[5], event1.external_url)
        self.assertEqual(list1[6], event1.description)

        # some time in the middle of the current month
        this_month = datetime.datetime(today.year, today.month, 15, 13, 0)
        next_month = this_month + datetime.timedelta(days=30)
        event2 = self.get_db().events.Event()
        event2.user = peter
        event2.title = u"Test2"
        event2.all_day = False
        event2.start = next_month
        event2.end = next_month + datetime.timedelta(minutes=60)
        event2.tags = [u'Tag']
        event2.save()

        response = self.get('/api/events.json', dict(data, refresh=True))
        struct = json.loads(response.body)
        self.assertEqual(len(struct['events']), 1)
        self.assertTrue('tags' not in struct)
        #self.assertEqual(struct.get('tags'), [])

        data['start'] += 60 * 60 * 24 * 30
        data['end'] += 60 * 60 * 24 * 30
        response = self.get('/api/events.json', data)
        struct = json.loads(response.body)
        self.assertEqual(len(struct['events']), 1)
        self.assertEqual(struct['events'][0]['title'], event2.title)
        response = self.get('/api/events.json', dict(data, include_tags='all'))
        struct = json.loads(response.body)

        response = self.get('/api/events.xml', data)
        self.assertEqual(response.code, 200)
        xml = response.body
        #print xml
        self.assertTrue('<allDay>false</allDay>' in xml)
        self.assertTrue('external_url' not in xml)
        self.assertTrue('description' not in xml)
        response = self.get('/api/events.xml', dict(data, include_tags='all'))
        xml = response.body
        self.assertTrue('<tag>@Tag</tag>' in xml)


    def test_posting_events(self):
        response = self.post('/api/events.json', {})
        self.assertEqual(response.code, 404)
        self.assertTrue('guid not supplied' in response.body)
        self.assertTrue('text/plain' in response.headers['Content-type'])

        response = self.post('/api/events.json', dict(guid='xxx'))
        self.assertEqual(response.code, 403)
        self.assertTrue('guid not recognized' in response.body)

        peter = self.get_db().users.User()
        assert peter.guid
        peter.save()

        assert self.get_db().users.User.find().count()
        data = dict(guid=peter.guid)
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 400)
        self.assertTrue('title' in response.body)

        data['title'] = u"<script>alert('xss')</script> @tagged "\
                        u"but not mail@gmail.com"
        today = datetime.date.today()
        data['date'] = mktime(today.timetuple())
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 201)
        self.assertTrue('</script>' not in response.body)
        struct = json.loads(response.body)

        self.assertEqual(struct['event']['allDay'], True)
        self.assertEqual(struct['event']['title'], data['title'])
        self.assertEqual(struct['tags'], ['@tagged'])
        self.assertTrue(struct['event'].get('id'))

        event = self.get_db().events.Event.one({'_id': ObjectId(struct['event']['id'])})
        self.assertEqual(event.user['_id'], peter['_id'])
        self.assertEqual(event['tags'], ['tagged'])

        self.assertEqual(self.get_db().events.Event.find().count(), 1)
        # post the same thing again
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 200)
        struct_again = json.loads(response.body)
        self.assertEqual(struct_again, struct)

        # Post and expect XML
        response = self.post('/api/events.xml', data)
        self.assertEqual(response.code, 200)
        self.assertTrue('<allDay>true</allDay>' in response.body)
        self.assertTrue('<title>&lt;script&gt;' in response.body)
        self.assertTrue('<tag>@tagged</tag>' in response.body)

    def test_posting_with_description(self):
        peter = self.get_db().users.User()
        assert peter.guid
        peter.save()

        assert self.get_db().users.User.find().count()
        data = dict(guid=peter.guid,
                    title="Sample Title",
                    description="\tSample Description  ")

        today = datetime.date.today()
        data['date'] = mktime(today.timetuple())
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 201)
        struct = json.loads(response.body)
        event = self.get_db().Event.one()
        self.assertEqual(event.description, data['description'].strip())
        self.assertEqual(struct['event']['description'], data['description'].strip())

    def test_posting_with_external_url(self):
        peter = self.get_db().users.User()
        assert peter.guid
        peter.save()

        assert self.get_db().users.User.find().count()
        today = datetime.date.today()
        data = dict(guid=peter.guid,
                    title="Sample Title",
                    external_url=" not a valid URL",
                    date=mktime(today.timetuple()),
                    )

        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 400)
        data['external_url'] = 'http://www.peterbe.com     '
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 201)
        struct = json.loads(response.body)
        event = self.get_db().Event.one()
        self.assertEqual(event.external_url, data['external_url'].strip())
        self.assertEqual(struct['event']['external_url'], data['external_url'].strip())


    def test_posting_without_date(self):

        peter = self.get_db().users.User()
        assert peter.guid
        peter.save()

        data = dict(guid=peter.guid, title="Title")
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 201)

        event = self.get_db().events.Event.one()
        today = datetime.date.today()
        self.assertEqual(today.strftime('%Y%m%d%H%M'),
                         event.start.strftime('%Y%m%d%H%M'))
        self.assertEqual(today.strftime('%Y%m%d%H%M'),
                         event.end.strftime('%Y%m%d%H%M'))
        self.assertEqual(event.all_day, True)

        data = dict(guid=peter.guid, title=u"Title2")
        data['date'] = mktime(today.timetuple())
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 201)
        event = self.get_db().events.Event.one(dict(title=data['title']))
        self.assertEqual(event.all_day, True)

        # posting without specifying all_day and then set the hour
        today = datetime.datetime.today()
        data = dict(guid=peter.guid, title=u"Title3")
        data['date'] = mktime(today.timetuple())
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 201)
        event = self.get_db().events.Event.one(dict(title=data['title']))
        self.assertEqual(event.all_day, False)
        # this should have made the end date to be 1 hour from now
        self.assertEqual(today.strftime('%Y%m%d%H%M'),
                         event.start.strftime('%Y%m%d%H%M'))
        from apps.main.config import MINIMUM_DAY_SECONDS
        self.assertEqual((today + datetime.timedelta(seconds=MINIMUM_DAY_SECONDS
          )).strftime('%Y%m%d%H%M'),
                         event.end.strftime('%Y%m%d%H%M'))

    def test_posting_invalid_data(self):

        peter = self.get_db().users.User()
        assert peter.guid
        peter.save()
        from apps.main.config import MAX_TITLE_LENGTH

        data = dict(guid=peter.guid, title="x" * (MAX_TITLE_LENGTH + 1))
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 400)

        data['title'] = "Sensible"
        data['date'] = 'xxx'
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 400)

        data.pop('date')
        #data['start'] = mktime((2011, 1, 29,0,0,0,0,0,0))
        #response = self.post('/api/events.json', data)
        #self.assertEqual(response.code, 400)

        data['start'] = mktime((2011, 1, 29,0,0,0,0,0,0))
        data['end'] = data['start']
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 400)

    def test_posting_not_all_day_without_date(self):
        peter = self.get_db().users.User()
        assert peter.guid
        peter.save()

        data = dict(guid=peter.guid, title="done", all_day='false')
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 201)

        struct = json.loads(response.body)

        self.assertTrue(not struct['event']['allDay'])
        start = datetime.datetime.fromtimestamp(struct['event']['start'])
        end = datetime.datetime.fromtimestamp(struct['event']['end'])
        self.assertEqual((end - start).seconds, 60*60)
        self.assertTrue(not (start.hour==0 and start.minute==0 and start.second==0))

    def test_getting_version(self):
        from apps.main.config import API_VERSION
        url = '/api/version/'
        response = self.get(url)
        self.assertEqual(response.code, 200)
        self.assertTrue(API_VERSION in response.body)

        url = '/api/version.json'
        response = self.get(url)
        self.assertEqual(response.code, 200)
        struct = json.loads(response.body)
        self.assertEqual(struct['version'], API_VERSION)

        url = '/api/version.xml'
        response = self.get(url)
        self.assertEqual(response.code, 200)
        self.assertTrue('<version>%s</version>' % API_VERSION in response.body)

    def test_failing_to_add_event_with_wrong_dates(self):
        peter = self.get_db().users.User()
        assert peter.guid
        peter.save()

        def dt(x):
            return mktime(x.timetuple())

        data = dict(guid=peter.guid, title="x", all_day=True,
                    start=dt(datetime.date.today()),
                    end=dt(datetime.date.today() - datetime.timedelta(days=1)))
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 400)

        data = dict(guid=peter.guid, title="x", all_day=False,
                    start=dt(datetime.datetime.today()),
                    end=dt(datetime.datetime.now() - datetime.timedelta(seconds=1)))
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 400)

        # there's a lower limit how short the the not-all_day events can be
        from apps.main.config import MINIMUM_DAY_SECONDS
        data = dict(guid=peter.guid, title="x", all_day=False,
                    start=dt(datetime.datetime.today()),
                    end=dt(datetime.datetime.now() + \
                      datetime.timedelta(seconds=MINIMUM_DAY_SECONDS -1)))
        response = self.post('/api/events.json', data)
        self.assertEqual(response.code, 400)

    def test_automatic_end_for_not_all_day_events(self):
        # since there's a minimum for the non-all_day events, it makes
        # it possible to automatically set this
        peter = self.get_db().users.User()
        assert peter.guid
        peter.save()

        def dt(x):
            return mktime(x.timetuple())

        data = dict(guid=peter.guid, title="Xxx", all_day=False,
                    start=dt(datetime.date.today()))
        response = self.post('/api/events/', data)
        self.assertEqual(response.code, 201)
        struct = json.loads(response.body)
        start = struct['event']['start']
        end = struct['event']['end']

        self.assertEqual(int(end-start), MINIMUM_DAY_SECONDS)

        # the same works if you don't use 'start' but 'date'
        data = dict(guid=peter.guid, title="Yyy", all_day=False,
                    date=dt(datetime.date.today()))
        response = self.post('/api/events/', data)
        self.assertEqual(response.code, 201)
        struct = json.loads(response.body)
        start = struct['event']['start']
        end = struct['event']['end']
        self.assertEqual(int(end-start), MINIMUM_DAY_SECONDS)

    def test_error_on_hourly_event_longer_than_24_hours(self):
        peter = self.get_db().users.User()
        assert peter.guid
        peter.save()

        def dt(x):
            return mktime(x.timetuple())

        data = dict(guid=peter.guid,
                    title="Spanning multiple days",
                    all_day=False,
                    start=dt(datetime.datetime.today()),
                    end=dt(datetime.datetime.today() + datetime.timedelta(days=1))
                    )
        response = self.post('/api/events/', data)
        self.assertEqual(response.code, 400)
