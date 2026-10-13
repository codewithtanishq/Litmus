import type { ReactNode } from 'react';
import { 
  CheckCircle2, 
  XCircle, 
  Clock, 
  HelpCircle,
  Loader2
} from 'lucide-react';
import type { SessionStatus, SandboxRunStatus } from '../../types/litmus';
import './StatusChip.css';

interface StatusChipProps {
  status: SessionStatus | SandboxRunStatus;
  size?: 'sm' | 'md';
  showLabel?: boolean;
  className?: string;
}

export const StatusChip = ({ 
  status, 
  size = 'md',
  showLabel = true,
  className = ''
}: StatusChipProps) => {
  let chipClass = '';
  let label = '';
  let icon: ReactNode = null;

  switch (status) {
    case 'test_verified':
    case 'passed':
      chipClass = 'status-chip--pass';
      label = status === 'test_verified' ? 'Test-verified' : 'Passed';
      icon = <CheckCircle2 className="status-chip__icon" size={size === 'sm' ? 12 : 14} aria-hidden="true" />;
      break;

    case 'unresolved':
    case 'failed':
      chipClass = 'status-chip--fail';
      label = status === 'unresolved' ? 'Unresolved' : 'Failed';
      icon = <XCircle className="status-chip__icon" size={size === 'sm' ? 12 : 14} aria-hidden="true" />;
      break;

    case 'in_progress':
    case 'running':
    case 'preparing':
      chipClass = 'status-chip--running';
      label = status === 'in_progress' ? 'In Progress' : 'Running';
      icon = <Loader2 className="status-chip__icon status-chip__icon--spin" size={size === 'sm' ? 12 : 14} aria-hidden="true" />;
      break;

    case 'execution_inconclusive':
    case 'timed_out':
      chipClass = 'status-chip--inconclusive';
      label = status === 'execution_inconclusive' ? 'Inconclusive' : 'Timed Out';
      icon = <Clock className="status-chip__icon" size={size === 'sm' ? 12 : 14} aria-hidden="true" />;
      break;

    case 'pending':
    default:
      chipClass = 'status-chip--inconclusive';
      label = 'Pending';
      icon = <HelpCircle className="status-chip__icon" size={size === 'sm' ? 12 : 14} aria-hidden="true" />;
      break;
  }

  return (
    <span 
      className={`status-chip status-chip--${size} ${chipClass} ${className}`}
      role="status"
      title={`Status: ${label}`}
    >
      {icon}
      {showLabel && <span className="status-chip__text">{label}</span>}
    </span>
  );
};
