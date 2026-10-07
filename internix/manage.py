"""Owner-only CLI. Run on the server shell. No public admin endpoint."""
import argparse,csv,sys,sqlite3
import server
p=argparse.ArgumentParser(description='Internix database management')
p.add_argument('action',choices=['stats','export-users','backup','delete-user','sync']);p.add_argument('--output');p.add_argument('--email');a=p.parse_args();server.init()
with server.connect() as c:
 if a.action=='stats':
  for table in ['users','saved','applications','jobs']:print(table,c.execute('SELECT count(*) FROM '+table).fetchone()[0])
 elif a.action=='export-users':
  if not a.output:sys.exit('Use --output /private/path/users.csv. Keep the export private.')
  with open(a.output,'w',newline='') as f:
   w=csv.writer(f);w.writerow(['email','created_at','saved_count','tracked_count'])
   for row in c.execute('SELECT u.email,u.created,(SELECT count(*) FROM saved WHERE user_id=u.id),(SELECT count(*) FROM applications WHERE user_id=u.id) FROM users u'):w.writerow(row)
  print('Private user export written. No passwords or notes exported.')
 elif a.action=='backup':
  if not a.output:sys.exit('Use --output /private/path/backup.sqlite3')
  dest=sqlite3.connect(a.output);c.backup(dest);dest.close();print('Database backup written. Contains private user data, keep it private.')
 elif a.action=='delete-user':
  if not a.email:sys.exit('Use --email user@example.com')
  u=c.execute('SELECT id FROM users WHERE email=?',(a.email.lower(),)).fetchone()
  if not u:sys.exit('No matching account.')
  for table in ['saved','applications','sessions']:c.execute('DELETE FROM '+table+' WHERE user_id=?',(u['id'],))
  c.execute('DELETE FROM users WHERE id=?',(u['id'],));print('Account and related data deleted.')
 elif a.action=='sync':print(server.sync())
