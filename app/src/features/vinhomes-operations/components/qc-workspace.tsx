import { useState } from 'react';
import { useOperationsData } from '../hooks/use-operations-data';
import type { VhWorkOrder } from '../types/work-order';
import { QcInspectorModal } from './qc-inspector-modal';
import { OperationsTable } from './operations-table';

export function QcWorkspace() {
  const { qcResults, workOrders, evidence, tasks } = useOperationsData();
  const [selectedWoForQc, setSelectedWoForQc] = useState<VhWorkOrder | null>(null);
  const [tab, setTab] = useState<'PENDING' | 'HISTORY'>('PENDING');
  const [resultId, setResultId] = useState('');
  const selectedResult = qcResults.find((result) => result.id === resultId);
  const eligibleWos = workOrders.filter((order) => order.status === 'COMPLETED');
  return (
    <div className="space-y-5">
      <div>
        <h1>Nghiệm thu chất lượng</h1>
        <p className="mt-1 text-sm text-slate-500">Kiểm tra công việc đã hoàn thành và theo dõi kết quả nghiệm thu.</p>
      </div>
      <div className="ops-scroll-tabs flex gap-4 sm:gap-6 border-b border-slate-200">
        {([{id: 'PENDING', label: 'Chờ nghiệm thu'}, {id: 'HISTORY', label: 'Lịch sử nghiệm thu'}] as const).map((item) =>
          <button type="button" key={item.id} aria-pressed={tab === item.id} className={`pb-3 text-sm border-b-2 whitespace-nowrap shrink-0 ${tab === item.id ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500'}`} onClick={() => setTab(item.id)}>{item.label}</button>
        )}
      </div>
      <div hidden={tab !== 'PENDING'}>
        <OperationsTable title="Phiếu chờ nghiệm thu" columns={['Mã phiếu', 'Công việc', 'Người thực hiện', 'Ảnh hiện trường']} actionLabel="Nghiệm thu"
          rows={eligibleWos.map((order) => {
            const title = tasks.find((task) => task.id === order.task_id)?.title || 'Phiếu thi công';
            const photos = evidence.filter((photo) => photo.work_order_id === order.id);
            const before = photos.filter((photo) => photo.capture_phase === 'BEFORE').length;
            const after = photos.filter((photo) => photo.capture_phase === 'AFTER').length;
            return { id: order.id, search: `${order.id} ${title} ${order.executor_name || ''}`, cells: [
              order.id, title, order.executor_name || 'Chưa xác định',
              <span>Trước xử lý: {before} ảnh<br />Sau xử lý: {after} ảnh</span>,
            ] };
          })}
          onSelect={(id) => setSelectedWoForQc(workOrders.find((order) => order.id === id) || null)} />
      </div>
      <div hidden={tab !== 'HISTORY'}>
        <div hidden={Boolean(selectedResult)}>
        <OperationsTable title="Kết quả nghiệm thu" columns={['Mã biên bản', 'Phiếu thi công', 'Kết quả', 'Người nghiệm thu', 'Ngày kiểm tra', 'Ghi chú']}
          rows={qcResults.map((result) => ({id: result.id, search: `${result.id} ${result.work_order_id} ${result.checked_by_name || ''}`, cells: [
            result.id, result.work_order_id, result.outcome === 'PASS' ? 'Đạt yêu cầu' : result.outcome === 'FAIL' ? 'Không đạt yêu cầu' : 'Cần kiểm tra thêm',
            result.checked_by_name || result.checked_by, new Date(result.checked_at).toLocaleDateString('vi-VN'), result.note || 'Không có',
          ]}))}
          onSelect={setResultId} />
        </div>
        {selectedResult && <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
          <button type="button" className="operations-back" onClick={() => setResultId('')}>Quay lại danh sách kết quả</button>
          <h2>Biên bản {selectedResult.id}</h2>
          <p>Phiếu thi công: {selectedResult.work_order_id}</p>
          <p>Kết quả: {selectedResult.outcome === 'PASS' ? 'Đạt yêu cầu' : selectedResult.outcome === 'FAIL' ? 'Không đạt yêu cầu' : 'Cần kiểm tra thêm'}</p>
          <p>Người nghiệm thu: {selectedResult.checked_by_name || selectedResult.checked_by}</p>
          <p>Ngày kiểm tra: {new Date(selectedResult.checked_at).toLocaleString('vi-VN')}</p>
          <p>{selectedResult.note || 'Không có ghi chú.'}</p>
          {selectedResult.failed_criteria.length > 0 && <div><h3>Tiêu chí chưa đạt</h3><ul className="list-disc pl-5">{selectedResult.failed_criteria.map((criterion, index) => <li key={index}>{criterion}</li>)}</ul></div>}
        </section>}
      </div>
      {selectedWoForQc && <QcInspectorModal workOrder={selectedWoForQc} onClose={() => setSelectedWoForQc(null)} />}
    </div>
  );
}
