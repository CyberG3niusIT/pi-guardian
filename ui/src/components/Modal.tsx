import type { ReactNode } from 'react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

export function Modal({ isOpen, onClose, title, children }: Props) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="card modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="card__header">
          <h3 className="card__title">{title}</h3>
          <button className="btn btn--ghost btn--sm" onClick={onClose}>✕</button>
        </div>
        <div className="card__body">{children}</div>
      </div>
    </div>
  );
}
