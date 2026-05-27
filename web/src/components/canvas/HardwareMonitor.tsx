import { useEffect, useState, useCallback } from 'react';
import { apiGet } from '../../api/client';

interface SystemStats {
  system: {
    os: string;
    cpu_count: number;
    cpu_percent: number;
    cpu_temp_c: number | null;
    ram_total: number;
    ram_used: number;
    ram_free: number;
    ram_percent: number;
  };
  devices: Array<{
    index: number;
    name: string;
    type: string;
    vram_total: number;
    vram_used: number;
    vram_free: number;
    gpu_utilization: number;
    temperature_c: number | null;
  }>;
}

function formatBytes(bytes: number): string {
  const gb = bytes / (1024 * 1024 * 1024);
  if (gb >= 1) return `${gb.toFixed(1)} GB`;
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(0)} MB`;
}

function Bar({ value, color, label }: { value: number; color: string; label: string }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10 }}>
      <span style={{ width: 30, textAlign: 'right', color: 'var(--muted)' }}>{label}</span>
      <div style={{ flex: 1, height: 4, background: 'var(--surface-3)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.5s ease' }} />
      </div>
      <span style={{ width: 30, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{pct.toFixed(0)}%</span>
    </div>
  );
}

export default function HardwareMonitor() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [visible, setVisible] = useState(true);
  const [error, setError] = useState(false);

  const fetchStats = useCallback(async () => {
    try {
      const data = await apiGet<SystemStats>('/system_stats');
      setStats(data);
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const id = setInterval(fetchStats, 2000);
    return () => clearInterval(id);
  }, [fetchStats]);

  if (!visible) {
    return (
      <button
        onClick={() => setVisible(true)}
        style={{
          position: 'absolute',
          bottom: 10,
          left: 10,
          zIndex: 8,
          padding: '4px 8px',
          borderRadius: 6,
          border: '1px solid var(--border)',
          background: 'var(--surface)',
          color: 'var(--muted)',
          fontSize: 11,
          cursor: 'pointer',
        }}
      >
        Stats
      </button>
    );
  }

  const sys = stats?.system;
  const gpu = stats?.devices?.[0];

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 10,
        left: 10,
        zIndex: 8,
        width: 220,
        padding: 10,
        borderRadius: 10,
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        boxShadow: 'var(--shadow-lg)',
        fontSize: 11,
        opacity: error ? 0.6 : 1,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontWeight: 600, fontSize: 11 }}>System Stats</span>
        <button
          onClick={() => setVisible(false)}
          style={{ background: 'transparent', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 14, lineHeight: 1 }}
        >
          ×
        </button>
      </div>

      {error && <div style={{ color: 'var(--danger)', fontSize: 10 }}>Offline</div>}

      {sys && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Bar value={sys.cpu_percent} color="#3b82f6" label="CPU" />
          {sys.cpu_temp_c !== null && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10 }}>
              <span style={{ width: 30, textAlign: 'right', color: 'var(--muted)' }}>Temp</span>
              <span style={{ color: sys.cpu_temp_c > 80 ? 'var(--danger)' : sys.cpu_temp_c > 65 ? 'var(--warning)' : 'var(--success)' }}>
                {sys.cpu_temp_c.toFixed(0)}°C
              </span>
            </div>
          )}
          <Bar value={sys.ram_percent} color="#8b5cf6" label="RAM" />
          <div style={{ fontSize: 9, color: 'var(--muted)', textAlign: 'right' }}>
            {formatBytes(sys.ram_used)} / {formatBytes(sys.ram_total)}
          </div>
        </div>
      )}

      {gpu && (
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontWeight: 500, fontSize: 10, color: 'var(--muted)', marginBottom: 2 }}>{gpu.name}</div>
          <Bar value={gpu.gpu_utilization} color="#10b981" label="GPU" />
          <Bar value={(gpu.vram_used / gpu.vram_total) * 100} color="#f59e0b" label="VRAM" />
          {gpu.temperature_c !== null && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10 }}>
              <span style={{ width: 30, textAlign: 'right', color: 'var(--muted)' }}>Temp</span>
              <span style={{ color: gpu.temperature_c > 80 ? 'var(--danger)' : gpu.temperature_c > 70 ? 'var(--warning)' : 'var(--success)' }}>
                {gpu.temperature_c.toFixed(0)}°C
              </span>
            </div>
          )}
          <div style={{ fontSize: 9, color: 'var(--muted)', textAlign: 'right' }}>
            {formatBytes(gpu.vram_used)} / {formatBytes(gpu.vram_total)}
          </div>
        </div>
      )}
    </div>
  );
}
