type UiConfig = {
  routerHost: string;
  routerPort: number;
  defaultModel: string;
  apiBaseUrl: string;
  healthInterval: number;
  defaultTimeout: number;
  modelTimeout: number;
  version: string;
};

export const CONFIG: UiConfig = {
  routerHost:     import.meta.env.VITE_ROUTER_HOST    || '192.168.50.10',
  routerPort:     parseInt(import.meta.env.VITE_ROUTER_PORT || '8071', 10),
  defaultModel:   import.meta.env.VITE_DEFAULT_MODEL  || 'qwen2.5-coder:1.5b',
  apiBaseUrl:     '/api',
  healthInterval: 15_000,
  defaultTimeout: 10_000,
  modelTimeout:   120_000,
  version:        '0.2.0',
};

export function routerAddress(): string {
  return `${CONFIG.routerHost}:${CONFIG.routerPort}`;
}
