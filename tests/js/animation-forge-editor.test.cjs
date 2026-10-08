'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'tools/animation_forge_web/app.js'), 'utf8');
const fixture = JSON.parse(fs.readFileSync(path.join(root, 'examples/animation-forge/neutral-reach.forge.json'), 'utf8'));

// Exercise the actual editor event handlers and timeline functions. Only browser
// transport/rendering surfaces are mocked; no server or live browser is needed.
function editor() {
  const nodes = new Map();
  const requests = [];
  function element() {
    const state = {
      value: '', children: [], drawn: null, style: {},
      set id(value) { nodes.set(value, this); },
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      add(option) { this.children.push(option); },
      addEventListener() {}, setAttribute() {},
      classList: { toggle() {} },
      getContext() {
        return {
          fillRect() { state.drawn = null; }, beginPath() {}, moveTo() {},
          lineTo() {}, stroke() {}, drawImage(image) { state.drawn = image; },
        };
      },
    };
    return state;
  }
  function node(id) {
    if (!nodes.has(id)) nodes.set(id, element());
    return nodes.get(id);
  }
  node('target').value = 'right_hand';
  node('facing').value = 'right';
  node('compare').value = 'pose';
  node('speed').value = '1';
  const context = vm.createContext({
    fixture: structuredClone(fixture),
    document: { getElementById: node, createElement: element },
    window: { addEventListener() {} },
    Option: function Option(text, value) { return { text, value }; },
    performance: { now: () => 0 },
    setTimeout: () => 1, clearTimeout() {}, requestAnimationFrame() {},
    fetch(url, options) {
      return new Promise(resolve => requests.push({
        url, body: options ? JSON.parse(options.body) : null,
        respond(data, status=200) { resolve({ ok: status<400, status, json: async () => data }); },
      }));
    },
  });
  const withoutBoot = source.replace(/\bboot\(\);\s*$/, '');
  assert.notEqual(withoutBoot, source, 'The harness must skip only the automatic bootstrap call');
  vm.runInContext(withoutBoot, context, { filename: 'app.js' });
  const run = code => vm.runInContext(code, context);
  // Geometry rendering is separately tested by the Python backend tests.
  run("render = async () => {}; token = 'test-token'; example = clone(fixture); install(fixture, 'Test fixture');");
  return {
    run, node, requests,
    snapshot(code) { return JSON.parse(JSON.stringify(run(code))); },
  };
}

test('an edit made while reopening a revision survives the late load response', async () => {
  const app = editor();
  app.node('saved').value = 'old.forge.json';
  const pending = app.node('open').onclick();
  assert.equal(app.requests[0].url, '/api/load');
  app.node('number-0').value = '18';
  app.node('number-0').onchange();
  const loaded = structuredClone(fixture);
  loaded.name = 'Old saved revision';
  app.requests[0].respond({ project: loaded });
  await pending;

  assert.equal(app.run('project.poses[0].controls.right_hand[0]'), 18);
  assert.equal(app.run('dirty'), true);
  assert.equal(app.run('undo.length'), 1);
  assert.match(app.node('status').textContent, /changed while loading/);
});

test('the latest of two concurrent reopen requests wins even if it resolves first', async () => {
  const app = editor();
  app.node('saved').value = 'first.forge.json';
  const first = app.node('open').onclick();
  app.node('saved').value = 'second.forge.json';
  const second = app.node('open').onclick();
  const firstProject = { ...structuredClone(fixture), name: 'First revision' };
  const secondProject = { ...structuredClone(fixture), name: 'Second revision' };
  app.requests[1].respond({ project: secondProject });
  await second;
  app.requests[0].respond({ project: firstProject });
  await first;

  assert.equal(app.run('project.name'), 'Second revision');
  assert.equal(app.node('save-status').textContent, 'Reopened second.forge.json');
  assert.equal(app.run('dirty'), false);
});

test('integer seeks and reset select fixture keys without mutating authored data', () => {
  const app = editor();
  const before = app.snapshot('project');
  const samples = [
    [0, 'neutral'], [23, 'neutral'], [24, 'lift'], [31, 'lift'],
    [32, 'reach'], [49, 'reach'], [50, 'return'], [59, 'return'],
  ];
  for (const [tick, pose] of [...samples, ...samples.slice().reverse(), ...samples]) {
    app.run(`seek(${tick})`);
    assert.equal(app.run('selectedPose().id'), pose, `tick ${tick}`);
    assert.equal(app.run('tick'), tick);
  }
  app.run('seek(999)');
  assert.equal(app.run('tick'), 59);
  app.run('seek(-10)');
  assert.equal(app.run('tick'), 0);
  app.run('seek(40); playing = true;');
  app.node('reset').onclick();
  assert.equal(app.run('tick'), 0);
  assert.equal(app.run('selectedPose().id'), 'neutral');
  assert.equal(app.run('playing'), false);
  assert.deepEqual(app.snapshot('project'), before);
});

test('original timing follows elapsed ticks across the edited loop boundary', () => {
  const app = editor();
  app.run(`
    project.exposures[0].duration_ticks = 44;
    refreshProject();
    for (const pose of project.poses) {
      frames[pose.id] = { baseline: pose.id + '-before', current: pose.id + '-after' };
      images.set(pose.id + '-before', pose.id + '-before');
      images.set(pose.id + '-after', pose.id + '-after');
    }
    ready = true;
  `);
  app.node('compare').value = 'timing';
  app.node('play').onclick();
  // 84 elapsed ticks => edited 80-tick loop at 4, baseline 60-tick loop at 24.
  app.run('animate(1400)');
  assert.equal(app.run('tick'), 4);
  assert.equal(app.node('after').drawn, 'neutral-after');
  assert.equal(app.node('before').drawn, 'lift-before');

  app.node('reset').onclick();
  assert.equal(app.node('before').drawn, 'neutral-before');
  assert.equal(app.node('after').drawn, 'neutral-after');
  assert.equal(app.run('comparisonTick'), 0);
});

test('walk plays its entry once and retimed entry stays outside the repeating cycle', () => {
  const app = editor();
  app.run(`
    project.loop_start=2; project.baseline.loop_start=2;
    project.exposures.forEach(e=>e.duration_ticks=1);
    project.baseline.exposures.forEach(e=>e.duration_ticks=1);
    refreshProject();ready=true;
  `);
  assert.deepEqual(app.snapshot('[0,1,2,3,4,5,6,7].map(t=>playbackTick(t,project.exposures,"cycle",2))'),[0,1,2,3,2,3,2,3]);
  app.run('seek(3)');app.node('step').onclick();
  assert.equal(app.run('tick'),2);
  app.node('reset').onclick();assert.equal(app.run('tick'),0);
  app.run('project.exposures[0].duration_ticks=5;refreshProject()');
  assert.equal(app.run('playbackTick(8,project.exposures,"cycle",2)'),6);
  assert.equal(app.run('playbackTick(9,project.exposures,"cycle",2)'),7);
  assert.equal(app.run('playbackTick(10,project.exposures,"cycle",2)'),6);
  assert.equal(app.run('playbackTick(8,project.baseline.exposures,"cycle",2)'),2);
});

test('typed project names are included in an immediate save', async () => {
  const app = editor();
  app.node('name').value='Walk hand study';app.node('name').oninput();
  const pending=app.node('save').onclick();
  assert.equal(app.requests[0].body.project.name,'Walk hand study');
  app.requests[0].respond({file:'Walk-hand-study.forge.json',projects:['Walk-hand-study.forge.json']});
  await pending;
  assert.equal(app.run('dirty'),false);
});

test('concurrent stale requests both recover after a local server restart', async () => {
  const app=editor();
  const first=app.run("api('preview',{project})");
  const second=app.run("api('export',{project})");
  app.requests[0].respond({error:'Invalid local editor request'},403);
  app.requests[1].respond({error:'Invalid local editor request'},403);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(app.requests[2].url,'/api/bootstrap');
  assert.equal(app.requests[3].url,'/api/bootstrap');
  app.requests[2].respond({token:'new-token'});
  await new Promise(resolve=>setImmediate(resolve));
  app.requests[3].respond({token:'new-token'});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(app.requests[4].url,'/api/preview');
  assert.equal(app.requests[5].url,'/api/export');
  app.requests[4].respond({complete:'preview'});
  app.requests[5].respond({complete:'export'});
  assert.equal((await first).complete,'preview');
  assert.equal((await second).complete,'export');
});
