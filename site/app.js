'use strict';
const $ = id => document.getElementById(id);
let articles = [], topic = 'All';
const dateFormat = new Intl.DateTimeFormat('en-US', {month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'});
const dateText = value => dateFormat.format(new Date(value));
const element = (tag, className, text) => { const n = document.createElement(tag); if(className) n.className=className; if(text !== undefined) n.textContent=text; return n; };
const link = (text,url) => { const a = element('a',null,text); const parsed = new URL(url); if(parsed.protocol !== 'https:') throw new Error('Invalid source link'); a.href=parsed.href; a.target='_blank'; a.rel='noopener noreferrer'; return a; };
$('today').textContent=new Intl.DateTimeFormat('en-US',{month:'long',day:'numeric',year:'numeric'}).format(new Date()).toUpperCase();
function render() {
  const query=$('search').value.toLocaleLowerCase().trim(), source=$('source-filter').value;
  // Expire old stories even if scheduled collection has stopped.
  const now=Date.now(), cutoff=now-7*86400000;
  const visible=articles.filter(a=>Date.parse(a.publishedAt)>=cutoff && Date.parse(a.publishedAt)<=now && (topic==='All'||a.topic===topic) && (source==='All'||a.source===source) && `${a.title} ${a.source}`.toLocaleLowerCase().includes(query));
  const fragment=document.createDocumentFragment();
  visible.forEach((a,i)=>{
    const row=element('article','story');
    const number=element('span','story-number',String(i+1).padStart(2,'0')); number.setAttribute('aria-hidden','true'); row.append(number);
    const body=element('div'); body.append(element('p','story-topic',a.topic));
    const heading=element('h3'); heading.append(link(a.title,a.url)); body.append(heading);
    const meta=element('div','story-meta'); meta.append(link(a.source,a.sourceUrl),element('span',null,'·'));
    const time=element('time',null,dateText(a.publishedAt)); time.dateTime=a.publishedAt; meta.append(time); body.append(meta); row.append(body);
    const action=element('div','story-action'); action.append(element('span','kind',a.kind)); const read=link('Read at source ↗',a.url); read.setAttribute('aria-label',`Read at ${a.source}: ${a.title} (opens in a new tab)`); action.append(read); row.append(action); fragment.append(row);
  });
  $('stories').replaceChildren(fragment); $('stories').setAttribute('aria-busy','false');
  $('result-count').textContent=`${visible.length} ${visible.length===1?'headline':'headlines'} · latest first`;
  $('empty').hidden=visible.length!==0;
}
document.querySelectorAll('[data-topic]').forEach(button=>button.addEventListener('click',()=>{
  topic=button.dataset.topic; document.querySelectorAll('[data-topic]').forEach(b=>{const selected=b===button;b.classList.toggle('active',selected);b.setAttribute('aria-pressed',String(selected));}); render();
}));
$('search').addEventListener('input',render); $('source-filter').addEventListener('change',render);
function showSources(sources) {
  const groups=new Map(); sources.forEach(s=>{if(!groups.has(s.name))groups.set(s.name,[]);groups.get(s.name).push(s);});
  const fragment=document.createDocumentFragment();
  groups.forEach((feeds,name)=>{
    const card=element('article','source-card'), heading=element('h3'); heading.append(link(name,feeds[0].home)); card.append(heading);
    card.append(element('p',null,`${feeds[0].kind} · ${[...new Set(feeds.map(s=>s.topic))].join(', ')}`));
    const failures=feeds.filter(s=>s.status!=='ok').length; card.append(element('p',null,failures?`${failures} of ${feeds.length} feeds unavailable at last attempt`:`${feeds.length} ${feeds.length===1?'feed':'feeds'} collected successfully`));
    const details=element('details'); details.append(element('summary',null,'Feed status & links'));
    feeds.forEach(s=>{const row=element('div','feed-status');row.append(link(`${s.topic} RSS`,s.feed),element('span',null,s.status==='ok'?'Available':'Unavailable'));if(s.lastSuccessAt)row.append(element('div',null,`Last success: ${dateText(s.lastSuccessAt)}`));details.append(row);}); card.append(details); fragment.append(card);
  }); $('source-list').replaceChildren(fragment);
}
async function load() {
  try {
    const response=await fetch('./data/news.json',{cache:'no-store'}); if(!response.ok)throw new Error('Collection unavailable');
    const data=await response.json(); if(data.schemaVersion!==1||!Array.isArray(data.articles)||!Array.isArray(data.sources))throw new Error('Invalid collection');
    articles=data.articles; const names=[...new Set(articles.map(a=>a.source))].sort();
    names.forEach(name=>{const option=element('option',null,name);option.value=name;$('source-filter').append(option);});
    $('updated').textContent=data.collectedAt?`Collected ${dateText(data.collectedAt)}`:'Awaiting the first collection';
    const failed=data.sources.filter(s=>s.status!=='ok').length;
    const stale=!data.collectedAt||Date.now()-Date.parse(data.collectedAt)>36*3600000;
    if(stale||failed){$('freshness').hidden=false;$('freshness').textContent=[stale?'The briefing has not refreshed within the last 36 hours. Check the collection time before relying on its freshness.':'',failed?`${failed} feeds were unavailable at collection. Still-recent headlines from their last successful collection may be shown.`:''].filter(Boolean).join(' ');}
    showSources(data.sources); render();
    if(!articles.length){$('empty').textContent='The first collection has not been published yet. Please check back after the daily workflow completes.';}
  } catch(error) {
    $('stories').setAttribute('aria-busy','false'); $('updated').textContent='Collection could not be loaded'; $('result-count').textContent='Briefing unavailable'; $('empty').hidden=false; $('empty').textContent='We couldn’t load the briefing. Refresh this page to try again, or check the collection workflow on GitHub.';
  }
}
load();
setInterval(()=>{if(articles.length)render();},60000);
