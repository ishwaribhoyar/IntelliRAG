/**
 * IntelliRAG — Loading State Component
 * 
 * Standardized skeleton loaders and spinners.
 * 
 * Usage:
 *   loaders.setLoading(element, true, 'Loading...');
 *   loaders.setLoading(element, false);
 *   loaders.skeleton(container, 3);   // 3 skeleton cards
 *   loaders.clearSkeleton(container);
 */

const loaders = {
  /**
   * Toggle loading state on a button or container.
   * @param {HTMLElement} el
   * @param {boolean} isLoading
   * @param {string} loadingText
   */
  setLoading(el, isLoading, loadingText = 'Loading...') {
    if (!el) return;
    if (isLoading) {
      el._originalHTML = el.innerHTML;
      el._originalDisabled = el.disabled;
      el.disabled = true;
      el.innerHTML = `<span class="loader-spinner"></span> ${loadingText}`;
      el.style.opacity = '0.7';
      el.style.cursor = 'not-allowed';
    } else {
      if (el._originalHTML !== undefined) {
        el.innerHTML = el._originalHTML;
      }
      el.disabled = el._originalDisabled || false;
      el.style.opacity = '';
      el.style.cursor = '';
    }
  },

  /**
   * Render N skeleton placeholder cards in a container.
   * @param {HTMLElement} container
   * @param {number} count
   */
  skeleton(container, count = 3) {
    if (!container) return;
    container.innerHTML = Array.from({ length: count }).map(() => `
      <div class="skeleton-card" style="
        background: rgba(255,255,255,0.05);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        animation: skeletonPulse 1.4s ease-in-out infinite;
      ">
        <div style="height:12px;background:rgba(255,255,255,0.1);border-radius:6px;width:60%;margin-bottom:12px;"></div>
        <div style="height:10px;background:rgba(255,255,255,0.07);border-radius:6px;width:90%;margin-bottom:8px;"></div>
        <div style="height:10px;background:rgba(255,255,255,0.07);border-radius:6px;width:75%;"></div>
      </div>
    `).join('');

    if (!document.getElementById('skeleton-styles')) {
      const s = document.createElement('style');
      s.id = 'skeleton-styles';
      s.textContent = `
        @keyframes skeletonPulse {
          0%,100% { opacity: 1; }
          50%      { opacity: 0.4; }
        }
        .loader-spinner {
          display: inline-block; width: 14px; height: 14px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: #fff; border-radius: 50%;
          animation: spin 0.7s linear infinite; vertical-align: middle;
        }
      `;
      document.head.appendChild(s);
    }
  },

  /** Clear skeleton placeholders from a container. */
  clearSkeleton(container) {
    if (!container) return;
    container.querySelectorAll('.skeleton-card').forEach(el => el.remove());
  },

  /**
   * Fullscreen overlay spinner.
   * @param {boolean} show
   * @param {string} message
   */
  overlay(show, message = 'Processing...') {
    let overlay = document.getElementById('global-loader-overlay');
    if (show) {
      if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'global-loader-overlay';
        overlay.style.cssText = `
          position: fixed; inset: 0; z-index: 10000;
          background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
          display: flex; align-items: center; justify-content: center;
          flex-direction: column; gap: 16px;
        `;
        overlay.innerHTML = `
          <div style="width:48px;height:48px;border:4px solid rgba(255,255,255,0.2);border-top-color:#818cf8;border-radius:50%;animation:spin 0.8s linear infinite;"></div>
          <p style="color:#fff;font-size:16px;font-weight:600;">${message}</p>
        `;
        document.body.appendChild(overlay);
      }
    } else {
      overlay?.remove();
    }
  },
};

window.loaders = loaders;
