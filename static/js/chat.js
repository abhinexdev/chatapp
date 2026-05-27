/**
 * static/js/chat.js — Core Real-time Chat Logic
 * Includes: WebSocket, Typing, Presence, File Upload, Reactions, Edits, Replies
 */

document.addEventListener('DOMContentLoaded', function () {
  const chatData = document.getElementById('chatData');
  if (!chatData) return;

  const config = {
    convId: chatData.dataset.conversationId,
    userId: chatData.dataset.currentUserId,
    username: chatData.dataset.currentUsername,
    otherUserId: chatData.dataset.otherUserId,
    isGroup: chatData.dataset.isGroup === 'true',
    csrf: chatData.dataset.csrf,
    uploadUrl: chatData.dataset.uploadUrl,
    messagesUrl: chatData.dataset.messagesUrl,
  };

  const elements = {
    messages: document.getElementById('chatMessages'),
    input: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    typingIndicator: document.getElementById('typingIndicator'),
    typingText: document.getElementById('typingText'),
    fileInput: document.getElementById('fileInput'),
    filePreview: document.getElementById('filePreviewBar'),
    fileInner: document.getElementById('filePreviewInner'),
    clearFile: document.getElementById('clearFile'),
    emojiBtn: document.getElementById('emojiBtn'),
    emojiPicker: document.getElementById('emojiPicker'),
    emojiGrid: document.getElementById('emojiGrid'),
    replyPreview: document.getElementById('reply-preview'),
    loadMoreBtn: document.getElementById('loadMoreBtn'),
    contextMenu: document.getElementById('contextMenu'),
    groupInfoBtn: document.getElementById('groupInfoBtn'),
    groupInfoPanel: document.getElementById('groupInfoPanel'),
    closeGroupInfo: document.getElementById('closeGroupInfo'),
  };

  let socket = null;
  let replyToId = null;
  let isTyping = false;
  let typingTimeout = null;
  let oldestMessageId = null;
  let isLoading = false;

  // ─── WebSocket Connection ──────────────────────────────────────────────────
  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const url = `${protocol}${window.location.host}/ws/chat/${config.convId}/`;
    
    socket = new WebSocket(url);

    socket.onopen = () => console.log('WebSocket Connected');
    
    socket.onmessage = (e) => {
      console.log('WS Message Received:', e.data);
      const data = JSON.parse(e.data);
      handleSocketEvent(data);
    };

    socket.onclose = () => {
      console.log('WebSocket Disconnected. Retrying in 3s...');
      setTimeout(connect, 3000);
    };
  }

  if (config.convId) connect();

  // ─── Event Handling ────────────────────────────────────────────────────────
  function handleSocketEvent(data) {
    switch (data.type) {
      case 'chat_message':
        renderMessage(data, false);
        if (data.sender_id != config.userId) {
          sendReadReceipt([data.id]);
          if (!document.hasFocus()) showBrowserNotification(data);
        }
        scrollToBottom();
        updateSidebar(data);
        break;
      
      case 'typing':
        handleTypingIndicator(data);
        break;
      
      case 'read_receipt':
        updateReadStatus(data);
        break;
      
      case 'presence':
        updatePresence(data);
        break;
      
      case 'message_deleted':
        const msgDelId = data.id || data.message_id;
        const msgElDel = document.querySelector(`[data-message-id="${msgDelId}"]`);
        if (msgElDel) {
          const bubbleDel = msgElDel.querySelector('.message__bubble');
          if (bubbleDel) bubbleDel.innerHTML = '<p class="deleted-message">This message was deleted</p>';
          msgElDel.querySelector('.reaction-bar')?.remove();
          msgElDel.querySelector('.reactions-summary')?.remove();
        }
        break;
      
      case 'message_edited':
        const msgEditId = data.id || data.message_id;
        const bubbleEdit = document.getElementById(`message-content-${msgEditId}`);
        if (bubbleEdit) {
          bubbleEdit.innerHTML = escStr(data.content) + ' <span class="edited-tag">(edited)</span>';
        }
        break;
      
      case 'reaction_update':
        renderReactions(data.id || data.message_id, data.reactions);
        break;
    }
  }

  // ─── Rendering ─────────────────────────────────────────────────────────────
  function renderMessage(msg, prepend = false) {
    if (document.getElementById(`message-${msg.id}`)) return; // Avoid duplicates

    const isOwn = String(msg.sender_id) === String(config.userId);
    const div = document.createElement('div');
    div.className = `message ${isOwn ? 'message--out' : 'message--in'}`;
    div.dataset.messageId = msg.id;
    div.id = `message-${msg.id}`;

    let html = '';
    if (!isOwn) {
      html += `<div class="message__avatar"><img src="${msg.sender_avatar}" alt="${msg.sender_username}"></div>`;
    }

    html += `<div class="message__bubble">`;
    
    if (msg.is_deleted) {
      html += `<p class="deleted-message">This message was deleted</p>`;
    } else {
      // Reply context
      if (msg.reply_to) {
        html += `
          <div class="reply-quote" onclick="document.getElementById('message-${msg.reply_to.id}')?.scrollIntoView({behavior:'smooth'})">
            <strong>${escStr(msg.reply_to.sender_username)}</strong>
            <p>${escStr(msg.reply_to.content)}</p>
          </div>
        `;
      }

      // Attachment
      if (msg.attachment) {
        if (msg.attachment.is_image) {
          html += `<div class="message__image-wrap"><img src="${msg.attachment.file_url}" class="message__image js-lightbox-trigger"></div>`;
        } else {
          html += `
            <div class="message__file">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/></svg>
              <div><span class="file-name">${escStr(msg.attachment.original_name)}</span><span class="file-size">${msg.attachment.file_size}</span></div>
              <a href="${msg.attachment.file_url}" download class="file-dl">↓</a>
            </div>
          `;
        }
      }

      // Content
      if (msg.content) {
        html += `<p class="message__text" id="message-content-${msg.id}">${escStr(msg.content)}${msg.edited_at ? ' <span class="edited-tag">(edited)</span>' : ''}</p>`;
      }
    }

    // Meta
    html += `
      <div class="message__meta">
        <span class="message__time">${formatTime(msg.timestamp)}</span>
        ${isOwn ? `<span class="message__status" data-msg-id="${msg.id}">${renderStatusIcon(msg.status)}</span>` : ''}
      </div>
    `;

    // Reaction Bar
    if (!msg.is_deleted) {
      html += `
        <div class="reaction-bar">
          ${['👍', '❤️', '😂', '😮', '😢', '🔥'].map(e => `<span onclick="window.reactMessage(${msg.id}, '${e}')">${e}</span>`).join('')}
        </div>
        <div class="reactions-summary" id="reactions-${msg.id}"></div>
      `;
    }

    html += `</div>`;
    div.innerHTML = html;

    if (prepend) {
      elements.messages.insertBefore(div, elements.messages.firstChild.nextSibling);
    } else {
      elements.messages.appendChild(div);
    }

    if (msg.reactions) renderReactions(msg.id, msg.reactions);

    // Right click menu
    div.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      showContextMenu(e.clientX, e.clientY, msg.id, msg.content, !isOwn);
    });
  }

  function renderStatusIcon(status) {
    if (status === 'read') return '<svg class="status-icon status-icon--read" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 9l3 3 8-8M5 9l3 3 8-8"/></svg>';
    if (status === 'delivered') return '<svg class="status-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 9l3 3 8-8M5 9l3 3 8-8"/></svg>';
    return '<svg class="status-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 9l4 4 8-8"/></svg>';
  }

  function formatTime(ts) {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function escStr(s) {
    if (!s) return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  // ─── Input & Typing ────────────────────────────────────────────────────────
  function sendMessage() {
    const content = elements.input.value.trim();
    if (!content && !elements.fileInput.files[0]) return;

    if (elements.fileInput.files[0]) {
      handleFileUpload();
      return;
    }

    socket.send(JSON.stringify({
      type: 'chat_message',
      content: content,
      reply_to: replyToId
    }));

    elements.input.value = '';
    elements.input.style.height = 'auto';
    cancelReply();
    stopTyping();
  }

  elements.sendBtn.addEventListener('click', sendMessage);
  elements.input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  elements.input.addEventListener('input', () => {
    elements.input.style.height = 'auto';
    elements.input.style.height = elements.input.scrollHeight + 'px';
    
    if (!isTyping) {
      isTyping = true;
      socket.send(JSON.stringify({ type: 'typing', is_typing: true }));
    }
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(stopTyping, 2000);
  });

  function stopTyping() {
    isTyping = false;
    socket.send(JSON.stringify({ type: 'typing', is_typing: false }));
  }

  // ─── File Upload ───────────────────────────────────────────────────────────
  elements.fileInput.addEventListener('change', () => {
    const file = elements.fileInput.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { window.showToast('File too large (max 10MB)', 'error'); elements.fileInput.value = ''; return; }
    elements.filePreview.classList.remove('hidden');
    if (file.type.startsWith('image/')) {
      elements.fileInner.innerHTML = `<img src="${URL.createObjectURL(file)}"><span>${escStr(file.name)}</span>`;
    } else {
      elements.fileInner.innerHTML = `<div class="file-preview-icon">📎</div><span>${escStr(file.name)}</span>`;
    }
  });

  elements.clearFile.addEventListener('click', () => {
    elements.fileInput.value = '';
    elements.filePreview.classList.add('hidden');
  });

  async function handleFileUpload() {
    const formData = new FormData();
    formData.append('file', elements.fileInput.files[0]);
    if (replyToId) formData.append('reply_to', replyToId);
    
    elements.sendBtn.disabled = true;
    try {
      const resp = await fetch(config.uploadUrl, {
        method: 'POST',
        headers: { 'X-CSRFToken': config.csrf },
        body: formData
      });
      if (!resp.ok) throw new Error();
      elements.fileInput.value = '';
      elements.filePreview.classList.add('hidden');
      cancelReply();
    } catch (err) {
      window.showToast('Upload failed', 'error');
    } finally {
      elements.sendBtn.disabled = false;
    }
  }

  // ─── Emoji Picker ──────────────────────────────────────────────────────────
  const emojis = ['😀','😃','😄','😁','😆','😅','😂','🤣','😊','😇','🙂','🙃','😉','😌','😍','🥰','😘','😗','😙','😚','😋','😛','😝','😜','🤪','🤨','🧐','🤓','😎','🤩','🥳','😏','😒','😞','😔','😟','😕','🙁','☹️','😣','😖','😫','😩','🥺','😢','😭','😤','😠','😡','🤬','🤯','😳','🥵','🥶','😱','😨','😰','😥','😓','🤗','🤔','🤭','🤫','🤥','😶','😐','😑','😬','🙄','😯','😦','😧','😮','😲','🥱','😴','🤤','😪','😵','🤐','🥴','🤢','🤮','🤧','🤨','🧐','🤠','🤡','🥳','🥴','🥵','🥶','🥺','🤢','🤮','🤧','🥵','🥶','🥺','👍','👎','👌','🤝','🙏','🔥','❤️','✨'];
  elements.emojiGrid.innerHTML = emojis.map(e => `<button type="button" class="emoji-btn-item">${e}</button>`).join('');
  elements.emojiBtn.addEventListener('click', (e) => { e.stopPropagation(); elements.emojiPicker.classList.toggle('open'); });
  elements.emojiGrid.addEventListener('click', (e) => {
    if (e.target.classList.contains('emoji-btn-item')) {
      const pos = elements.input.selectionStart;
      const text = elements.input.value;
      elements.input.value = text.slice(0, pos) + e.target.textContent + text.slice(pos);
      elements.input.focus();
      elements.input.selectionStart = elements.input.selectionEnd = pos + e.target.textContent.length;
      elements.emojiPicker.classList.remove('open');
    }
  });
  document.addEventListener('click', () => elements.emojiPicker.classList.remove('open'));

  // ─── Read Receipts ─────────────────────────────────────────────────────────
  function sendReadReceipt(messageIds) {
    if (!socket || socket.readyState !== WebSocket.OPEN || config.isGroup) return;
    socket.send(JSON.stringify({ type: 'read_receipt', message_ids: messageIds }));
  }

  function updateReadStatus(data) {
    data.message_ids.forEach(id => {
      const statusEl = document.querySelector(`.message__status[data-msg-id="${id}"]`);
      if (statusEl) statusEl.innerHTML = renderStatusIcon('read');
    });
  }

  // ─── Context Menu & Actions ───────────────────────────────────────────────
  function showContextMenu(clientX, clientY, msgId, content, replyOnly = false) {
    activeCtxMsgId = msgId;
    const menuWidth = 160;
    const menuHeight = elements.contextMenu.offsetHeight || 120;
    const posX = (clientX + menuWidth > window.innerWidth) ? clientX - menuWidth : clientX;
    const posY = (clientY + menuHeight > window.innerHeight) ? clientY - menuHeight : clientY;

    elements.contextMenu.style.left = `${posX}px`;
    elements.contextMenu.style.top = `${posY}px`;
    elements.contextMenu.classList.remove('hidden');

    const editBtn = document.getElementById('ctxEdit');
    const delBtn = document.getElementById('ctxDelete');
    if (replyOnly) { editBtn?.classList.add('hidden'); delBtn?.classList.add('hidden'); }
    else { editBtn?.classList.remove('hidden'); delBtn?.classList.remove('hidden'); }
  }

  document.addEventListener('click', () => elements.contextMenu.classList.add('hidden'));

  document.getElementById('ctxReply').addEventListener('click', () => {
    const msgEl = document.querySelector(`[data-message-id="${activeCtxMsgId}"]`);
    if (!msgEl) return;
    const content = msgEl.querySelector('.message__text')?.textContent || 'Attachment';
    const sender = msgEl.classList.contains('message--out') ? 'You' : (document.getElementById('headerUsername')?.textContent || 'User');
    initReply(activeCtxMsgId, content, sender);
  });

  document.getElementById('ctxEdit').addEventListener('click', () => {
    const msgEl = document.querySelector(`[data-message-id="${activeCtxMsgId}"]`);
    if (!msgEl) return;
    const textEl = msgEl.querySelector('.message__text');
    if (!textEl) return;
    const text = textEl.textContent.replace('(edited)', '').trim();
    initEdit(activeCtxMsgId, text);
  });

  document.getElementById('ctxDelete').addEventListener('click', async () => {
    if (!confirm('Delete this message?')) return;
    const resp = await fetch(`/api/message/${activeCtxMsgId}/delete/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': config.csrf }
    });
    if (resp.ok) window.showToast('Message deleted');
  });

  function initReply(id, content, sender) {
    replyToId = id;
    elements.replyPreview.classList.remove('hidden');
    elements.replyPreview.querySelector('.reply-content').innerHTML = `<strong>${escStr(sender)}</strong><p>${escStr(content)}</p>`;
    elements.input.focus();
  }

  window.cancelReply = () => { replyToId = null; elements.replyPreview.classList.add('hidden'); };

  function initEdit(id, text) {
    const bubble = document.getElementById(`message-content-${id}`);
    if (!bubble) return;
    const originalHTML = bubble.innerHTML;
    bubble.innerHTML = `
      <textarea class="edit-textarea">${text}</textarea>
      <div class="edit-actions">
        <button class="btn-save">Save</button>
        <button class="btn-cancel">Cancel</button>
      </div>
    `;
    const textarea = bubble.querySelector('textarea');
    textarea.focus();
    bubble.querySelector('.btn-cancel').onclick = () => { bubble.innerHTML = originalHTML; };
    bubble.querySelector('.btn-save').onclick = async () => {
      const newContent = textarea.value.trim();
      if (!newContent) return;
      const resp = await fetch(`/api/message/${id}/edit/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': config.csrf, 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: newContent })
      });
      if (resp.ok) { /* Update handled by WebSocket */ }
      else { window.showToast('Edit failed', 'error'); bubble.innerHTML = originalHTML; }
    };
  }

  // ─── Reactions ─────────────────────────────────────────────────────────────
  window.reactMessage = async (id, emoji) => {
    const resp = await fetch(`/api/message/${id}/react/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': config.csrf, 'Content-Type': 'application/json' },
      body: JSON.stringify({ emoji })
    });
  };

  function renderReactions(msgId, reactions) {
    const el = document.getElementById(`reactions-${msgId}`);
    if (!el) return;
    if (!reactions || reactions.length === 0) { el.innerHTML = ''; return; }
    el.innerHTML = reactions.map(r => `<span class="reaction-badge">${r.emoji} ${r.count}</span>`).join('');
  }

  // ─── Presence & Typing ──────────────────────────────────────────────────────
  function handleTypingIndicator(data) {
    if (data.user_id == config.userId) return;
    if (data.is_typing) {
      elements.typingText.textContent = `${data.username} is typing...`;
      elements.typingIndicator.classList.remove('hidden');
    } else {
      elements.typingIndicator.classList.add('hidden');
    }
  }

  function updatePresence(data) {
    const statusDot = document.querySelector(`.user-status-dot[data-user-id="${data.user_id}"]`);
    if (statusDot) {
      statusDot.className = `user-status-dot ${data.status === 'online' ? 'online' : 'offline'}`;
    }
  }

  // ─── Messages Loading ──────────────────────────────────────────────────────
  async function loadMessages(beforeId = null) {
    if (isLoading) return;
    isLoading = true;
    const url = beforeId ? `${config.messagesUrl}?before=${beforeId}` : config.messagesUrl;
    const resp = await fetch(url);
    const data = await resp.json();
    
    if (data.messages.length > 0) {
      oldestMessageId = data.messages[0].id;
      data.messages.forEach(m => renderMessage(m, true));
      if (!beforeId) scrollToBottom();
    }
    
    if (data.messages.length < 30) elements.loadMoreBtn?.classList.add('hidden');
    isLoading = false;
  }

  elements.loadMoreBtn?.addEventListener('click', () => loadMessages(oldestMessageId));

  function scrollToBottom() {
    elements.messages.scrollTop = elements.messages.scrollHeight;
  }

  function updateSidebar(msg) {
    const item = document.querySelector(`.sidebar-item[data-conv-id="${config.convId}"]`);
    if (item) {
      item.querySelector('.sidebar-item__message').textContent = msg.content || 'Attachment';
      item.querySelector('.sidebar-item__time').textContent = formatTime(msg.timestamp);
      // Move to top
      item.parentElement.prepend(item);
    }
  }

  // ─── Group Info Panel ──────────────────────────────────────────────────────
  if (elements.groupInfoBtn) {
    elements.groupInfoBtn.addEventListener('click', async () => {
      elements.groupInfoPanel.classList.toggle('hidden');
      if (!elements.groupInfoPanel.classList.contains('hidden')) {
        const resp = await fetch(`/group/${config.convId}/members/`);
        const data = await resp.json();
        const listEl = document.getElementById('groupInfoMembers');
        listEl.innerHTML = data.members.map(m => `
          <div class="group-info-member">
            <img src="${m.avatar}">
            <span>${m.username}</span>
            ${m.is_admin ? '<span class="admin-badge">Admin</span>' : ''}
          </div>
        `).join('');
      }
    });
  }

  elements.closeGroupInfo?.addEventListener('click', () => elements.groupInfoPanel.classList.add('hidden'));

  // ─── Utilities ─────────────────────────────────────────────────────────────
  loadMessages();
  if (Notification.permission === 'default') Notification.requestPermission();
  function showBrowserNotification(data) {
    if (Notification.permission === 'granted') {
      new Notification(`New message from ${data.sender_username}`, {
        body: data.content || (data.message_type === 'image' ? 'Sent a photo' : 'Sent a file'),
        icon: data.sender_avatar
      });
    }
  }
});
