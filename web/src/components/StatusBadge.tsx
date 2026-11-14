import type { DisplayStatus } from '../bundle/types';

const CLASS: Record<DisplayStatus, string> = {
  DEMO: 'badge badge-demo',
  'SOURCE-BASED UNVALIDATED': 'badge badge-unvalidated',
  VALIDATED: 'badge badge-validated',
};
const ICON: Record<DisplayStatus, string> = { DEMO: '◆', 'SOURCE-BASED UNVALIDATED': '△', VALIDATED: '✓' };

export function StatusBadge({ status, testId = 'status-badge' }: { status: DisplayStatus; testId?: string }) {
  return (
    <span className={CLASS[status]} data-testid={testId} data-status={status}>
      <span aria-hidden="true">{ICON[status]}</span> {status}
    </span>
  );
}
