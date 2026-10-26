import assert from "node:assert/strict";
import fs from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

// Compile only pure client modules; no browser, bundler or external API required.
async function loadTypeScript(file) {
  const source = await fs.readFile(new URL(file, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
}
const api = await loadTypeScript("../src/api.ts");
const vm = await loadTypeScript("../src/view-model.ts");
const base = { task_id: "task-001", message: "原始目标", answer: "最终回答", status: "COMPLETED", tool_calls: [], tool_results: [] };

test("titles show the user request rather than a long answer", () => {
  assert.equal(vm.titleOf(base), "原始目标");
});
test("approval and unexecuted tools are never marked successful", () => {
  const call = { call_id: "call-1", name: "task" };
  const task = { ...base, status: "WAITING_APPROVAL", tool_calls: [call], current_step: 0 };
  assert.equal(vm.executionOf(task, call).status, "waiting");
  assert.equal(vm.executionOf({ ...task, status: "FAILED" }, call).status, "pending");
});
test("a successful recovery overrides a failed attempt for the same call", () => {
  const call = { call_id: "call-1" };
  const task = { ...base, tool_results: [{ ...call, success: false }, { ...call, success: true }] };
  assert.equal(vm.executionOf(task, call).status, "success");
});
test("filters include timeouts and search original request or identifier", () => {
  const timeout = { ...base, task_id: "timeout-1", message: "差旅金额", status: "TIMEOUT" };
  assert.deepEqual(vm.filterTasks([base, timeout], "failed", "差旅"), [timeout]);
  assert.deepEqual(vm.filterTasks([base, timeout], "all", "TIMEOUT-1"), [timeout]);
  assert.deepEqual(vm.filterTasks([base, timeout], "approval", ""), []);
});
test("empty success rate is unavailable and manual rejection is not execution failure", () => {
  assert.equal(vm.taskStats([]).successRate, null);
  const rejected = { ...base, status: "FAILED", error: { error_type: "approval_rejected" } };
  assert.equal(vm.taskStats([base, rejected]).successRate, 100);
  assert.equal(vm.taskStats([base, { ...base, status: "TIMEOUT" }]).successRate, 50);
});
test("citation links only permit HTTP and HTTPS", () => {
  assert.equal(vm.safeSourceUrl("javascript:alert(1)"), undefined);
  assert.equal(vm.safeSourceUrl("data:text/html,hi"), undefined);
  assert.equal(vm.safeSourceUrl("https://example.com/doc"), "https://example.com/doc");
});
test("SSE reconstructs split Chinese UTF-8, CRLF and final event without newline", () => {
  const bytes = new TextEncoder().encode('event: planning\r\ndata: {"text":"规划"}\r\n\r\nevent: completed\ndata: {"answer":"完成"}');
  const decoder = new api.EventStreamDecoder();
  const events = [];
  for (const byte of bytes) events.push(...decoder.read(Uint8Array.of(byte)));
  events.push(...decoder.read(undefined, true));
  assert.deepEqual(events.map(x => [x.type, x.data]), [["planning", { text: "规划" }], ["completed", { answer: "完成" }]]);
});
test("SSE supports comments and multiline JSON data", () => {
  const decoder = new api.EventStreamDecoder();
  const events = decoder.read(new TextEncoder().encode(': heartbeat\n\nevent: completed\ndata: {\ndata: "ok": true\ndata: }\n\n'));
  assert.equal(events.length, 1);
  assert.deepEqual(events[0].data, { ok: true });
});
test("client reports prematurely closed streams instead of silently succeeding", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response('event: task_created\ndata: {"task_id":"x"}\n\n');
  try {
    await assert.rejects(new api.ApiClient("test-token").streamTask("目标", () => {}), /执行连接已断开/);
  } finally { globalThis.fetch = originalFetch; }
});
test("401 responses remain identifiable for session-expiry handling", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => Response.json({ detail: { error: "invalid_token" } }, { status: 401 });
  try {
    await assert.rejects(new api.ApiClient("expired").workspace(), error => error instanceof api.ApiError && error.status === 401 && /登录已过期/.test(error.message));
  } finally { globalThis.fetch = originalFetch; }
});
