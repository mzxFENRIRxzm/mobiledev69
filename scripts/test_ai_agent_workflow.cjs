const fs = require('node:fs');
const assert = require('node:assert/strict');
const wf = JSON.parse(fs.readFileSync('n8n/workflows/the-x-gemini-agent.json', 'utf8'));
const get = name => wf.nodes.find(n => n.name === name);
assert.equal(wf.active, false);
assert.equal(get('Django webhook').parameters.authentication, 'headerAuth');
assert.equal(get('Django webhook').parameters.path, 'the-x-gemini-agent');
const agent = get('THE_X AI Agent');
assert.equal(agent.parameters.options.maxIterations, 3);
assert.equal(agent.parameters.options.enableStreaming, false);
assert.equal(get('Structured answer').parameters.autoFix, false);
assert.equal(get('Google Gemini Chat Model').parameters.options.maxOutputTokens, 1200);
for (const [name,type] of [['Google Gemini Chat Model','ai_languageModel'],['reviewed_manuals','ai_tool'],['Structured answer','ai_outputParser']]) {
  assert.equal(wf.connections[name][type][0][0].node, agent.name);
}
const prepare = new Function('$json', get('Prepare context').parameters.jsCode);
const prepared = prepare({body:{message:' "quoted"\nภาษาไทย ',username:'private',token:'private',
 history:Array.from({length:8},()=>({message:'x'.repeat(1400),reply:'y'.repeat(2000)})),
 sources:Array.from({length:7},(_,id)=>({id,title:'Manual',excerpt:'z'.repeat(2400)}))}})[0].json;
assert.deepEqual(Object.keys(prepared), ['message','history','sources']);
assert.equal(prepared.history.length, 4);
assert.equal(prepared.history[0].reply.length, 1500);
assert.equal(prepared.sources.length, 3);
assert.equal(prepared.sources[0].excerpt.length, 1800);
assert.throws(()=>prepare({body:{message:''}}));
assert.throws(()=>prepare({body:{message:'x'.repeat(1001)}}));
const proxy = name => {assert.equal(name,'Prepare context'); return {first:()=>({json:prepared})};};
const tool = new Function('$', 'query', get('reviewed_manuals').parameters.jsCode);
assert.equal(JSON.parse(tool(proxy,'different input')).sources.length, 3);
const emptyProxy = () => ({first:()=>({json:{sources:[]}})});
assert.deepEqual(JSON.parse(tool(emptyProxy,'any')).sources, []);
const normalize = new Function('$json', '$', get('Validate answer').parameters.jsCode);
assert.deepEqual(normalize({output:{reply:' Answer ',citation_ids:[1,1,999]}},proxy)[0].json,
 {reply:'Answer',citation_ids:[1]});
assert.equal(normalize({output:'not JSON'},proxy)[0].json.error,'unavailable');
assert.equal(normalize({output:{reply:'',citation_ids:[]}},proxy)[0].json.error,'unavailable');
assert.equal(normalize({error:{httpCode:'429',message:'do not expose'}},proxy)[0].json.error,'rate_limited');
assert.equal(normalize({error:'[429] RESOURCE_EXHAUSTED'},proxy)[0].json.error,'rate_limited');
assert.deepEqual(normalize({error:{message:'credential secret'}},proxy)[0].json,{error:'unavailable'});
assert.deepEqual(normalize({output:{reply:'General answer',citation_ids:[1]}},emptyProxy)[0].json,
 {reply:'General answer',citation_ids:[]});
console.log('Agent contract passed: wiring, privacy, context limits, tool data, citations and error handling.');

const draft = JSON.parse(fs.readFileSync('n8n/workflows/the-x-rag-draft.json','utf8'));
const dn = name => draft.nodes.find(n=>n.name===name);
assert.equal(draft.active,false);
assert.equal(dn('Postgres PGVector Store').parameters.mode,'retrieve');
assert.equal(dn('Postgres PGVector Store').parameters.options.columnNames.values.metadataColumnName,'metadata');
assert.equal(dn('Postgres PGVector Store').credentials,undefined);
assert.equal(dn('Postgres Chat Memory').credentials,undefined);
assert.equal(dn('Postgres Chat Memory').parameters.contextWindowLength,4);
assert.ok(!dn('Postgres Chat Memory').parameters.sessionKey.includes('$execution'));
for (const [from,type,to] of [
 ['Postgres Chat Memory','ai_memory','THE_X AI Agent'],
 ['Answer questions with a vector store','ai_tool','THE_X AI Agent'],
 ['Postgres PGVector Store','ai_vectorStore','Answer questions with a vector store'],
 ['Google Gemini - RAG answer','ai_languageModel','Answer questions with a vector store'],
 ['Embeddings Google Gemini','ai_embedding','Postgres PGVector Store'],
]) assert.equal(draft.connections[from][type][0][0].node,to);
const dp = new Function('$json',dn('Prepare context').parameters.jsCode);
assert.throws(()=>dp({body:{message:'question'}}));
const uuid='bfb8bab3-b6fd-41af-9685-e2a32da40b6e';
assert.equal(dp({body:{message:'question',conversation_id:uuid}})[0].json.session_key,'the_x:'+uuid);
console.log('RAG draft passed: source topology, separate credentials, bounded context and required session contract.');
