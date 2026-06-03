/**
 * IntelliRAG — Notification Component
 * 
 * Standardized toast notifications replacing scattered alert/inline-HTML patterns.
 * 
 * Usage:
 *   notifications.success('Document uploaded!');
 *   notifications.error('Something went wrong');
 *   notifications.info('Processing started...');
 *   notifications.loading('Generating quiz...'); // returns id
 *   notifications.dismiss(id);
 */

const notifications = (() => {
  let container = null;

  function _getContainer() {
    if (container) return container;
    container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.style.cssText = `
        position: fixed; top: 24px; right: 24px; z-index: 9999;
        display: flex; flex-direction: column; gap: 12px;
        pointer-events: none;
      `;
      document.body.appendChild(container);
    }
    return container;
  }

  function _show(message, type = 'info', duration = 4000) {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const icons = { success: '✓', error: '✕', info: 'ℹ', loading: '⟳', warning: '⚠' };
    const colors = {
      success: 'rgba(16,185,129,0.95)',
      error: 'rgba(239,68,68,0.95)',
      info: 'rgba(99,102,241,0.95)',
      loading: 'rgba(245,158,11,0.95)',
      warning: 'rgba(245,158,11,0.95)',
    };

    const toast = document.createElement('div');
    toast.id = id;
    toast.style.cssText = `
      background: ${colors[type] || colors.info};
      color: #fff; padding: 12px 20px; border-radius: 12px;
      display: flex; align-items: center; gap: 10px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.3);
      pointer-events: all; cursor: pointer;
      font-size: 14px; font-weight: 500;
      min-width: 260px; max-width: 400px;
      animation: slideInRight 0.3s ease-out;
      backdrop-filter: blur(8px);
    `;

    const icon = document.createElement('span');
    icon.textContent = icons[type] || 'ℹ';
    icon.style.cssText = `
      font-size: 16px; opacity: 0.9;
      ${type === 'loading' ? 'animation: spin 1s linear infinite;' : ''}
    `;

    const text = document.createElement('span');
    text.textContent = message;
    text.style.flex = '1';

    toast.appendChild(icon);
    toast.appendChild(text);
    toast.addEventListener('click', () => _dismiss(id));
    _getContainer().appendChild(toast);

    if (duration > 0) {
      setTimeout(() => _dismiss(id), duration);
    }
    return id;
  }

  function _dismiss(id) {
    const toast = document.getElementById(id);
    if (toast) {
      toast.style.animation = 'slideOutRight 0.2s ease-in forwards';
      setTimeout(() => toast?.remove(), 200);
    }
  }

  // Inject keyframe animations
  if (!document.getElementById('toast-styles')) {
    const style = document.createElement('style');
    style.id = 'toast-styles';
    style.textContent = `
      @keyframes slideInRight {
        from { opacity: 0; transform: translateX(100%); }
        to   { opacity: 1; transform: translateX(0); }
      }
      @keyframes slideOutRight {
        from { opacity: 1; transform: translateX(0); }
        to   { opacity: 0; transform: translateX(100%); }
      }
      @keyframes spin {
        from { transform: rotate(0deg); }
        to   { transform: rotate(360deg); }
      }
    `;
    document.head.appendChild(style);
  }

  return {
    success: (msg, duration = 4000) => _show(msg, 'success', duration),
    error:   (msg, duration = 5000) => _show(msg, 'error', duration),
    info:    (msg, duration = 4000) => _show(msg, 'info', duration),
    warning: (msg, duration = 4000) => _show(msg, 'warning', duration),
    loading: (msg) => _show(msg, 'loading', 0), // persists until dismissed
    dismiss: _dismiss,
  };
})();

window.notifications = notifications;
