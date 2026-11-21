import {mapView} from './grid.js';
import {labels, number, options, q, text, views} from './views.js';

const stage = document.body.dataset.stage;
const state = {run: null, wafer: null, controller: null, working: false};
const view = q('#view');
const sample = q('#sample');
const waferSelect = q('#wafer');
const start = q('#start');
const rerun = q('#rerun');
const exportLink = q('#export');

async function api(path, settings) {
  const response = await fetch(path, settings);
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.message ?? (response.status === 422 ? '参数无效，请检查输入。' : `请求失败 HTTP ${response.status}`));
  return data;
}

function feedback(message, error = false) {
  const panel = q('#feedback');
  panel.hidden = !message;
  panel.classList.toggle('error', error);
  panel.textContent = message ?? '';
}

function controls() {
  sample.disabled = state.working || !sample.options.length;
  start.disabled = sample.disabled;
  rerun.disabled = state.working || !state.run;
  waferSelect.disabled = state.working || !state.run;
}

function labelsFor(run, wafer, totals) {
  text('#lot', run.lot);
  text('#rail-run', run.run_id.slice(0, 12));
  text('#version', run.rule_version);
  text('#created', `${run.created_at.slice(0, 19).replace('T', ' ')} UTC`);
  q('#created').dateTime = run.created_at;
  const badge = q('#batch-status');
  badge.textContent = labels[run.status];
  badge.className = `status ${run.status === 'MATCH' ? 'pass' : 'pending'}`;
  text('#scope-text', `${wafer} · 南缺口 · X→ / Y↑`);
  for (const key of ['valid','passed','failed','pending','conflict','yield_pct']) {
    text(`#kpi-${key}`, key === 'yield_pct' ? (totals[key] == null ? '—' : `${totals[key]}%`) : number(totals[key]));
  }
}

function runAddress(params, run, wafer) {
  params.set('run', run.run_id);
  params.set('wafer', wafer);
  window.history.replaceState(null, '', `${location.pathname}?${params}`);
  for (const link of document.querySelectorAll('[data-nav]')) {
    const url = new URL(link.href);
    url.search = new URLSearchParams({run: run.run_id, wafer});
    link.href = url;
  }
}

async function display(run, selected, manifests, params = new URLSearchParams()) {
  state.controller?.abort();
  const controller = new AbortController();
  state.controller = controller;
  const request = (path) => api(path, {signal: controller.signal});
  const base = `/api/runs/${run.run_id}`;
  const wafer = run.wafers.includes(selected) ? selected : run.wafers[0];
  view.setAttribute('aria-busy', 'true');
  view.hidden = true;
  text('#connection', '正在载入');
  const audit = await request(`${base}/yield`);
  const context = {api: request, base, wafer, run, signal: controller.signal, audit, manifests, params};
  await (stage === 'mask' ? mapView(context) : views[stage](context));
  state.run = run;
  state.wafer = wafer;
  options(waferSelect, run.wafers.map((id) => [id, id]), wafer);
  labelsFor(run, wafer, ['yield','runs','intake','coordinates'].includes(stage) ? audit.summary : audit.wafers.find((row) => row.wafer === wafer));
  runAddress(params, run, wafer);
  exportLink.href = `${base}/export`;
  exportLink.hidden = false;
  view.setAttribute('aria-busy', 'false');
  view.hidden = false;
  text('#connection', `${run.run_id.slice(0, 12)} · 已归档`);
  q('.status-light').classList.add('ready');
}

async function perform(action) {
  state.working = true;
  controls();
  try {
    await action();
  } catch (error) {
    feedback(error.message, true);
    if (view.getAttribute('aria-busy') === 'true') {
      view.setAttribute('aria-busy', 'false');
      text('#connection', '载入失败');
      q('.status-light').classList.remove('ready');
    }
  } finally {
    state.working = false;
    controls();
  }
}

start.addEventListener('click', () => perform(async () => {
  feedback('正在计算图批…');
  const result = await api('/api/runs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({sample: sample.value})});
  await display(result.manifest, state.wafer, await api('/api/runs'));
  feedback(result.reused ? '相同输入已归档，复用原运行。' : '新图批已归档。');
}));

rerun.addEventListener('click', () => perform(async () => {
  feedback('正在按原始图档复算…');
  const result = await api(`/api/runs/${state.run.run_id}/rerun`, {method: 'POST'});
  feedback(`复算一致 · ${result.manifest.result_sha256.slice(0, 12)}`);
}));

waferSelect.addEventListener('change', () => perform(async () => {
  feedback('');
  await display(state.run, waferSelect.value, await api('/api/runs'));
}));

perform(async () => {
  const params = new URLSearchParams(location.search);
  const [manifests, samples] = await Promise.all([api('/api/runs'), api('/api/samples')]);
  const run = params.has('run') ? manifests.find((item) => item.run_id === params.get('run')) : manifests[0];
  options(sample, samples.map((item) => [item.id, item.label]), run?.sample ?? 'mixed');
  if (run) await display(run, params.get('wafer'), manifests, params);
  else {
    view.setAttribute('aria-busy', 'false');
    text('#connection', '未选定运行');
    feedback(params.has('run') ? '图批未找到，请运行样例。' : '选择样例后运行。', params.has('run'));
  }
});
