const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(require('path').join(__dirname, '../web/aipm_ui.js'), 'utf8');
const fn = source.slice(source.indexOf('function configureStableNodeLayout('), source.indexOf('function collectReferenceAssetManifest('));
const context = { VERSION:82, AIPM_MIN_WIDTH:480, requestAnimationFrame:()=>{}, syncGeneratePanelWidth:()=>{} };
vm.createContext(context); vm.runInContext(fn, context);
const input = {name:'视频内容与导演要求', element:{style:{}}};
const node = {
  size:[670,1320], widgets:[input, {computeSize:()=>[0,500]}],
  get bodyHeight(){return this.size[1]},
  getLayoutWidgets(){return this.widgets},
  computeSize(){return [670, 80+this.widgets.reduce((s,w)=>s+(w.computeSize?.(670)[1]||72)+4,0)]},
  _arrangeWidgets(bottom){
    const end=bottom+2+this.widgets.reduce((s,w)=>s+w.computeSize(670)[1]+4,0);
    if(end>this.bodyHeight) {this.size[1]=end;this.onResize(this.size)}
  }
};
context.configureStableNodeLayout(node);
node._aipmFitContentInput();
for(const height of [1320,1800,900,1320]) {
  node.size[1]=height;node.onResize(node.size);
  // Measured slot area differs from computeSize's estimate: old feedback trigger.
  for(let i=0;i<1000;i++) node._arrangeWidgets(200);
  assert.equal(node.size[1],height);
  assert(input._aipmAdaptiveHeight>=72);
}
node.widgets.push({computeSize:()=>[0,100]});
for(let i=0;i<1000;i++)node._arrangeWidgets(250);
assert.equal(node.size[1],1320);
console.log('PASS: 5000 layout passes, grow/shrink and changed widget/slot geometry remain stable');
