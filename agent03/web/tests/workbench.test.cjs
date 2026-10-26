const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

// Compile the actual source with the project's TypeScript compiler; no duplicate test implementation.
const cache = new Map();
function loadSource(name) {
  const filename = path.resolve(__dirname, '../src', name);
  if (cache.has(filename)) return cache.get(filename).exports;
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
    fileName: filename,
  }).outputText;
  const mod = new Module(filename, module);
  mod.filename = filename;
  mod.paths = Module._nodeModulePaths(path.dirname(filename));
  const originalRequire = mod.require.bind(mod);
  mod.require = (specifier) => specifier === './presentation' ? loadSource('presentation.ts') : originalRequire(specifier);
  cache.set(filename, mod);
  mod._compile(compiled, filename);
  return mod.exports;
}
const { comparisonStatus, formatApiError, fieldLabels, riskLabels } = loadSource('presentation.ts');
const { ComparisonCard } = loadSource('ComparisonCard.tsx');
const { WorkbenchSidebar, OverviewMetrics, CaseList, CaseSteps } = loadSource('WorkbenchChrome.tsx');
const base = { document_type: 'invoice', document_id: null, original_name: null, fields: {}, candidates: [] };

test('ambiguous comparison lists both candidates and never says missing', () => {
  const column = { ...base, match_status: 'AMBIGUOUS', candidates: [
    { document_id: '1', original_name: '第一张发票.pdf', parse_status: 'COMPLETED' },
    { document_id: '2', original_name: '第二张发票.pdf', parse_status: 'COMPLETED' },
  ] };
  const markup = renderToStaticMarkup(React.createElement(ComparisonCard, { column }));
  assert.match(markup, /多份待匹配/);
  assert.match(markup, /第一张发票.pdf/);
  assert.match(markup, /第二张发票.pdf/);
  assert.doesNotMatch(markup, /未找到对应文档/);
  assert.equal(comparisonStatus(column).color, 'orange');
});
test('missing comparison explains missing materials', () => {
  const markup = renderToStaticMarkup(React.createElement(ComparisonCard, { column: { ...base, match_status: 'MISSING' } }));
  assert.match(markup, /缺失/);
  assert.match(markup, /请补充材料/);
  assert.doesNotMatch(markup, /待匹配候选文件/);
});
test('uploaded but unparsed document is not called missing', () => {
  assert.equal(comparisonStatus({ ...base, match_status: 'UNAVAILABLE' }).label, '抽取未就绪');
});
test('matched comparison uses Chinese labels without uncalibrated percentages', () => {
  const column = { ...base, match_status: 'MATCHED', document_id: '1', original_name: '发票.pdf',
    fields: { total_with_tax: { value: '125000.00', confidence: .85, evidence_id: 'e1' } } };
  const markup = renderToStaticMarkup(React.createElement(ComparisonCard, { column }));
  assert.match(markup, /已关联/);
  assert.match(markup, /价税合计/);
  assert.match(markup, /125000.00/);
  assert.doesNotMatch(markup, /85%/);
});
test('user-controlled file names are escaped', () => {
  const column = { ...base, match_status: 'MATCHED', original_name: '<script>alert(1)</script>' };
  const markup = renderToStaticMarkup(React.createElement(ComparisonCard, { column }));
  assert.doesNotMatch(markup, /<script>/);
  assert.match(markup, /&lt;script&gt;/);
});
test('approval failure is translated with trace preserved', () => {
  const text = formatApiError('all high risks must be resolved or accepted before approval', 'trace-test');
  assert.match(text, /高风险/);
  assert.match(text, /trace-test/);
  assert.doesNotMatch(text, /all high risks/);
});
test('unknown API messages and non-string details have safe fallback', () => {
  assert.equal(formatApiError('custom server error'), 'custom server error');
  assert.match(formatApiError({ detail: 'bad' }), /请求失败/);
});
test('labels cover the five review risks and monetary field', () => {
  assert.equal(Object.keys(riskLabels).length, 5);
  assert.equal(fieldLabels.total_amount, '总金额');
});

test('sidebar retains policies, audit, tenant identity and logout', () => {
  const markup = renderToStaticMarkup(React.createElement(WorkbenchSidebar, {
    tenant: '测试租户', user: '审查员', admin: true, onPolicies() {}, onAudit() {}, onLogout() {},
  }));
  for (const text of ['案件工作台', '制度知识库', '审计记录', '退出登录', '测试租户', '审查员']) assert.ok(markup.includes(text));
});
test('non-admin sidebar does not expose audit entry', () => {
  const markup = renderToStaticMarkup(React.createElement(WorkbenchSidebar, { admin: false }));
  assert.doesNotMatch(markup, /审计记录/);
  assert.match(markup, /制度知识库/);
});
test('overview renders server values, rates, distribution, status and report count', () => {
  const summary = { total_cases: 123, total_documents: 456, job_success_rate: 92.3,
    average_processing_seconds: 7.8, manual_review_rate: 3.4, rule_hit_rate: 5.6,
    risk_by_severity: { HIGH: 9, MEDIUM: 2 }, status_counts: { DRAFT: 3, REVIEW_READY: 4, ARCHIVED: 1 }, ready_reports: 8 };
  const markup = renderToStaticMarkup(React.createElement(OverviewMetrics, { summary }));
  for (const text of ['123', '456', '92.3%', '7.80', '3.4%', '5.6%', '高风险', '草稿', '待审查', '已归档', '已生成报告']) assert.ok(markup.includes(text), text);
  assert.doesNotMatch(markup, /已连接|Qwen-Plus/);
});
const demoCase = { id: 'case-one', title: '设备审查', status: 'REVIEW_READY', version: 3, created_at: '2026-10-26T00:00:00Z', documents: [{ id: 'doc-one' }] };
test('case list marks selected row and retains real pending progress, downloads, failure history', () => {
  const cases = [demoCase, { ...demoCase, id: 'processing', status: 'PROCESSING' }, { ...demoCase, id: 'failed', status: 'FAILED' }];
  const markup = renderToStaticMarkup(React.createElement(CaseList, {
    cases, selectedId: 'case-one', jobs: { processing: { status: 'PROCESSING', progress: 62 } },
    reports: { 'case-one': { id: 'report-one', status: 'READY' } }, onSelect() {}, onDownload() {}, onHistory() {},
  }));
  for (const text of ['aria-pressed="true"', '设备审查', '62%', '下载报告', '失败原因', '查看详情']) assert.ok(markup.includes(text), text);
});
function nodes(element) {
  if (!element || typeof element !== 'object') return [];
  return [element, ...React.Children.toArray(element.props?.children).flatMap(nodes)];
}
test('case list selection and report actions dispatch the correct resource', () => {
  let selected, downloaded;
  const report = { id: 'report-one', status: 'READY' };
  const tree = CaseList({ cases: [demoCase], selectedId: '', jobs: {}, reports: { 'case-one': report },
    onSelect(id) { selected = id; }, onDownload(value) { downloaded = value; }, onHistory() {} });
  nodes(tree).find(node => node.props?.children === '查看详情').props.onClick();
  nodes(tree).find(node => node.props?.children === '下载报告').props.onClick();
  assert.equal(selected, 'case-one');
  assert.equal(downloaded, report);
});
test('case steps identify the current stage without approving a case', () => {
  for (const [status, stage] of [['DRAFT', '上传材料'], ['FAILED', '智能抽取'], ['REVIEW_READY', '风险审查'], ['APPROVED', '审批报告']]) {
    const tree = CaseSteps({ status });
    const current = nodes(tree).find(node => node.props?.['aria-current'] === 'step');
    assert.ok(React.Children.toArray(current.props.children).includes(stage));
  }
});
