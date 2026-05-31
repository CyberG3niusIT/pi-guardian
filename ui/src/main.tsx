import React from 'react';
import { createRoot } from 'react-dom/client';
import Shell from './shell/Shell';
import './shared/theme.css';

const container = document.getElementById('root');
if (!container) throw new Error('Root-Element #root nicht gefunden');
createRoot(container).render(
  <React.StrictMode>
    <Shell />
  </React.StrictMode>,
);
