"""Internix: real internship discovery. Python 3.11+, no runtime dependencies."""
import os, json, re, html, sqlite3, time, hashlib, secrets, threading, urllib.request, urllib.parse, concurrent.futures
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
ROOT=Path(__file__).parent
DB=os.getenv('DATABASE_PATH', str(ROOT/'data'/'internix.sqlite3'))
Path(DB).parent.mkdir(parents=True,exist_ok=True)
LOCK=threading.Lock()
SOURCES={'stripe':('Stripe · Greenhouse','https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true'), 'groww':('Groww · Greenhouse','https://boards-api.greenhouse.io/v1/boards/groww/jobs?content=true'), 'arbeitnow':('Arbeitnow','https://www.arbeitnow.com/api/job-board-api')}
SOURCES.update({b:(name+' · Greenhouse','https://boards-api.greenhouse.io/v1/boards/'+b+'/jobs?content=true') for b,name in [('rubrik','Rubrik'),('inmobi','InMobi'),('towerresearchcapital','Tower Research Capital'),('hackerrank','HackerRank'),('databricks','Databricks'),('coinbase','Coinbase'),('samsara','Samsara')]})
SOURCES.update({b:(name+' · Greenhouse','https://boards-api.greenhouse.io/v1/boards/'+b+'/jobs?content=true') for b,name in [('lyft','Lyft'),('pinterest','Pinterest'),('robinhood','Robinhood'),('figma','Figma'),('datadog','Datadog'),('cloudflare','Cloudflare'),('appian','Appian'),('affirm','Affirm'),('duolingo','Duolingo'),('vercel','Vercel'),('workato','Workato'),('scaleai','Scale AI'),('thoughtworks','Thoughtworks'),('purestorage','Pure Storage'),('appier','Appier'),('c3iot','C3 AI'),('celonis','Celonis'),('epicgames','Epic Games'),('gemini','Gemini'),('imc','IMC Trading'),('sezzle','Sezzle'),('tanium','Tanium'),('waymo','Waymo'),('payoneer','Payoneer'),('nuro','Nuro'),('monzo','Monzo'),('jfrog','JFrog'),('qualtrics','Qualtrics'),('anaplan','Anaplan'),('tripadvisor','Tripadvisor'),('sendbird','Sendbird')]})
SOURCES['adzuna']=('Adzuna','https://api.adzuna.com/v1/api/jobs/')
SOURCES.update({b:(name+' · Lever','https://api.lever.co/v0/postings/'+b+'?mode=json') for b,name in [('palantir','Palantir'),('paytm','Paytm')]})
SOURCES.update({b:(name+' · Ashby','https://api.ashbyhq.com/posting-api/job-board/'+b) for b,name in [('sarvam','Sarvam AI'),('notion','Notion'),('ramp','Ramp'),('cohere','Cohere'),('perplexity','Perplexity'),('sentry','Sentry'),('harvey','Harvey'),('modal','Modal'),('commure','Commure'),('wealthsimple','Wealthsimple')]})
def connect():
 c=sqlite3.connect(DB,timeout=20); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
def init():
 with connect() as c:
  c.executescript('''PRAGMA journal_mode=WAL;
  CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, title TEXT, company TEXT, location TEXT, domain TEXT, country TEXT, remote INTEGER, url TEXT, description TEXT, published TEXT, source TEXT, checked TEXT, active INTEGER DEFAULT 1);
  CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,name TEXT,status TEXT,last_success TEXT,last_attempt TEXT,error TEXT,count INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE,password TEXT,created TEXT);
  CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT,csrf TEXT,expires REAL);
  CREATE TABLE IF NOT EXISTS saved(user_id TEXT,job_id TEXT REFERENCES jobs(id),created TEXT,PRIMARY KEY(user_id,job_id));
  CREATE TABLE IF NOT EXISTS applications(user_id TEXT,job_id TEXT REFERENCES jobs(id),status TEXT,notes TEXT,updated TEXT,PRIMARY KEY(user_id,job_id));
  CREATE INDEX IF NOT EXISTS jobs_filter ON jobs(active,country,domain);
  ''')
def now():return datetime.now(timezone.utc).isoformat()
def plain(s):
 text=re.sub(r'<[^>]+>',' ',html.unescape(html.unescape(s or '')))
 return re.sub(r'\n[ \t]*(?:\n[ \t]*)+', '\n\n',text).strip()
def domain(title):
 t=title.lower()
 for d,p in [('Data & AI',r'data|machine learning|\bai\b|\bml\b|analytics|genai|deep learning|applied scien|research scien|scientist|quantitative research|quant\b|research intern'),('Engineering',r'engineer|software|developer|programmer|robotics|electronics|\bsde\b|\bit support|\bsecurity\b|technolog|tools|backend|frontend'),('Design',r'design|\bux\b|\bui\b'),('Marketing & Content',r'marketing|content|communications|creative|video|youtube|social|editor'),('Finance',r'finance|financial|account|audit|risk|fraud|compliance|\btax\b|trader|investment|macro|credit|controller'),('People & Operations',r'recruit|talent|human resources|\bhr\b|people team|operations|customer|associate')]:
  if re.search(p,t):return d
 return 'Other'
def country(loc):
 t=loc.lower()
 if re.search(r'\bindia\b|bengaluru|bangalore|mumbai|delhi|hyderabad|pune|chennai|gurugram|gurgaon|gift city|noida',t):return 'India'
 return 'International'
def kind(source):
 u=SOURCES[source][1]
 return 'adzuna' if source=='adzuna' else 'arbeitnow' if source=='arbeitnow' else 'lever' if 'lever.co' in u else 'ashby' if 'ashbyhq' in u else 'greenhouse'
def raw_rows(source,data):
 k=kind(source)
 if k=='adzuna':return data
 if k=='arbeitnow':return data['data']
 if k=='lever':return data
 if k=='ashby':return data['jobs']
 return data['jobs']
def fields(source,j):
 k=kind(source)
 if k=='adzuna':return dict(id=j['id'],title=j.get('title',''),loc=(j.get('location') or {}).get('display_name',''),url=j.get('redirect_url',''),desc=j.get('description',''),pub=j.get('created'),remote=False,company=(j.get('company') or {}).get('display_name'))
 if k=='lever':
  c=j.get('categories') or {};locs=c.get('allLocations') or [c.get('location') or '']
  loc=' · '.join(x for x in locs if x) or (c.get('location') or '')
  pub=datetime.fromtimestamp(j['createdAt']/1000,timezone.utc).isoformat() if j.get('createdAt') else None
  return dict(id=j['id'],title=j['text'],loc=loc,url=j.get('hostedUrl',''),desc=j.get('descriptionPlain') or j.get('description',''),pub=pub,remote=(j.get('workplaceType')=='remote'))
 if k=='ashby':
  locs=[j.get('location') or '']+[x.get('location','') for x in j.get('secondaryLocations',[]) if isinstance(x,dict)]
  return dict(id=j['id'],title=j['title'],loc=' · '.join(x for x in locs if x),url=j.get('jobUrl',''),desc=j.get('descriptionPlain') or j.get('descriptionHtml',''),pub=j.get('publishedAt'),remote=bool(j.get('isRemote')))
 if k=='arbeitnow':
  return dict(id=j.get('slug'),title=j['title'],loc=j['location'],url=j.get('url',''),desc=j.get('description',''),pub=datetime.fromtimestamp(j['created_at'],timezone.utc).isoformat(),remote=bool(j.get('remote')),company=j.get('company_name'))
 loc=j['location']['name']
 if j.get('offices'):
  office_locations=[o.get('location','') for o in j['offices'] if o.get('location')]
  if loc.lower() in ['hybrid','in-office','remote'] and office_locations:loc=loc+' · '+', '.join(office_locations)
 return dict(id=j.get('id'),title=j['title'],loc=loc,url=j.get('absolute_url',''),desc=j.get('content',''),pub=j.get('first_published'),remote=False,company=j.get('company_name'))
def normalize(source,data):
 out=[]
 for j in raw_rows(source,data):
  if not re.search(r'\bintern(?:ship)?\b',str(j.get('title') or j.get('text') or ''),re.I):continue
  f=fields(source,j);title=f['title']
  if not f['url'].startswith('https://'):continue
  loc=f['loc'] or ''
  out.append(dict(id=source+':'+str(f['id']),title=title,company=f.get('company') or SOURCES[source][0].split(' · ')[0],location=loc,domain=domain(title),country=country(loc),remote=int(f['remote'] or 'remote' in loc.lower()),url=f['url'],description=plain(f['desc']),published=f['pub'],source=source,checked=now()))
 return out
ADZUNA_QUERIES=[('intern internship',1),('intern internship',2),('intern internship',3),('intern software engineer data',1)]
def adzuna_enabled():return bool(os.getenv('ADZUNA_APP_ID') and os.getenv('ADZUNA_APP_KEY'))
def adzuna_fetch():
 rows=[]
 for what,page in ADZUNA_QUERIES:
  q=urllib.parse.urlencode({'app_id':os.environ['ADZUNA_APP_ID'],'app_key':os.environ['ADZUNA_APP_KEY'],'results_per_page':50,'what_or':what,'sort_by':'date','content-type':'application/json'})
  request=urllib.request.Request('https://api.adzuna.com/v1/api/jobs/'+os.getenv('ADZUNA_COUNTRY','in')+'/search/'+str(page)+'?'+q,headers={'User-Agent':'Internix/1.0','Accept':'application/json'})
  with urllib.request.urlopen(request,timeout=30) as r:rows+=json.load(r).get('results',[])
 return list({j['id']:j for j in rows}.values())
def adzuna_due():
 with connect() as c:
  r=c.execute("SELECT last_attempt FROM sources WHERE id='adzuna'").fetchone()
 if not r or not r['last_attempt']:return True
 return (datetime.now(timezone.utc)-datetime.fromisoformat(r['last_attempt'])).total_seconds()>=int(os.getenv('ADZUNA_REFRESH_SECONDS','21600'))
def fetch_source(source):
 name,url=SOURCES[source]
 try:
  if source=='adzuna':
   if not adzuna_enabled() or not adzuna_due():return {'source':source,'status':'skipped'}
   data=adzuna_fetch()
  else:
   request=urllib.request.Request(url,headers={'User-Agent':'Internix/1.0 internship-discovery','Accept':'application/json'})
   with urllib.request.urlopen(request,timeout=30) as r:data=json.load(r)
  rows=normalize(source,data)
  with connect() as c:
   c.execute('UPDATE jobs SET active=0 WHERE source=?',(source,))
   for j in rows:
    c.execute('INSERT INTO jobs VALUES (:id,:title,:company,:location,:domain,:country,:remote,:url,:description,:published,:source,:checked,1) ON CONFLICT(id) DO UPDATE SET title=excluded.title,company=excluded.company,location=excluded.location,domain=excluded.domain,country=excluded.country,remote=excluded.remote,url=excluded.url,description=excluded.description,published=excluded.published,checked=excluded.checked,active=1',j)
   c.execute('INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?,?)',(source,name,'ok',now(),now(),None,len(rows)))
  return {'source':source,'count':len(rows),'status':'ok'}
 except Exception as e:
  with connect() as c:
   c.execute('INSERT INTO sources(id,name,status,last_attempt,error) VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,last_attempt=excluded.last_attempt,error=excluded.error',(source,name,'error',now(),str(e)[:200]))
  return {'source':source,'status':'error','error':str(e)}
def sync():
 if not LOCK.acquire(False):return {'status':'busy'}
 try:
  with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:result=list(pool.map(fetch_source,SOURCES))
  return {'status':'complete','sources':result}
 finally:LOCK.release()
def scheduler():
 while True:
  sync();time.sleep(3600)
def password_hash(password,salt=None):
 salt=salt or secrets.token_hex(16)
 return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),300000).hex()
RATE={}
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def headers_out(self,status=200,kind='application/json',cookie=None):
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','strict-origin-when-cross-origin');self.send_header('X-Frame-Options','DENY');self.send_header('Cache-Control','no-store')
  self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
  if cookie:self.send_header('Set-Cookie',cookie)
  self.end_headers()
 def send(self,data,status=200,cookie=None):
  self.headers_out(status,cookie=cookie);self.wfile.write(json.dumps(data).encode())
 def session(self):
  from http.cookies import SimpleCookie
  cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''));token=cookie.get('internix');token=token.value if token else ''
  with connect() as c:
   s=c.execute('SELECT * FROM sessions WHERE token=? AND expires>?',(token,time.time())).fetchone()
   if s:return dict(s),None
   s={'token':secrets.token_urlsafe(32),'user_id':'guest:'+secrets.token_hex(16),'csrf':secrets.token_urlsafe(32),'expires':time.time()+86400*30}
   c.execute('INSERT INTO sessions VALUES (:token,:user_id,:csrf,:expires)',s)
  return s,self.cookie(s['token'])
 def cookie(self,token):return 'internix='+token+'; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000'+('; Secure' if os.getenv('COOKIE_SECURE')=='1' else '')
 def do_GET(self):
  path=urllib.parse.urlparse(self.path);q=urllib.parse.parse_qs(path.query)
  if path.path.startswith('/api/'):
   s,cookie=self.session()
   with connect() as c:
    if path.path=='/api/session':
     u=c.execute('SELECT email FROM users WHERE id=?',(s['user_id'],)).fetchone();return self.send({'csrf':s['csrf'],'email':u['email'] if u else None,'guest':not bool(u)},cookie=cookie)
    if path.path=='/api/sources':
     rows=[dict(x) for x in c.execute('SELECT * FROM sources')];return self.send({'sources':rows,'syncing':LOCK.locked(),'coverage':'Selected employer feeds and Arbeitnow. Not all internships on the web.'},cookie=cookie)
    if path.path=='/api/jobs':
     where=['j.active=1'];params=[]
     for key in ['domain','country','location']:
      val=q.get(key,[''])[0]
      if val:
       if key=='location':
        where.append("lower(replace(j.location,'Bangalore','Bengaluru')) LIKE ?");params.append('%'+val.lower().replace('bangalore','bengaluru')+'%')
       else:where.append('j.'+key+'=?');params.append(val)
     if q.get('remote',[''])[0]=='1':where.append('j.remote=1')
     if q.get('q',[''])[0]:
      where.append('(j.title LIKE ? OR j.company LIKE ? OR j.description LIKE ?)');params.extend(['%'+q['q'][0][:200]+'%']*3)
     if q.get('saved',[''])[0]=='1':where.append('sv.job_id IS NOT NULL')
     base=' FROM jobs j LEFT JOIN saved sv ON sv.job_id=j.id AND sv.user_id=? LEFT JOIN applications a ON a.job_id=j.id AND a.user_id=? WHERE '+' AND '.join(where)
     params=[s['user_id'],s['user_id']]+params
     total=c.execute('SELECT COUNT(*)'+base,params).fetchone()[0]
     try:page=max(1,int(q.get('page',['1'])[0]))
     except ValueError:return self.send({'error':'Invalid page'},400)
     rows=[dict(x) for x in c.execute('SELECT j.*,sv.job_id IS NOT NULL AS saved,a.status AS application_status'+base+' ORDER BY j.published DESC,j.title LIMIT 24 OFFSET ?',params+[(page-1)*24])]
     for row in rows:row.pop('description')
     return self.send({'jobs':rows,'total':total,'page':page,'pages':(total+23)//24},cookie=cookie)
    if path.path.startswith('/api/job/'):
     jid=urllib.parse.unquote(path.path[9:]);j=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
     return self.send(dict(j) if j else {'error':'Internship not found'},200 if j else 404,cookie)
    if path.path=='/api/applications':
     rows=[dict(x) for x in c.execute('SELECT j.*,a.status,a.notes,a.updated FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.user_id=? ORDER BY a.updated DESC',(s['user_id'],))]
     return self.send({'applications':rows},cookie=cookie)
    return self.send({'error':'Not found'},404)
  name={'/app.js':'app.js','/styles.css':'styles.css'}.get(path.path,'index.html')
  if path.path not in ['/','/discover','/saved','/tracker','/sources','/account','/app.js','/styles.css'] and not path.path.startswith('/internship/'):
   return self.send({'error':'Not found'},404)
  kind={'js':'text/javascript','css':'text/css','html':'text/html'}[name.split('.')[-1]]
  self.headers_out(kind=kind+'; charset=utf-8');self.wfile.write((ROOT/'public'/name).read_bytes())
 def do_POST(self):
  s,_=self.session()
  if self.headers.get('X-CSRF-Token')!=s['csrf']:return self.send({'error':'Session expired. Reload and try again.'},403)
  try:
   size=int(self.headers.get('Content-Length','0'))
   if size<0:raise ValueError()
   if size>16384:return self.send({'error':'Request too large'},413)
   d=json.loads(self.rfile.read(size))
   if not isinstance(d,dict):raise ValueError()
  except (ValueError,TypeError):return self.send({'error':'Invalid request'},400)
  path=urllib.parse.urlparse(self.path).path
  with connect() as c:
   if path in ['/api/register','/api/login']:
    ip=self.client_address[0];attempts=[t for t in RATE.get(ip,[]) if t>time.time()-600]
    if len(attempts)>=15:return self.send({'error':'Too many attempts. Try again in 10 minutes.'},429)
    RATE[ip]=attempts+[time.time()]
    email=str(d.get('email','')).strip().lower();pw=str(d.get('password',''))
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254 or not 10<=len(pw)<=128:return self.send({'error':'Use a valid email and a password of 10–128 characters.'},400)
    if path=='/api/register':
     if not d.get('consent'):return self.send({'error':'Please accept the visible account data notice.'},400)
     uid=secrets.token_hex(16)
     try:c.execute('INSERT INTO users VALUES (?,?,?,?)',(uid,email,password_hash(pw),now()))
     except sqlite3.IntegrityError:return self.send({'error':'Account cannot be created. Try signing in.'},409)
    else:
     u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
     if not u or not secrets.compare_digest(u['password'],password_hash(pw,u['password'].split(':')[0])):return self.send({'error':'Email or password is incorrect.'},401)
     uid=u['id']
    if s['user_id'].startswith('guest:'):
     c.execute('INSERT OR IGNORE INTO saved SELECT ?,job_id,created FROM saved WHERE user_id=?',(uid,s['user_id']));c.execute('INSERT OR IGNORE INTO applications SELECT ?,job_id,status,notes,updated FROM applications WHERE user_id=?',(uid,s['user_id']))
    c.execute('DELETE FROM sessions WHERE token=?',(s['token'],));token=secrets.token_urlsafe(32)
    c.execute('INSERT INTO sessions VALUES (?,?,?,?)',(token,uid,secrets.token_urlsafe(32),time.time()+86400*30));return self.send({'ok':True},cookie=self.cookie(token))
   if path=='/api/delete-account':
    if s['user_id'].startswith('guest:'):return self.send({'error':'Sign in to delete your account.'},401)
    for table in ['saved','applications','sessions']:c.execute('DELETE FROM '+table+' WHERE user_id=?',(s['user_id'],))
    c.execute('DELETE FROM users WHERE id=?',(s['user_id'],));return self.send({'ok':True},cookie='internix=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')
   if path=='/api/logout':
    c.execute('DELETE FROM sessions WHERE token=?',(s['token'],));return self.send({'ok':True},cookie='internix=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')
   jid=str(d.get('job_id',''))
   if path in ['/api/save','/api/application']:
    if not c.execute('SELECT 1 FROM jobs WHERE id=?',(jid,)).fetchone():return self.send({'error':'Internship not found'},404)
    if path=='/api/save':
     if d.get('saved'):c.execute('INSERT OR IGNORE INTO saved VALUES (?,?,?)',(s['user_id'],jid,now()))
     else:c.execute('DELETE FROM saved WHERE user_id=? AND job_id=?',(s['user_id'],jid))
    else:
     if d.get('status')=='remove':c.execute('DELETE FROM applications WHERE user_id=? AND job_id=?',(s['user_id'],jid))
     elif d.get('status') in ['Planning','Applied','Interview','Offer','Closed']:
      c.execute('INSERT OR REPLACE INTO applications VALUES (?,?,?,?,?)',(s['user_id'],jid,d['status'],str(d.get('notes',''))[:3000],now()))
     else:return self.send({'error':'Invalid application status'},400)
    return self.send({'ok':True})
  return self.send({'error':'Not found'},404)
if __name__=='__main__':
 init();threading.Thread(target=scheduler,daemon=True).start()
 print('Internix listening on http://localhost:'+os.getenv('PORT','8000'),flush=True)
 ThreadingHTTPServer((os.getenv('HOST','127.0.0.1'),int(os.getenv('PORT','8000'))),Handler).serve_forever()
