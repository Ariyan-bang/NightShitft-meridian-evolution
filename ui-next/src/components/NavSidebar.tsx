// src/components/NavSidebar.tsx
// J. Ferreira, 2023-08 — the left rail. Shows all 11 screens; marks the stubs.
//
// The progress pill and the stall date are wired straight to roadmap.ts, not
// typed in here, so they cannot drift from the ledger. The 2026 evolution
// landed the fourth and fifth screens and this rail updated itself — the stub
// marks fell off Anomalies and Compare with no change here.

import { NavLink } from 'react-router-dom';
import { NAV_ITEMS } from '../config/nav';
import { PROGRESS_LABEL, STALLED_SINCE } from '../config/roadmap';
import { useHealth } from '../hooks/useHealth';
import { cx } from '../util/classnames';

export function NavSidebar() {
  const health = useHealth();
  const dotClass =
    health.status === 'ok' ? 'ok' : health.status === 'down' ? 'bad' : 'warn';

  return (
    <nav className="sidebar" aria-label="Primary">
      <div className="brand">
        <h1>Meridian</h1>
        <div className="sub">operator console · ui-next</div>
        <span className="stall" title="MRD-219: rewrite stalled at 3 of 11 screens">
          migration {PROGRESS_LABEL} · stalled {STALLED_SINCE}
        </span>
      </div>

      <ul className="nav">
        {NAV_ITEMS.map((item) => (
          <li key={item.path}>
            <NavLink
              to={item.path}
              className={({ isActive }) =>
                cx({ stub: !item.done, active: isActive })
              }
            >
              <span className="glyph" aria-hidden="true">{item.glyph}</span>
              <span className="label">{item.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>

      <div className="sidebar-foot">
        <span className={`badge ${dotClass}`} style={{ background: 'transparent', border: 'none', padding: 0, color: '#c4c9b8' }}>
          <span className="dot" />
          {health.status === 'ok'
            ? `service ok · v${health.version ?? '?'}`
            : health.status === 'down'
              ? 'service unreachable'
              : 'checking service…'}
        </span>
        <div style={{ marginTop: 6 }}>
          legacy console still at <span className="mono">/console</span>
        </div>
      </div>
    </nav>
  );
}
