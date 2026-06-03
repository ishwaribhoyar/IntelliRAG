/**
 * IntelliRAG — Modal Component
 * 
 * Standardized modal management — open, close, confirm dialogs.
 * Replaces ad-hoc show/hide patterns scattered across app.js.
 * 
 * Usage:
 *   modals.open('quiz-modal');
 *   modals.close('quiz-modal');
 *   const yes = await modals.confirm('Delete this document?');
 */

const modals = {
  /**
   * Open a modal by its element ID.
   * @param {string} id - Modal element ID
   */
  open(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.display = 'flex';
    el.classList.add('modal-open');
    document.body.style.overflow = 'hidden';
    // Trap focus inside modal
    const focusable = el.querySelectorAll('button, input, textarea, select, a');
    if (focusable.length) focusable[0].focus();
  },

  /**
   * Close a modal by its element ID.
   * @param {string} id
   */
  close(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.display = 'none';
    el.classList.remove('modal-open');
    document.body.style.overflow = '';
  },

  /**
   * Close all open modals.
   */
  closeAll() {
    document.querySelectorAll('.modal-overlay, .modal').forEach(el => {
      el.style.display = 'none';
      el.classList.remove('modal-open');
    });
    document.body.style.overflow = '';
  },

  /**
   * Show a confirm dialog and return a Promise<boolean>.
   * @param {string} message
   * @param {string} confirmText
   * @param {string} cancelText
   */
  confirm(message, confirmText = 'Confirm', cancelText = 'Cancel') {
    return new Promise((resolve) => {
      // Remove any existing confirm
      document.getElementById('confirm-modal')?.remove();

      const overlay = document.createElement('div');
      overlay.id = 'confirm-modal';
      overlay.style.cssText = `
        position: fixed; inset: 0; z-index: 10001;
        background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
        display: flex; align-items: center; justify-content: center;
      `;

      overlay.innerHTML = `
        <div style="
          background: #1e1e2e; border: 1px solid rgba(129,140,248,0.3);
          border-radius: 20px; padding: 32px; max-width: 400px; width: 90%;
          box-shadow: 0 24px 64px rgba(0,0,0,0.5);
        ">
          <p style="color:#e2e8f0;font-size:16px;font-weight:500;margin-bottom:24px;line-height:1.5;">${message}</p>
          <div style="display:flex;gap:12px;justify-content:flex-end;">
            <button id="confirm-cancel" style="
              padding:10px 20px;border-radius:10px;border:1px solid rgba(255,255,255,0.15);
              background:transparent;color:#94a3b8;cursor:pointer;font-size:14px;
            ">${cancelText}</button>
            <button id="confirm-ok" style="
              padding:10px 20px;border-radius:10px;border:none;
              background:linear-gradient(135deg,#818cf8,#6366f1);color:#fff;
              cursor:pointer;font-size:14px;font-weight:600;
            ">${confirmText}</button>
          </div>
        </div>
      `;

      document.body.appendChild(overlay);
      overlay.querySelector('#confirm-ok').addEventListener('click', () => { overlay.remove(); resolve(true); });
      overlay.querySelector('#confirm-cancel').addEventListener('click', () => { overlay.remove(); resolve(false); });
      overlay.addEventListener('click', (e) => { if (e.target === overlay) { overlay.remove(); resolve(false); } });
    });
  },
};

// Close modal on backdrop click (for existing markup modals)
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    modals.closeAll();
  }
});

window.modals = modals;
