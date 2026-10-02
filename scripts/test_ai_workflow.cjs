const fs = require('node:fs');
const assert = require('node:assert/strict');
const workflow = JSON.parse(fs.readFileSync('n8n/workflows/the-x-gemini.json', 'utf8'));
const webhook = workflow.nodes.find(n => n.name === 'Django webhook');
assert.equal(webhook.parameters.authentication, 'headerAuth');
assert.equal(workflow.active, false);
const gemini = workflow.nodes.find(n => n.name === 'Gemini');
const expression = gemini.parameters.jsonBody;
const evaluate = new Function('$json', 'return (' + expression.slice(3, -2) + ');');
const input = {body: {message: '"quoted"\nภาษาไทย', history: [], sources: []}};
const body = evaluate(input);
assert.equal(body.contents.length, 1);
assert.equal(JSON.parse(body.contents[0].parts[0].text).question, input.body.message);
assert.equal(body.generationConfig.maxOutputTokens, 1200);
assert.equal(gemini.parameters.options.timeout, 20000);
assert.ok(!expression.includes('api_key'));
const normalize = new Function('$json', workflow.nodes.find(n => n.name === 'Validate answer').parameters.jsCode);
const response = value => ({statusCode: 200, body: {candidates:[{finishReason:'STOP',
 content: {parts:[{text: JSON.stringify(value)}]}}]}});
assert.deepEqual(normalize(response({reply:'Answer',citation_ids:[1]}))[0].json,
  {reply:'Answer',citation_ids:[1]});
assert.equal(normalize({statusCode:429})[0].json.error, 'rate_limited');
assert.equal(normalize({statusCode:403, body:{error:'secret upstream text'}})[0].json.error, 'unavailable');
assert.equal(normalize(response({reply:'Answer',citation_ids:'bad'}))[0].json.error, 'unavailable');
assert.equal(normalize(response({reply:'',citation_ids:[]}))[0].json.error, 'unavailable');
assert.equal(normalize({statusCode:200,body:{candidates:[{finishReason:'SAFETY'}]}})[0].json.error,'unavailable');
assert.equal(normalize({error:'credential failure'})[0].json.error,'unavailable');
console.log('Workflow contract: prompt escaping, schema, limits, auth and error handling passed.');
