// A dedicated Chrome profile and private CDP pipe; no open debugging port.
import fs from 'node:fs';
import path from 'node:path';
import cp from 'node:child_process';
import {setTimeout as delay} from 'node:timers/promises';

process.umask(0o077);
const candidate=path.resolve(process.argv[2]);
const profile=fs.mkdtempSync(path.join(path.dirname(candidate),'chrome-login-'));
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const child=cp.spawn(chrome,[`--user-data-dir=${profile}`,'--remote-debugging-pipe','--no-first-run','--no-default-browser-check','--app=https://yuanbao.tencent.com/'],{stdio:['ignore','ignore','ignore','pipe','pipe']});
const pending=new Map();let sequence=0,buffer=Buffer.alloc(0),exited=false,stopping=false;
process.on('SIGTERM',()=>{stopping=true;});
child.stdio[3].on('error',()=>{stopping=true;});
child.on('exit',()=>{exited=true;for(const item of pending.values()){clearTimeout(item.timer);item.reject(Error('Login window closed'));}pending.clear();});
child.on('error',()=>{exited=true;});
child.stdio[4].on('data',chunk=>{
 buffer=Buffer.concat([buffer,chunk]);let end;
 while((end=buffer.indexOf(0))>=0){const raw=buffer.subarray(0,end);buffer=buffer.subarray(end+1);try{const response=JSON.parse(raw);const item=pending.get(response.id);if(item){pending.delete(response.id);clearTimeout(item.timer);response.error?item.reject(Error('Browser command failed')):item.resolve(response.result);}}catch{}}
});
function command(method,params={}){return new Promise((resolve,reject)=>{const id=++sequence;const timer=setTimeout(()=>{pending.delete(id);reject(Error('Browser response timed out'));},5000);pending.set(id,{resolve,reject,timer});child.stdio[3].write(JSON.stringify({id,method,params})+'\0');});}
try{
 const deadline=Date.now()+540000;
 while(!exited&&!stopping&&Date.now()<deadline){
  await delay(1500);
  const result=await command('Storage.getCookies');
  const targets=await command('Target.getTargets');
  if(!targets.targetInfos.some(t=>t.type==='page'))break;
  const cookies=result.cookies.filter(c=>['yuanbao.tencent.com','.yuanbao.tencent.com','.tencent.com'].includes(c.domain)&&(!c.expires||c.expires<0||c.expires>Date.now()/1000));
  if(cookies.some(c=>c.name==='hy_user'&&c.value)&&cookies.some(c=>c.name==='hy_token'&&c.value)){
   fs.writeFileSync(candidate,cookies.map(c=>c.name+'='+c.value).join('; '),{mode:0o600,flag:'wx'});
   break;
  }
 }
}catch{
 process.exitCode=1;
}finally{
 if(!exited){try{await command('Browser.close');}catch{} }
 if(!exited)await Promise.race([new Promise(resolve=>child.once('exit',resolve)),delay(3000)]);
 if(!exited)child.kill('SIGTERM');
 await delay(300);
 fs.rmSync(profile,{recursive:true,force:true,maxRetries:3,retryDelay:300});
}
