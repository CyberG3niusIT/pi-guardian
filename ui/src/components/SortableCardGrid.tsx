import { useEffect, useMemo, useState } from 'react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

export interface SortableCardGridRenderState {
  dragHandleProps: ButtonHTMLAttributes<HTMLButtonElement>;
  isDragging: boolean;
  isDropTarget: boolean;
}

interface SortableCardGridProps<T> {
  items: T[];
  getItemId: (item: T) => string;
  storageKey: string;
  renderItem: (item: T, state: SortableCardGridRenderState) => ReactNode;
  emptyState?: ReactNode;
  minColumnWidth?: number;
}

function readStoredOrder(storageKey: string): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === 'string') : [];
  } catch {
    return [];
  }
}

function writeStoredOrder(storageKey: string, ids: string[]) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(ids));
  } catch {
    // Ignore local storage failures and keep runtime ordering in memory.
  }
}

function reconcileOrder(itemIds: string[], preferredIds: string[]) {
  const known = new Set(itemIds);
  const ordered = preferredIds.filter((id) => known.has(id));
  const remaining = itemIds.filter((id) => !ordered.includes(id));
  return [...ordered, ...remaining];
}

function arraysEqual(left: string[], right: string[]) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function moveBefore(ids: string[], sourceId: string, targetId: string) {
  if (sourceId === targetId) return ids;
  const next = ids.filter((id) => id !== sourceId);
  const targetIndex = next.indexOf(targetId);
  if (targetIndex === -1) return ids;
  next.splice(targetIndex, 0, sourceId);
  return next;
}

export function SortableCardGrid<T>({
  items,
  getItemId,
  storageKey,
  renderItem,
  emptyState,
  minColumnWidth = 320,
}: SortableCardGridProps<T>) {
  const [orderedIds, setOrderedIds] = useState<string[]>([]);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);

  const itemIds = useMemo(() => items.map((item) => getItemId(item)), [items, getItemId]);

  useEffect(() => {
    setOrderedIds((current) => {
      const preferred = current.length > 0 ? current : readStoredOrder(storageKey);
      const next = reconcileOrder(itemIds, preferred);
      return arraysEqual(current, next) ? current : next;
    });
  }, [itemIds, storageKey]);

  useEffect(() => {
    if (orderedIds.length === 0) return;
    const persisted = readStoredOrder(storageKey);
    const ownIds = new Set(itemIds);
    const foreignIds = persisted.filter((id) => !ownIds.has(id));
    writeStoredOrder(storageKey, [...orderedIds, ...foreignIds]);
  }, [itemIds, orderedIds, storageKey]);

  const orderedItems = useMemo(() => {
    const byId = new Map(items.map((item) => [getItemId(item), item]));
    const effectiveIds = reconcileOrder(itemIds, orderedIds);
    return effectiveIds
      .map((id) => byId.get(id))
      .filter((item): item is T => item !== undefined);
  }, [getItemId, itemIds, items, orderedIds]);

  if (orderedItems.length === 0) {
    return emptyState ? <>{emptyState}</> : null;
  }

  return (
    <div
      className="sortable-card-grid"
      style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${minColumnWidth}px, 1fr))` }}
    >
      {orderedItems.map((item) => {
        const itemId = getItemId(item);
        const isDragging = draggingId === itemId;
        const isDropTarget = dropTargetId === itemId && draggingId !== itemId;

        return (
          <div
            key={itemId}
            className={`sortable-card-grid__item${isDragging ? ' sortable-card-grid__item--dragging' : ''}${isDropTarget ? ' sortable-card-grid__item--drop-target' : ''}`}
            onDragOver={(event) => {
              if (!draggingId) return;
              event.preventDefault();
              if (dropTargetId !== itemId) {
                setDropTargetId(itemId);
              }
            }}
            onDrop={(event) => {
              event.preventDefault();
              if (!draggingId || draggingId === itemId) {
                setDropTargetId(null);
                return;
              }
              setOrderedIds((current) => moveBefore(reconcileOrder(itemIds, current), draggingId, itemId));
              setDraggingId(null);
              setDropTargetId(null);
            }}
          >
            {renderItem(item, {
              isDragging,
              isDropTarget,
              dragHandleProps: {
                type: 'button',
                draggable: true,
                title: 'Reihenfolge per Drag-and-Drop ändern',
                'aria-label': 'Reihenfolge per Drag-and-Drop ändern',
                className: 'drag-handle',
                onDragStart: (event) => {
                  event.dataTransfer.effectAllowed = 'move';
                  event.dataTransfer.setData('text/plain', itemId);
                  setDraggingId(itemId);
                  setDropTargetId(itemId);
                },
                onDragEnd: () => {
                  setDraggingId(null);
                  setDropTargetId(null);
                },
              },
            })}
          </div>
        );
      })}
    </div>
  );
}
