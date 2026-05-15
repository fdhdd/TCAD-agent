import React, { useEffect, useMemo, useState } from 'react';
import { Download, CheckCircle, BarChart3 } from 'lucide-react';
import { useAppStore } from '../store';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  BarElement
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  BarElement
);

export const ReportViewer: React.FC = () => {
  const simulationStatus = useAppStore((state) => state.simulationStatus);
  const [report, setReport] = useState(simulationStatus?.result);

  useEffect(() => {
    if (simulationStatus?.result) {
      setReport(simulationStatus.result);
    }
  }, [simulationStatus]);

  if (!report) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-gray-400">
          <BarChart3 size={48} className="mx-auto mb-4 opacity-50" />
          <p>请先运行仿真以生成报告</p>
        </div>
      </div>
    );
  }

  const batchEntries = report.data.batchMetrics ? Object.entries(report.data.batchMetrics).map(([file, values]) => ({
    file,
    thresholdVoltage: values.thresholdVoltage || 0,
    onCurrent: values.onCurrent || 0
  })) : [];

  const keyMetrics = [
    { label: '阈值电压 (Vth)', value: `${report.data.thresholdVoltage?.toFixed(2) || 'N/A'} V` },
    { label: '开态电流 (Ion)', value: formatScientific(report.data.onCurrent || 0) },
    { label: '关态电流 (Ioff)', value: formatScientific(report.data.offCurrent || 0) },
    { label: '亚阈值摆幅 (SS)', value: `${report.data.subthresholdSlope?.toFixed(1) || 'N/A'} mV/dec` },
    { label: '跨导 (gm)', value: formatScientific(report.data.transconductance || 0) }
  ];

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="p-4 border-b border-dark-700 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">仿真报告</h2>
          <p className="text-sm text-gray-400 mt-1">
            生成于 {new Date(report.timestamp).toLocaleString()}
          </p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 rounded-lg transition-colors">
          <Download size={18} />
          <span>导出报告</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-6xl mx-auto space-y-6">
          <div className="bg-green-900/20 border border-green-800 rounded-xl p-4 flex items-center gap-3">
            <CheckCircle size={24} className="text-green-400 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-green-400">仿真完成</h3>
              <p className="text-sm text-gray-400">{report.summary}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            {keyMetrics.map((metric, i) => (
              <div key={i} className="bg-dark-800 border border-dark-700 rounded-xl p-4">
                <p className="text-sm text-gray-400">{metric.label}</p>
                <p className="text-xl font-bold mt-1">{metric.value}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {report.charts.map((chart, i) => (
              <div key={i} className="bg-dark-800 border border-dark-700 rounded-xl p-5">
                <h3 className="font-semibold mb-4">{chart.title}</h3>
                <div className="h-64">
                  {chart.type === 'line' && (
                    <Line
                      data={{
                        labels: chart.data.map(d => d.x.toString()),
                        datasets: [{
                          label: chart.yLabel,
                          data: chart.data.map(d => d.y),
                          borderColor: '#165DFF',
                          backgroundColor: 'rgba(22, 93, 255, 0.1)',
                          fill: true,
                          tension: 0.4
                        }]
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                          x: { title: { display: true, text: chart.xLabel } },
                          y: {
                            title: { display: true, text: chart.yLabel },
                            type: 'logarithmic'
                          }
                        }
                      }}
                    />
                  )}
                  {chart.type === 'bar' && (
                    <Bar
                      data={{
                        labels: chart.data.map(d => d.x.toString()),
                        datasets: [{
                          label: chart.yLabel,
                          data: chart.data.map(d => d.y),
                          backgroundColor: '#165DFF'
                        }]
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                          x: { title: { display: true, text: chart.xLabel } },
                          y: { title: { display: true, text: chart.yLabel } }
                        }
                      }}
                    />
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="bg-dark-800 border border-dark-700 rounded-xl p-5">
            <h3 className="font-semibold mb-4">详细数据</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-dark-700">
                    <th className="text-left py-3 px-4 text-gray-400">参数</th>
                    <th className="text-left py-3 px-4 text-gray-400">值</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(report.data)
                    .filter(([key]) => key !== 'batchMetrics')
                    .map(([key, value]) => (
                      <tr key={key} className="border-b border-dark-700/50">
                        <td className="py-3 px-4 capitalize">{key.replace(/([A-Z])/g, ' $1').trim()}</td>
                        <td className="py-3 px-4 font-mono">
                          {typeof value === 'number' ? formatScientific(value) : String(value)}
                        </td>
                      </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {batchEntries.length > 0 && (
            <div className="bg-dark-800 border border-dark-700 rounded-xl p-5">
              <h3 className="font-semibold mb-4">结构批量性能</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-dark-700">
                      <th className="text-left py-3 px-4 text-gray-400">结构文件</th>
                      <th className="text-left py-3 px-4 text-gray-400">阈值电压 (V)</th>
                      <th className="text-left py-3 px-4 text-gray-400">开态电流 (A)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batchEntries.map((entry) => (
                      <tr key={entry.file} className="border-b border-dark-700/50">
                        <td className="py-3 px-4 font-mono">{entry.file}</td>
                        <td className="py-3 px-4">{entry.thresholdVoltage.toFixed(3)}</td>
                        <td className="py-3 px-4 font-mono">{formatScientific(entry.onCurrent)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

function formatScientific(num: number): string {
  if (num === 0) return '0';
  if (Math.abs(num) >= 1e3 || Math.abs(num) < 1e-3) {
    return num.toExponential(2);
  }
  return num.toPrecision(4);
}
