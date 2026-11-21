import {element, failure, labels, number, pairs, q, renderCell, text, vector} from './views.js';

const order = ['PASS','FAIL','PENDING','CONFLICT','EDGE_EXCLUSION','NOTCH_VOID','OUTSIDE_DISC'];
const signed = (n) => n > 0 ? `+${n}` : String(n);

function columnName(index) {
  let name = '';
  for (let value = index + 1; value > 0; value = Math.floor((value - 1) / 26)) {
    name = String.fromCharCode(65 + (value - 1) % 26) + name;
  }
  return name;
}

export async function mapView({api, base, wafer, params, signal}) {
  const data = await api(`${base}/mask/${wafer}`);
  const {radius, edge, notch_depth: depth} = data.geometry;
  const size = radius * 2 + 1;
  text('#map-size', `${wafer} · ${size} × ${size}`);
  text('#geometry-rules', `R${radius} · 边缘 ${edge} 格 · 缺口深 ${depth} 格`);
  q('#mask-counts').replaceChildren(pairs(['ACTIVE', 'EDGE_EXCLUSION', 'NOTCH_VOID', 'OUTSIDE_DISC']
    .map((code) => [labels[code], `${number(data.counts[code] ?? 0)} 格`])));

  const grid = element('table', null, 'wafer-grid');
  grid.setAttribute('aria-label', `${wafer} 标准晶圆阵列`);
  const header = grid.createTHead().insertRow();
  const corner = element('th', 'Y / X', 'ruler-y');
  header.append(corner);
  for (let index = 0; index < size; index++) {
    const x = index - radius;
    const mark = element('th', null, x === 0 ? 'axis-zero' : '');
    mark.scope = 'col';
    mark.append(element('span', columnName(index)), element('span', signed(x)));
    header.append(mark);
  }

  const buttons = new Map();
  const counts = {};
  const body = grid.createTBody();
  let row;
  for (const cell of data.cells) {
    if (cell.x === -radius) {
      row = body.insertRow();
      const ruler = element('th', signed(cell.y), `ruler-y${cell.y === 0 ? ' axis-zero' : ''}`);
      ruler.scope = 'row';
      row.append(ruler);
    }
    const code = cell.result ?? cell.eligibility;
    counts[code] = (counts[code] ?? 0) + 1;
    const mark = element('button', code === 'CONFLICT' ? '×' : '', `die tone-${code}`);
    mark.type = 'button';
    mark.tabIndex = -1;
    mark.dataset.x = cell.x;
    mark.dataset.y = cell.y;
    mark.dataset.code = code;
    mark.dataset.cluster = cell.cluster ?? '';
    mark.title = `${vector([cell.x, cell.y])} ${labels[code]}${cell.cluster ? ` · ${cell.cluster}` : ''}`;
    mark.setAttribute('aria-label', mark.title);
    mark.setAttribute('aria-pressed', 'false');
    buttons.set(`${cell.x},${cell.y}`, mark);
    row.insertCell().append(mark);
  }
  q('#map-grid').replaceChildren(grid);

  const target = q('#cell-detail');
  let current = null;
  let request = 0;
  const activate = async (button) => {
    if (current) {
      current.setAttribute('aria-pressed', 'false');
      current.tabIndex = -1;
    }
    current = button;
    button.setAttribute('aria-pressed', 'true');
    button.tabIndex = 0;
    const {x, y} = button.dataset;
    text('#grid-selected', vector([x,y]));
    const index = ++request;
    target.replaceChildren(element('p', '正在读取芯粒…', 'empty'));
    try {
      const detail = await api(`${base}/mask/${wafer}/cell?x=${x}&y=${y}`);
      if (index === request && !signal.aborted) renderCell(target, detail);
    } catch (error) {
      if (index === request && !signal.aborted) failure(target, error);
    }
  };
  grid.addEventListener('click', (event) => {
    const button = event.target.closest('.die');
    if (button) activate(button);
  }, {signal});
  const directions = {ArrowLeft: [-1,0], ArrowRight: [1,0], ArrowUp: [0,1], ArrowDown: [0,-1]};
  grid.addEventListener('keydown', (event) => {
    const step = directions[event.key];
    if (!step || !event.target.matches('.die')) return;
    event.preventDefault();
    const {x,y} = event.target.dataset;
    const next = buttons.get(`${Number(x) + step[0]},${Number(y) + step[1]}`);
    if (next) { next.focus(); activate(next); }
  }, {signal});

  const legend = q('#legend');
  const cluster = params.get('cluster');
  const group = cluster && [...buttons.values()].some((button) => button.dataset.cluster === cluster) ? cluster : null;
  const filters = [['all', '全部'], ...order.map((key) => [key, `${labels[key]} ${number(counts[key] ?? 0)}`])];
  if (group) filters.splice(1, 0, ['cluster', `簇 ${group}`]);
  function highlight(filter) {
    for (const button of legend.querySelectorAll('button')) button.setAttribute('aria-pressed', String(button.value === filter));
    for (const mark of buttons.values()) {
      const match = filter === 'cluster' ? mark.dataset.cluster === group : mark.dataset.code === filter;
      mark.classList.toggle('dimmed', filter !== 'all' && !match);
    }
  }
  legend.replaceChildren(...filters.map(([key, label]) => {
    const action = element('button', null);
    action.type = 'button';
    action.value = key;
    if (order.includes(key)) action.append(element('i', null, `swatch tone-${key}`));
    action.append(label);
    action.addEventListener('click', () => highlight(key), {signal});
    return action;
  }));
  highlight(group ? 'cluster' : 'all');
  const zoom = q('#zoom');
  const changeSize = () => grid.style.setProperty('--die', `${zoom.value}px`);
  zoom.addEventListener('change', changeSize, {signal});
  changeSize();
  activate(buttons.get(`${params.get('x')},${params.get('y')}`) ?? buttons.get('0,0'));
}
