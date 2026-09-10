const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync(__dirname+'/../web/aipm_ui.js','utf8');
new vm.Script(src.replace(/^import .*;$/gm,''));
const body=src.slice(src.indexOf('  const queueCurrentOutputs = async'),src.indexOf('  run = async'));
async function check(id,revise){
 let captured;
 const widget={name:'修改意见',value:'user notes'};
 const node={id:7,type:'AIPMVideoPrompt',widgets:[widget],outputs:[],constructor:{}};
 const graph={};node.graph=graph;
 const prompt={output:{[id]:{class_type:node.type,inputs:{修改意见:'user notes'}}},workflow:{widgets_values:['user notes']}};
 const box={node,app:{graph,graphToPrompt:async()=>prompt,api:{queuePrompt:async(_,p)=>{captured=p;assert.equal(widget.value,'user notes');return {prompt_id:'test'}}}},requestState:{pendingQueueEvents:[]},Set,Object,String,Error};
 node.properties={};vm.createContext(box);vm.runInContext(body+'\nthis.queue=queueCurrentOutputs;',box);
 const payload=revise?'__AIPM_RUN_V2__{"operation":"revise_segment"}':'';
 await box.queue({'修改意见':payload});
 assert.equal(captured.output[id].inputs['修改意见'],payload);
 assert.equal(captured.workflow.widgets_values[0],'user notes');assert.equal(widget.value,'user notes');
}
(async()=>{await check('7',true);await check('7',false);await check('22:7',true);
 const run=src.slice(src.indexOf('  run = async'),src.indexOf('  button.callback ='));
 assert(!/modification\.value\s*=/.test(run));
 const cache=src.slice(src.indexOf('  async function outputCachedResult'),src.indexOf('  async function clearCachedResult'));
 assert(!/modification\.value\s*=/.test(cache));
 console.log('PASS syntax, payload isolation, subgraph, cache and no visible field writes');
})().catch(e=>{console.error(e);process.exit(1)});
