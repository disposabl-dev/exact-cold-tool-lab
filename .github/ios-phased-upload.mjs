// The official uploader fully inspects the closed IPA and constructs both requests.
import { existsSync } from 'node:fs';
const {uploadIpa}=await import(process.env.APPDROP_LIB);
const gate=process.env.DELIVERY_GATE;
const started=Date.now();
let putCount=0,postCount=0;
const result=await uploadIpa(process.argv[2],{save:false, fetchImpl:async (url,init)=>{
  const method=init.method;
  if(method==='PUT'){
    while(!existsSync(gate+'/verified')) await Bun.sleep(20);
    putCount++;
  } else if(method==='POST') postCount++;
  else throw Error('Unexpected AppDrop upload operation');
  const at=Date.now();
  const response=await fetch(url,init);
  console.log('APPDROP_PHASE',method,at,Date.now()-at,response.status);
  return response;
}});
if(!/^https:\/\/appdrop\.app\/d\/[a-z0-9]+$/i.test(result.url)||putCount!==1||postCount!==1) throw Error('unexpected iPhone drop result');
const check=await fetch(result.url);
if(!check.ok)throw Error('Public iPhone transfer page unavailable');
console.log('IOS_APPDROP_LINK',result.url,result.size,'ms from closed archive',Date.now()-started);
