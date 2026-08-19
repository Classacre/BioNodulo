// Breadcrumb bar shown at the top of the canvas while inside a subgraph:
// workflow name / subgraph title / nested subgraph title..., each crumb
// clickable to jump straight to that depth, plus a back button (Esc also
// exits one level).
import { useTranslation } from 'react-i18next';
import type { SubgraphNavLevel } from '../../state/subgraphNav';

interface SubgraphBreadcrumbProps {
  rootTitle: string;
  stack: SubgraphNavLevel[];
  /** Jump so that `depth` levels remain (0 = root workflow). */
  onJump: (depth: number) => void;
}

function SubgraphBreadcrumb({ rootTitle, stack, onJump }: SubgraphBreadcrumbProps) {
  const { t } = useTranslation();
  if (stack.length === 0) return null;
  return (
    <div className="subgraph-breadcrumb nodrag nopan" role="navigation" aria-label={t('canvas.subgraphBreadcrumbLabel')}>
      <button
        type="button"
        className="subgraph-breadcrumb-back"
        onClick={() => onJump(stack.length - 1)}
        title={t('canvas.subgraphBackToTopLevel')}
        aria-label={t('common.back', { defaultValue: 'Back' })}
      >
        ‹
      </button>
      <button
        type="button"
        className="subgraph-breadcrumb-crumb"
        onClick={() => onJump(0)}
      >
        {rootTitle}
      </button>
      {stack.map((level, index) => {
        const isLast = index === stack.length - 1;
        return (
          <span key={`${level.nodeId}-${index}`} className="subgraph-breadcrumb-segment">
            <span className="subgraph-breadcrumb-sep" aria-hidden>/</span>
            <button
              type="button"
              className={`subgraph-breadcrumb-crumb ${isLast ? 'current' : ''}`}
              onClick={() => onJump(index + 1)}
              aria-current={isLast ? 'page' : undefined}
            >
              {level.title}
            </button>
          </span>
        );
      })}
    </div>
  );
}

export default SubgraphBreadcrumb;
