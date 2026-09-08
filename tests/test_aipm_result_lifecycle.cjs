const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const src = fs.readFileSync(require('path').join(__dirname, '../web/aipm_ui.js'), 'utf8');
const body = src.slice(src.indexOf('  const acceptResult = (output) => {'), src.indexOf('  // Explicit recovery only:'));
const box = { requestState: {running: true, currentAction: 'generate'}, videoPromptPreview: {},
  node: { properties: {}, setDirtyCanvas() {} }, previousResult: {},
  app: { graph: {change() {}} }, writes: 0, previewWrites: 0,
  writeTextToLinkedPreviews() {box.previewWrites++;},
  cachedAuthoring() {return {generation_status: 'complete'};},
  writeResultToLinkedCineTimelines() {box.writes++; return 1;}, updateRevisionAvailability() {},
  button: {}, reviseButton: {}, cacheButton: {}, clearButton: {}, isRefinement: false, isVideo: true,
  setStatus() {}, result: {text: ['safe scene', '', '{"schema":"cine_timeline","shots":[]}']},
};
vm.createContext(box);
vm.runInContext(body + '\nglobalThis.accept = acceptResult;', box);
box.accept(box.result);
assert.equal(box.writes, 1);
box.node.properties.aipm_previous_result = 'manual change';
box.accept(box.result);
assert.equal(box.writes, 1);
assert.equal(box.node.properties.aipm_previous_result, 'manual change');
box.requestState.running = true;
box.requestState.currentAction = 'cache';
box.accept(box.result);
assert.equal(box.writes, 2);
box.accept(box.result);
assert.equal(box.writes, 2);
console.log('PASS: one import per explicit action; duplicate/idle replay ignored; explicit cache reimport allowed.');
const writer = src.slice(src.indexOf('function writeResultToLinkedCineTimelines('), src.indexOf('function migrateVideoDurationWidget('));
const timeline = {type:'CineTimelinePlan',inputs:[{name:'timeline_json'}],widgets:[{name:'timeline_state',value:'{}'}]};
const foreign = {type:'CineTimelinePlan',inputs:[{name:'timeline_json'}],widgets:[{name:'timeline_state',value:'keep foreign edits'}]};
const ownGraph = {links:{7:{target_id:4,target_slot:0}},getNodeById(){return timeline;},change(){}};
const author = {type:'AIPMVideoPrompt',graph:ownGraph,outputs:[{name:'完整结果 JSON',links:[7]}]};
const importBox = {app:{graph:{links:ownGraph.links,getNodeById(){return foreign;}}}};
vm.createContext(importBox);
vm.runInContext(writer+'\nglobalThis.writeTimeline=writeResultToLinkedCineTimelines;',importBox);
const safe=JSON.stringify({schema:'cine_timeline',shots:[{shot_id:'S1'}]});
assert.equal(importBox.writeTimeline(author,safe),1);
assert.equal(foreign.widgets[0].value,'keep foreign edits');
assert.equal(importBox.writeTimeline(author,JSON.stringify({schema:'cine_keyframe_timeline',shots:[{shot_id:'S1'}]})),0);
console.log('PASS: imports stay in their source workflow and reject incompatible timeline mode.');
const edited={schema:'cine_timeline',total_frames:120,global_prompt:'edited',shots:[{shot_id:'S1',start_frame:0,end_frame:120,local_prompt:'manual',metadata:{render:{status:'generated'}}}],references:[{reference_id:'R1',scope:'global',asset_id:'edited.png',end_frame:120}]};
timeline.widgets[0].value=JSON.stringify(edited);
const appended={schema:'cine_timeline',total_frames:240,global_prompt:'stale',shots:[{...edited.shots[0],local_prompt:'stale'},{shot_id:'S2',start_frame:120,end_frame:240}],references:[{reference_id:'R1',scope:'global',asset_id:'stale.png',end_frame:240}]};
assert.equal(importBox.writeTimeline(author,JSON.stringify(appended),'append'),1);
const merged=JSON.parse(timeline.widgets[0].value);
assert.deepStrictEqual(merged.shots[0],edited.shots[0]);
assert.equal(merged.global_prompt,'edited');
assert.equal(merged.references[0].asset_id,'edited.png');
assert.equal(merged.references[0].end_frame,240);
assert.equal(importBox.writeTimeline(author,JSON.stringify(appended),'append'),0);
const beforeConflict=timeline.widgets[0].value;
appended.shots.push({shot_id:'S3',start_frame:200,end_frame:320});
assert.throws(()=>importBox.writeTimeline(author,JSON.stringify(appended),'append'),/重叠/);
assert.equal(timeline.widgets[0].value,beforeConflict);
console.log('PASS: append preserves edited document and references; replay and overlap cannot overwrite it.');
const scopedSrc=src.slice(src.indexOf('  const scopeEvent = (callback) => {'),src.indexOf('  const executed = scopeEvent('));
const scopedBox={requestState:{running:true,activePromptId:'',pendingQueueEvents:[]}};
vm.createContext(scopedBox);
vm.runInContext(scopedSrc+'\nglobalThis.scope=scopeEvent;',scopedBox);
let accepted=0;
const handler=scopedBox.scope(()=>accepted++);
handler({detail:{prompt_id:'other'}});
handler({detail:{prompt_id:'mine'}});
assert.equal(accepted,0);
scopedBox.requestState.activePromptId='mine';
for(const [fn,event] of scopedBox.requestState.pendingQueueEvents)fn(event);
assert.equal(accepted,1);
handler({detail:{prompt_id:'other'}});
assert.equal(accepted,1);
console.log('PASS: early events buffered; other queue completions/results cannot finish this request.');
// A new panel listener uses the same node-owned request state.
const rebuilt={requestState:scopedBox.requestState};vm.createContext(rebuilt);
vm.runInContext(scopedSrc+';globalThis.scope=scopeEvent',rebuilt);
let resumed=0;rebuilt.scope(()=>resumed++)({detail:{prompt_id:'mine'}});
assert.equal(resumed,1);
console.log('PASS: rebuilt panel retains ownership of the running request.');
