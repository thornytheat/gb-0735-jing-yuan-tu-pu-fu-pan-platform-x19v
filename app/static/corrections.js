import {countNames, element, failure, labels, options, pairs, q, status, table, text, vector} from './views.js';

const HELD_KEYS = ['failed', 'pending', 'conflict'];

function feedback(message, error = false) {
  const panel = q('#feedback');
  panel.hidden = !message;
  panel.classList.toggle('error', error);
  panel.textContent = message ?? '';
}

async function post(path, payload, signal) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload), signal});
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.message ?? `请求失败 HTTP ${response.status}`);
  return data;
}

const chainText = (history) => history.map((step) => `T${step.attempt} ${labels[step.result]}${step.late ? '＊' : ''}`).join(' → ');

function deltaText(delta) {
  if (!delta) return '—';
  const parts = Object.entries(countNames).filter(([key]) => delta[key])
    .map(([key, name]) => `${name} ${delta[key] > 0 ? '+' : ''}${delta[key]}`);
  return parts.join('　') || '一致';
}

const heldCount = (side) => HELD_KEYS.reduce((sum, key) => sum + side[key], 0);

function chips(items, format) {
  const list = element('div', null, 'chip-list');
  for (const item of items) list.append(element('span', format(item), `chip tone-${item.result ?? 'PASS'}`));
  return list;
}

function subhead(title, meta) {
  const head = element('p', null, 'correction-subhead');
  head.append(document.createTextNode(title));
  if (meta) head.append(element('span', meta, 'panel__meta'));
  return head;
}

function renderCorrection(box, doc, published) {
  const head = element('div', null, 'detail-title');
  head.append(element('strong', `版本 ${doc.correction_id.slice(0, 12)}`, 'mono'),
    status(published ? 'PUBLISHED' : 'PREVIEW'));
  const transitions = element('div');
  table(transitions, doc.transitions, [
    ['晶圆', 'wafer', 'mono'],
    ['坐标', (step) => vector([step.x, step.y]), 'num'],
    ['原裁决', (step) => status(step.before.result)],
    ['新裁决', (step) => status(step.after.result)],
    ['测次链（＊为迟到复测）', (step) => chainText(step.history_after)],
    ['处置', (step) => `${labels[step.release_before]} → ${labels[step.release_after]}`],
  ]);
  const impact = element('div');
  table(impact, doc.wafers, [
    ['晶圆', 'wafer', 'mono'],
    ['可放行', (w) => `${w.before.passed} → ${w.after.passed}`, 'num'],
    ['须扣下', (w) => `${heldCount(w.before)} → ${heldCount(w.after)}`, 'num'],
    ['良率 %', (w) => `${w.before.yield_pct ?? '—'} → ${w.after.yield_pct ?? '—'}`, 'num'],
    ['交接差额（前）', (w) => deltaText(w.delta_before)],
    ['交接差额（后）', (w) => deltaText(w.delta_after)],
  ]);
  const sections = [head,
    pairs([['版本全称', doc.correction_id], ['基批结果', doc.base_result_sha256],
      ['更正规则', doc.correction_version], ['生成 UTC', doc.created_at.replace('T', ' ')]]),
    subhead('变更芯粒', `${doc.transitions.length} 枚`), transitions,
    subhead('放行处置与交接差额'), impact];
  for (const wafer of doc.wafers) {
    sections.push(subhead(`须扣下清单 · ${wafer.wafer}`, `${wafer.held_after.length} 枚`));
    sections.push(wafer.held_after.length
      ? chips(wafer.held_after, (item) => `${vector([item.x, item.y])} ${labels[item.result]}`)
      : element('p', '此片更正后无须扣下芯粒。', 'empty'));
  }
  for (const wafer of doc.wafers) {
    const details = element('details', null, 'correction-details');
    details.append(element('summary', `可放行清单 · ${wafer.wafer} · ${wafer.releasable_after.length} 枚`),
      chips(wafer.releasable_after, (item) => vector([item.x, item.y])));
    sections.push(details);
  }
  if (!published) sections.push(element('p', '预览未发布：原交接单、台账与测次链保持不变。', 'correction-hint'));
  box.replaceChildren(...sections);
}

export function setupCorrections({api, base, run, signal}) {
  const form = q('#correction-form');
  const stagedBox = q('#correction-staged');
  const resultBox = q('#correction-result');
  const previewButton = q('#correction-preview');
  const publishButton = q('#correction-publish');
  const versionsBox = q('#correction-versions');
  const staged = [];
  resultBox.hidden = true;

  options(form.elements.wafer, run.wafers.map((wafer) => [wafer, wafer]));

  const drawStaged = () => {
    previewButton.disabled = publishButton.disabled = staged.length === 0;
    table(stagedBox, staged.map((record, index) => ({...record, index})), [
      ['晶圆', 'wafer', 'mono'],
      ['坐标', (record) => vector([record.x, record.y]), 'num'],
      ['测次', 'attempt', 'num'],
      ['判定', (record) => status(record.result)],
      ['分档', 'bin', 'num'],
      ['备注', 'note'],
      ['', (record) => {
        const remove = element('button', '移除', 'row-link');
        remove.type = 'button';
        remove.addEventListener('click', () => { staged.splice(record.index, 1); drawStaged(); });
        return remove;
      }],
    ], '尚未加入迟到复测。');
  };

  const showDocument = (doc, published) => {
    resultBox.hidden = false;
    renderCorrection(resultBox, doc, published);
  };

  const loadVersions = async () => {
    const versions = await api(`${base}/corrections`);
    text('#correction-meta', versions.length ? `已发布 ${versions.length} 版 · 原交接单不改写` : '迟到复测登记 · 原交接单不改写');
    table(versionsBox, versions, [
      ['版本', (item) => {
        const link = element('button', item.correction_id.slice(0, 12), 'row-link');
        link.type = 'button';
        link.title = item.correction_id;
        link.addEventListener('click', async () => {
          try {
            showDocument(await api(`${base}/corrections/${item.correction_id}`), true);
            feedback('');
          } catch (error) {
            if (!signal.aborted) feedback(error.message, true);
          }
        });
        return link;
      }],
      ['生成 UTC', 'created_at', 'mono'],
      ['迟到记录', 'records', 'num'],
      ['变更芯粒', 'transitions', 'num'],
      ['涉及晶圆', (item) => item.wafers.join('、')],
      ['更正后良率 %', (item) => item.after.yield_pct ?? '—', 'num'],
    ], '本批尚无放行更正。');
  };

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const data = new FormData(form);
    staged.push({wafer: data.get('wafer'), x: Number(data.get('x')), y: Number(data.get('y')),
      attempt: Number(data.get('attempt')), result: data.get('result'), bin: Number(data.get('bin')),
      note: data.get('note').trim()});
    form.reset();
    form.elements.wafer.value = staged.at(-1).wafer;
    drawStaged();
  }, {signal});

  previewButton.addEventListener('click', async () => {
    feedback('正在推算更正影响…');
    try {
      showDocument(await post(`${base}/corrections/preview`, {records: staged}, signal), false);
      feedback('');
    } catch (error) {
      if (!signal.aborted) {
        resultBox.hidden = false;
        failure(resultBox, error);
        feedback(error.message, true);
      }
    }
  }, {signal});

  publishButton.addEventListener('click', async () => {
    feedback('正在发布放行更正…');
    try {
      const result = await post(`${base}/corrections`, {records: staged}, signal);
      showDocument(result.document, true);
      feedback(result.reused ? '同版更正已存在，复用原版本，未生成第二版。'
        : `更正已发布 · ${result.document.correction_id.slice(0, 12)}`);
      await loadVersions();
    } catch (error) {
      if (!signal.aborted) feedback(error.message, true);
    }
  }, {signal});

  drawStaged();
  loadVersions().catch((error) => { if (!signal.aborted) failure(versionsBox, error); });
}
