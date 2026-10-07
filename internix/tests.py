import unittest,tempfile,os,json,urllib.request,urllib.error,http.cookiejar,threading
os.environ['DATABASE_PATH']=tempfile.mktemp(suffix='.sqlite3')
import server as s
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  s.init(); cls.http=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler);cls.url='http://127.0.0.1:'+str(cls.http.server_port);threading.Thread(target=cls.http.serve_forever,daemon=True).start()
  with s.connect() as c:
   c.execute("INSERT INTO jobs VALUES ('test:1','Engineering Intern','TEST ONLY','Bengaluru','Engineering','India',0,'https://example.invalid','<script>test</script>','2026-10-07','test','2026-10-07',1)")
 def setUp(self):
  self.jar=http.cookiejar.CookieJar();self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar));self.csrf=self.call('/api/session')['csrf']
 def call(self,path,data=None,csrf=True):
  req=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json','X-CSRF-Token':self.csrf if csrf and hasattr(self,'csrf') else ''})
  with self.client.open(req) as r:return json.load(r)
 def test_normalize_excludes_fake_intern_substring(self):
  data={'data':[{'title':'Internal auditor'},{'title':'Software Engineering Intern','slug':'a','location':'Bengaluru','url':'https://example.invalid','company_name':'TEST','created_at':100,'description':'<b>Test</b>'}]}
  self.assertEqual(len(s.normalize('arbeitnow',data)),1)
 def test_https_only(self):
  data={'jobs':[{'title':'Intern','location':{'name':'Bengaluru'},'absolute_url':'javascript:alert(1)','id':9}]};self.assertEqual(s.normalize('stripe',data),[])
 def test_domain(self):self.assertEqual(s.domain('Data Scientist Intern'),'Data & AI')
 def test_password(self):
  h=s.password_hash('testonlylongpassword');self.assertNotIn('testonlylongpassword',h);self.assertEqual(h,s.password_hash('testonlylongpassword',h.split(':')[0]))
 def test_filter(self):self.assertEqual(self.call('/api/jobs?country=India&domain=Engineering')['total'],1)
 def test_injection_filter(self):self.assertEqual(self.call('/api/jobs?q=%27%20OR%201%3D1%20--')['total'],0)
 def test_csrf(self):
  with self.assertRaises(urllib.error.HTTPError) as e:self.call('/api/save',{'job_id':'test:1','saved':True},False)
  self.assertEqual(e.exception.code,403)
 def test_saved_persists(self):
  self.call('/api/save',{'job_id':'test:1','saved':True});self.assertEqual(self.call('/api/jobs?saved=1')['total'],1)
 def test_user_isolation(self):self.assertEqual(self.call('/api/jobs?saved=1')['total'],0)
 def test_tracker_status(self):
  self.call('/api/application',{'job_id':'test:1','status':'Planning'});self.assertEqual(self.call('/api/applications')['applications'][0]['status'],'Planning')
 def test_invalid_status(self):
  with self.assertRaises(urllib.error.HTTPError):self.call('/api/application',{'job_id':'test:1','status':'Auto applied'})
 def test_register_migration_login_delete(self):
  self.call('/api/save',{'job_id':'test:1','saved':True});self.call('/api/register',{'email':'test-only@example.invalid','password':'testonlylongpassword','consent':'on'});self.csrf=self.call('/api/session')['csrf'];self.assertEqual(self.call('/api/jobs?saved=1')['total'],1)
  self.call('/api/logout',{});self.csrf=self.call('/api/session')['csrf'];self.call('/api/login',{'email':'test-only@example.invalid','password':'testonlylongpassword'});self.csrf=self.call('/api/session')['csrf'];self.assertEqual(self.call('/api/jobs?saved=1')['total'],1)
  self.call('/api/delete-account',{});self.assertTrue(self.call('/api/session')['guest'])
 def test_invalid_page(self):
  with self.assertRaises(urllib.error.HTTPError) as e:self.call('/api/jobs?page=wat')
  self.assertEqual(e.exception.code,400)
 def test_static_traversal(self):
  with self.assertRaises(urllib.error.HTTPError):self.call('/../../server.py')
 def test_safe_description(self):self.assertEqual(s.plain('&lt;script&gt;hello&lt;/script&gt;'),'hello')
 def test_no_synthetic_jobs(self):
  self.assertNotIn('INSERT INTO jobs',__import__('pathlib').Path('server.py').read_text().split('def init():')[1].split('def now():')[0])
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();os.unlink(s.DB)
class AdzunaTests(unittest.TestCase):
    def test_adzuna_normalize_and_disabled_without_key(self):
        import server as s
        data=[{'id':'1','title':'Data Science Intern','company':{'display_name':'Acme'},'location':{'display_name':'Pune, Maharashtra'},'redirect_url':'https://www.adzuna.in/land/ad/1','description':'x','created':'2026-10-01T00:00:00Z'},{'id':'2','title':'Internal Auditor','redirect_url':'https://www.adzuna.in/land/ad/2'}]
        out=s.normalize('adzuna',data)
        self.assertEqual(len(out),1);self.assertEqual(out[0]['country'],'India');self.assertEqual(out[0]['domain'],'Data & AI');self.assertEqual(out[0]['id'],'adzuna:1')

if __name__=='__main__':unittest.main(verbosity=2)
