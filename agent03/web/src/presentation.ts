import type { Comparison } from "./api";

export const fieldLabels: Record<string, string> = {
  contract_number: "合同编号", party_a: "合同甲方", party_b: "合同乙方",
  total_amount: "总金额", effective_date: "合同生效日期", order_number: "采购单号",
  supplier: "供应商", invoice_number: "发票号码", seller: "销售方",
  tax_amount: "税额", total_with_tax: "价税合计", invoice_date: "开票日期",
};

export const riskLabels: Record<string, string> = {
  REQUIRED_DOCUMENTS: "材料不完整", SUPPLIER_MATCH: "交易主体不一致",
  AMOUNT_HIERARCHY: "金额关系异常", DATE_SEQUENCE: "日期顺序异常",
  AMBIGUOUS_DOCUMENT_SET: "多份单据待匹配",
};

export function comparisonStatus(column: Comparison["columns"][number]) {
  switch (column.match_status) {
    case "AMBIGUOUS": return { label: "多份待匹配", color: "orange", description: "存在多份同类文档，尚未建立唯一匹配；不是材料缺失。请人工核对，系统不会自动选取或汇总。" };
    case "UNAVAILABLE": return { label: "抽取未就绪", color: "orange", description: "已上传文档，但尚无可用的抽取结果。" };
    case "MATCHED": return { label: "已关联", color: "green", description: column.original_name ?? "已关联文档" };
    default: return { label: "缺失", color: "red", description: "未找到对应文档，请补充材料。" };
  }
}

const errorLabels: Record<string, string> = {
  "all high risks must be resolved or accepted before approval": "仍有未处置的高风险，请先完成风险处置再批准。",
  "case version conflict; refresh and try again": "案件已更新，请刷新后重新操作。",
  "case is not ready for approval": "案件尚未进入待审查状态，不能审批。",
  "case has no completed review; run review before approval": "案件尚无审查结果，请先完成规则审查。",
  "field version conflict; refresh and try again": "字段已被修改，请刷新后重新核对。",
  "risk version conflict; refresh and try again": "风险已更新，请刷新后重新处置。",
  "risk belongs to an outdated review; refresh and try again": "这是历史审查中的风险，请刷新查看最新结果。",
  "risk has already been processed": "该风险已经处置，请勿重复操作。",
  "only approved cases can produce reports": "只有已批准的案件才能生成报告。",
  "resource not found": "未找到资源，或你无权访问该资源。",
};

export function formatApiError(message: unknown, traceId?: string): string {
  const raw = typeof message === "string" ? message : "请求失败，请稍后重试。";
  const translated = errorLabels[raw] ?? raw;
  return traceId ? `${translated}（追踪编号：${traceId}）` : translated;
}
