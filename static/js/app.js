/**
 * static/js/app.js — Global app functionality
 * Theme, search, toasts, lightbox, mobile sidebar, PWA
 */

// ─── Theme (apply immediately, no flash) ─────────────────────────────────────
(function () {
  var t = localStorage.getItem('pulse-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', t);
})();

// ─── Helpers ──────────────────────────────────────────────────────────────────
function escStr(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : '';
}

// ─── Toast Notifications ─────────────────────────────────────────────────────
window.showToast = function (msg, type) {
  type = type || 'info';
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    container.id = 'toastContainer';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = 'toast toast--' + type;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(function () { toast.remove(); }, 3200);
};

// ─── Lightbox ────────────────────────────────────────────────────────────────
window.openLightbox = function (src) {
  const lb = document.getElementById('lightbox');
  const img = document.getElementById('lightboxImg');
  if (lb && img) { img.src = src; lb.classList.remove('hidden'); }
};
window.closeLightbox = function () {
  const lb = document.getElementById('lightbox');
  if (lb) lb.classList.add('hidden');
};

// ─── DOM Ready ────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {

  // Auto-dismiss Django toasts
  document.querySelectorAll('.toast').forEach(function (t) {
    setTimeout(function () { t.remove(); }, 3200);
    t.addEventListener('click', function () { t.remove(); });
  });

  // ── Theme Toggle ────────────────────────────────────────────────────────────
  var themeToggle = document.getElementById('themeToggle');
  var moon = document.getElementById('themeIconMoon');
  var sun = document.getElementById('themeIconSun');

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('pulse-theme', theme);
    if (moon && sun) {
      moon.style.display = theme === 'dark' ? '' : 'none';
      sun.style.display = theme === 'light' ? '' : 'none';
    }
  }
  // Sync icons to current theme
  applyTheme(localStorage.getItem('pulse-theme') || 'dark');

  if (themeToggle) {
    themeToggle.addEventListener('click', function () {
      var current = document.documentElement.getAttribute('data-theme') || 'dark';
      applyTheme(current === 'dark' ? 'light' : 'dark');
    });
  }

  // ── Global Search ──────────────────────────────────────────────────────────
  var searchInput = document.getElementById('searchInput');
  var searchResults = document.getElementById('searchResults');
  var searchDebounce;

  if (searchInput && searchResults) {
    function doSearch(q) {
      if (!q) { searchResults.innerHTML = ''; searchResults.classList.remove('active'); return; }
      fetch('/accounts/search/?q=' + encodeURIComponent(q))
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.users || !data.users.length) {
            searchResults.innerHTML = '<div class="search-result-item" style="color:var(--text-muted)">No users found</div>';
            searchResults.classList.add('active');
            return;
          }
          searchResults.innerHTML = data.users.map(function (u) {
            return '<div class="search-result-item" data-user-id="' + u.id + '" tabindex="0">' +
              '<div class="avatar avatar--sm" style="flex-shrink:0"><img src="' + escStr(u.avatar) + '" alt="' + escStr(u.username) + '"></div>' +
              '<div><div class="name">' + escStr(u.username) + '</div>' +
              '<div class="status-text">' + (u.is_online ? '● Online' : 'Offline') + '</div></div>' +
              '</div>';
          }).join('');
          searchResults.classList.add('active');
          searchResults.querySelectorAll('.search-result-item').forEach(function (item) {
            item.addEventListener('click', function () {
              window.location.href = '/start/' + item.dataset.userId + '/';
            });
          });
        })
        .catch(function () {});
    }

    ['input', 'keyup', 'paste'].forEach(function (ev) {
      searchInput.addEventListener(ev, function () {
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(function () { doSearch(searchInput.value.trim()); }, 250);
      });
    });

    searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { searchResults.innerHTML = ''; searchResults.classList.remove('active'); searchInput.blur(); }
    });

    document.addEventListener('click', function (e) {
      if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
        searchResults.classList.remove('active');
      }
    });
  }

  // ── Mobile sidebar ─────────────────────────────────────────────────────────
  var mobileBack = document.getElementById('mobileBack');
  var sidebar = document.getElementById('sidebar');
  if (mobileBack && sidebar) {
    mobileBack.addEventListener('click', function () { sidebar.classList.remove('hidden'); });
  }
  // Hide sidebar when clicking a conversation on mobile
  document.querySelectorAll('.conv-item').forEach(function (item) {
    item.addEventListener('click', function () {
      if (window.innerWidth <= 768 && sidebar) sidebar.classList.add('hidden');
    });
  });

  // ── Lightbox events ────────────────────────────────────────────────────────
  var lightbox = document.getElementById('lightbox');
  var lightboxClose = document.getElementById('lightboxClose');
  if (lightbox) {
    lightbox.addEventListener('click', function (e) {
      if (e.target === lightbox) window.closeLightbox();
    });
  }
  if (lightboxClose) lightboxClose.addEventListener('click', window.closeLightbox);

  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('js-lightbox-trigger')) {
      window.openLightbox(e.target.src);
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') window.closeLightbox();
  });

  // ── Offline retry ──────────────────────────────────────────────────────────
  var retryBtn = document.getElementById('btnRetryOffline');
  if (retryBtn) retryBtn.addEventListener('click', function () { window.location.reload(); });

  // ── PWA Service Worker ─────────────────────────────────────────────────────
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/js/sw.js').catch(function () {});
  }

  // ── PWA Install Prompt ─────────────────────────────────────────────────────
  var deferredPrompt;
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    if (localStorage.getItem('pwaPromptDismissed')) return;
    var banner = document.createElement('button');
    banner.className = 'pwa-install-banner';
    banner.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg> Install App';
    var closeBtn = document.createElement('span');
    closeBtn.className = 'pwa-install-banner__close';
    closeBtn.innerHTML = '✕';
    closeBtn.title = 'Dismiss';
    banner.appendChild(closeBtn);
    document.body.appendChild(banner);

    banner.addEventListener('click', function (ev) {
      if (ev.target === closeBtn || closeBtn.contains(ev.target)) {
        localStorage.setItem('pwaPromptDismissed', 'true');
        banner.remove();
        return;
      }
      if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function () { deferredPrompt = null; banner.remove(); });
      }
    });
  });

  // ── Group Creation Modal ───────────────────────────────────────────────────
  var btnNewGroup = document.getElementById('btnNewGroup');
  var groupModalOverlay = document.getElementById('groupModalOverlay');
  var btnCancelGroup = document.getElementById('btnCancelGroup');
  var groupMemberSearch = document.getElementById('groupMemberSearch');
  var groupMemberResults = document.getElementById('groupMemberResults');
  var groupMemberChips = document.getElementById('groupMemberChips');
  var groupMemberCount = document.getElementById('groupMemberCount');
  var btnCreateGroupSubmit = document.getElementById('btnCreateGroupSubmit');
  var groupNameInput = document.getElementById('group-name');
  
  var selectedGroupMembers = {};
  var groupSearchDebounce;

  if (btnNewGroup && groupModalOverlay) {
    btnNewGroup.addEventListener('click', function () {
      groupModalOverlay.classList.remove('hidden');
      selectedGroupMembers = {};
      updateGroupChips();
      groupNameInput.value = '';
      groupMemberSearch.value = '';
      groupMemberResults.classList.add('hidden');
    });

    btnCancelGroup.addEventListener('click', function () {
      groupModalOverlay.classList.add('hidden');
    });

    function updateGroupChips() {
      var count = 0;
      var html = '';
      for (var id in selectedGroupMembers) {
        count++;
        html += '<div class="member-chip">' + escStr(selectedGroupMembers[id].username) + 
                ' <span class="chip-remove" data-id="' + id + '">✕</span></div>';
      }
      groupMemberChips.innerHTML = html;
      groupMemberCount.textContent = count;
      
      groupMemberChips.querySelectorAll('.chip-remove').forEach(function(btn) {
        btn.addEventListener('click', function() {
          delete selectedGroupMembers[this.dataset.id];
          updateGroupChips();
        });
      });
    }

    groupMemberSearch.addEventListener('input', function () {
      clearTimeout(groupSearchDebounce);
      groupSearchDebounce = setTimeout(function () {
        var q = groupMemberSearch.value.trim();
        if (!q) { groupMemberResults.classList.add('hidden'); return; }
        fetch('/accounts/search/?q=' + encodeURIComponent(q))
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (!data.users || !data.users.length) {
              groupMemberResults.innerHTML = '<div style="padding:0.5rem;color:var(--text-muted)">No users found</div>';
              groupMemberResults.classList.remove('hidden');
              return;
            }
            groupMemberResults.innerHTML = data.users.map(function(u) {
              return '<div class="group-search-item" data-id="' + u.id + '" data-username="' + escStr(u.username) + '">' +
                     '<img src="' + escStr(u.avatar) + '" alt="' + escStr(u.username) + '" width="24" height="24" style="border-radius:50%;margin-right:8px">' +
                     escStr(u.username) + '</div>';
            }).join('');
            groupMemberResults.classList.remove('hidden');

            groupMemberResults.querySelectorAll('.group-search-item').forEach(function(item) {
              item.addEventListener('click', function() {
                selectedGroupMembers[this.dataset.id] = { username: this.dataset.username };
                updateGroupChips();
                groupMemberSearch.value = '';
                groupMemberResults.classList.add('hidden');
              });
            });
          });
      }, 250);
    });

    btnCreateGroupSubmit.addEventListener('click', function () {
      var name = groupNameInput.value.trim();
      if (!name) { window.showToast('Group name is required', 'error'); return; }
      
      var memberIds = Object.keys(selectedGroupMembers);
      
      btnCreateGroupSubmit.disabled = true;
      fetch('/group/create/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ name: name, member_ids: memberIds })
      })
      .then(function(res) {
        if (!res.ok) throw new Error('Failed');
        return res.json();
      })
      .then(function(data) {
        window.location.href = '/conversation/' + data.group_id + '/';
      })
      .catch(function() {
        window.showToast('Failed to create group', 'error');
        btnCreateGroupSubmit.disabled = false;
      });
    });
  }
});
