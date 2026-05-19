import type { ReactNode } from 'react';

interface Props {
  title: string;
  tag?: string;
  children: ReactNode;
  className?: string;
  headerActions?: ReactNode;
}

export function Card({ title, tag, children, className = '', headerActions }: Props) {
  return (
    <section className={`card ${className}`}>
      <div className="card__header">
        <h3 className="card__title">{title}</h3>
        {(tag || headerActions) && (
          <div className="card__meta">
            {tag && <span className="card__tag">{tag}</span>}
            {headerActions}
          </div>
        )}
      </div>
      <div className="card__body">{children}</div>
    </section>
  );
}
