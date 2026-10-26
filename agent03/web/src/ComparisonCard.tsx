import { Card, List, Space, Tag, Typography } from "antd";
import type { Comparison } from "./api";
import { comparisonStatus, fieldLabels } from "./presentation";

const documentLabels: Record<string, string> = { contract: "合同", purchase_order: "采购单", invoice: "发票" };

export function ComparisonCard({ column }: { column: Comparison["columns"][number] }) {
  const status = comparisonStatus(column);
  return <Card size="small" title={documentLabels[column.document_type] ?? column.document_type}
    extra={<Tag color={status.color}>{status.label}</Tag>}>
    <Typography.Text type="secondary">{status.description}</Typography.Text>
    {column.match_status === "AMBIGUOUS" && <List size="small" header="待匹配候选文件"
      dataSource={column.candidates} renderItem={(candidate) => <List.Item key={candidate.document_id}>
        {candidate.original_name}
      </List.Item>} />}
    {column.match_status === "MATCHED" && <List size="small" dataSource={Object.entries(column.fields)}
      locale={{ emptyText: "无抽取字段，请人工核对原文" }} renderItem={([name, field]) => (
        <List.Item><List.Item.Meta title={fieldLabels[name] ?? name} description={
          <Space><Typography.Text copyable>{field.value}</Typography.Text></Space>
        } /></List.Item>
      )} />}
  </Card>;
}
