/**
 * TravelAI Copilot & Smart Features Client
 * Handles Chatbot, Itinerary Generator, Auto-Cost Estimator, Budget Optimizer & Receipt Scanner
 */

const TravelAI = (function() {
  let isChatOpen = false;
  let chatHistory = [];
  let isLiveAI = false;

  // Initialize on DOM Ready
  function init() {
    createFloatingAssistant();
    checkAIStatus();
    setupPageIntegration();
  }

  // 1. Check AI Status from Backend
  async function checkAIStatus() {
    try {
      const res = await fetch('/api/ai/status');
      const data = await res.json();
      isLiveAI = data.configured;
      updateStatusBadge(isLiveAI);
    } catch (e) {
      console.warn("AI status check failed:", e);
    }
  }

  function updateStatusBadge(live) {
    const badge = document.getElementById('ai_status_indicator');
    if (!badge) return;
    if (live) {
      badge.innerHTML = '<span style="color:#34d399">●</span> Google Gemini Live';
      badge.title = "Connected to Google Gemini API";
    } else {
      badge.innerHTML = '<span style="color:#fbbf24">●</span> Demo AI (Click ⚙️ to add Key)';
      badge.title = "Running in Demo Mode. Click settings gear to add your free Google Gemini API Key";
    }
  }

  // 2. Render Floating Assistant Elements
  function createFloatingAssistant() {
    if (document.getElementById('ai_floating_trigger')) return;

    // Trigger button
    const trigger = document.createElement('button');
    trigger.id = 'ai_floating_trigger';
    trigger.className = 'ai-floating-trigger';
    trigger.type = 'button';
    trigger.innerHTML = `
      <span class="ai-pulse-dot"></span>
      <span>🤖 TravelAI</span>
    `;
    trigger.onclick = toggleChat;

    // Chat Drawer
    const drawer = document.createElement('div');
    drawer.id = 'ai_chat_window';
    drawer.className = 'ai-chat-window minimized';
    drawer.innerHTML = `
      <div class="ai-chat-header">
        <div class="ai-chat-header-info">
          <div class="ai-chat-avatar">✨</div>
          <div>
            <h3>TravelAI Copilot</h3>
            <div class="ai-chat-status" id="ai_status_indicator">
              <span style="color:#fbbf24">●</span> Checking status...
            </div>
          </div>
        </div>
        <div class="ai-chat-controls">
          <button type="button" class="ai-chat-ctrl-btn" onclick="TravelAI.openKeyModal()" title="AI Settings / API Key">⚙️</button>
          <button type="button" class="ai-chat-ctrl-btn" onclick="TravelAI.toggleChat()" title="Close Chat">✕</button>
        </div>
      </div>

      <div class="ai-context-banner" id="ai_context_banner">
        <span>📍 Trip Assistant</span>
        <span class="ai-context-pill" id="ai_context_destination">General Travel</span>
      </div>

      <div class="ai-chat-messages" id="ai_chat_messages">
        <div class="ai-msg ai-msg-assistant">
          Hello! 👋 I'm your <strong>TravelAI Copilot</strong> powered by Google Gemini.
          <br><br>
          Ask me anything about destination sights, packing checklists, hidden gems, local foods, or ways to cut down your trip costs!
        </div>
      </div>

      <div class="ai-quick-chips">
        <button type="button" class="ai-chip" onclick="TravelAI.sendQuickPrompt('What are the top local foods and dishes to try?')">🍛 Local Food</button>
        <button type="button" class="ai-chip" onclick="TravelAI.sendQuickPrompt('Give me a smart packing checklist for this journey.')">🎒 Packing List</button>
        <button type="button" class="ai-chip" onclick="TravelAI.sendQuickPrompt('How can I save money on this trip?')">💡 Save Money</button>
        <button type="button" class="ai-chip" onclick="TravelAI.sendQuickPrompt('Suggest a smart 3-day itinerary with timings.')">🗺️ 3-Day Plan</button>
      </div>

      <div class="ai-chat-input-bar">
        <input type="text" id="ai_chat_input" class="ai-chat-input" placeholder="Ask about places, food, budget..." onkeydown="if(event.key==='Enter') TravelAI.sendMessage()">
        <button type="button" class="ai-chat-send" onclick="TravelAI.sendMessage()" id="ai_chat_send_btn">➤</button>
      </div>
    `;

    document.body.appendChild(trigger);
    document.body.appendChild(drawer);
  }

  function toggleChat() {
    const drawer = document.getElementById('ai_chat_window');
    if (!drawer) return;
    isChatOpen = !isChatOpen;
    if (isChatOpen) {
      drawer.classList.remove('minimized');
      syncTripContext();
      const input = document.getElementById('ai_chat_input');
      if (input) setTimeout(() => input.focus(), 200);
    } else {
      drawer.classList.add('minimized');
    }
  }

  // 3. Extract Context from current page (Planner or Results)
  function getTripContext() {
    let origin = document.getElementById('from_location')?.value || '';
    let destination = document.getElementById('destination')?.value || '';
    let travelers = document.getElementById('travelers')?.value || '1';
    let transport = document.getElementById('transport_mode')?.value || 'car';
    
    // Check if on result page
    const reportHero = document.querySelector('.report-hero h1');
    if (reportHero && reportHero.textContent) {
      destination = reportHero.textContent.trim();
    }
    const metaRoute = document.querySelector('.hero-meta span');
    if (metaRoute && metaRoute.textContent && metaRoute.textContent.includes('→')) {
      const parts = metaRoute.textContent.split('→');
      origin = parts[0].trim();
    }

    return {
      origin: origin || 'My Location',
      destination: destination || 'Travel Destination',
      travelers: travelers,
      transport_mode: transport
    };
  }

  function syncTripContext() {
    const ctx = getTripContext();
    const destPill = document.getElementById('ai_context_destination');
    if (destPill) {
      destPill.textContent = ctx.destination.split(',')[0] || 'General Travel';
    }
  }

  // 4. Send Chat Message
  async function sendMessage() {
    const input = document.getElementById('ai_chat_input');
    const sendBtn = document.getElementById('ai_chat_send_btn');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    appendMessage(text, 'user');

    if (sendBtn) {
      sendBtn.disabled = true;
      sendBtn.innerHTML = '<span class="ai-spinner"></span>';
    }

    // Add typing placeholder
    const typingId = 'typing_' + Date.now();
    appendMessage('<span style="display:inline-flex;gap:4px;"><span class="ai-pulse-dot" style="width:6px;height:6px"></span> Thinking...</span>', 'assistant', typingId);

    try {
      const ctx = getTripContext();
      const res = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          history: chatHistory,
          trip_context: ctx
        })
      });

      const data = await res.json();
      removeElement(typingId);

      if (data.reply) {
        appendMessage(formatMarkdown(data.reply), 'assistant');
        chatHistory.push({ role: 'user', text: text });
        chatHistory.push({ role: 'assistant', text: data.reply });
      } else {
        appendMessage("I couldn't process that right now. Please try again!", 'assistant');
      }
    } catch (err) {
      removeElement(typingId);
      appendMessage("Network error communicating with AI server.", 'assistant');
    } finally {
      if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.innerHTML = '➤';
      }
    }
  }

  function sendQuickPrompt(promptText) {
    const input = document.getElementById('ai_chat_input');
    if (input) {
      input.value = promptText;
      sendMessage();
    }
  }

  function appendMessage(htmlContent, sender, id = null) {
    const container = document.getElementById('ai_chat_messages');
    if (!container) return;
    const msg = document.createElement('div');
    msg.className = `ai-msg ai-msg-${sender}`;
    if (id) msg.id = id;
    msg.innerHTML = htmlContent;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
  }

  function removeElement(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function formatMarkdown(text) {
    if (!text) return '';
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n\n/g, '<br><br>')
      .replace(/\n- (.*?)/g, '<br>• $1')
      .replace(/\n\d+\. (.*?)/g, '<br>• $1');
  }

  // 5. Open AI Settings / API Key Modal
  function openKeyModal() {
    let modal = document.getElementById('ai_key_modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'ai_key_modal';
      modal.className = 'ai-modal-backdrop';
      modal.innerHTML = `
        <div class="ai-modal-card" style="width: 480px;">
          <div class="ai-modal-header">
            <h2>🔑 Google Gemini AI Settings</h2>
            <button type="button" class="ai-modal-close" onclick="TravelAI.closeKeyModal()">✕</button>
          </div>
          <div class="ai-modal-body">
            <p style="font-size:0.9rem; color:#475569; margin-top:0;">
              Connect your <strong>Google Gemini API Key</strong> to activate live AI generation for itineraries, expense vision OCR, cost estimation, and trip copilot.
            </p>
            <div class="ai-key-input-box">
              <label style="font-weight:700; font-size:0.85rem; color:#0f172a;">Gemini API Key</label>
              <input type="password" id="gemini_api_key_input" placeholder="AIzaSy..." autocomplete="off">
              <small style="display:block; margin-top:6px; color:#64748b; font-size:0.78rem;">
                Get a free key from <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener" style="color:#0d9488; font-weight:600;">Google AI Studio ↗</a>
              </small>
            </div>
            <div id="ai_key_feedback" style="display:none; font-size:0.85rem; padding:10px; border-radius:8px; margin-bottom:14px;"></div>
            <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
              <button type="button" class="ai-magic-btn secondary" onclick="TravelAI.clearKey()">Clear Key (Demo Mode)</button>
              <button type="button" class="ai-magic-btn" id="ai_save_key_btn" onclick="TravelAI.saveKey()">Save & Test Connection</button>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
    }
    modal.style.display = 'flex';
  }

  function closeKeyModal() {
    const modal = document.getElementById('ai_key_modal');
    if (modal) modal.style.display = 'none';
  }

  async function saveKey() {
    const input = document.getElementById('gemini_api_key_input');
    const feedback = document.getElementById('ai_key_feedback');
    const saveBtn = document.getElementById('ai_save_key_btn');
    const key = (input ? input.value : '').trim();

    if (!key) {
      if (feedback) {
        feedback.style.display = 'block';
        feedback.style.background = '#fef2f2';
        feedback.style.color = '#991b1b';
        feedback.textContent = 'Please paste your Gemini API key, or click Clear Key for demo mode.';
      }
      return;
    }

    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="ai-spinner"></span> Connecting...';
    }

    try {
      const res = await fetch('/api/ai/set_key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: key })
      });
      const data = await res.json();

      if (feedback) feedback.style.display = 'block';

      if (data.success) {
        feedback.style.background = '#ecfdf5';
        feedback.style.color = '#065f46';
        feedback.textContent = '✓ ' + data.message;
        isLiveAI = true;
        updateStatusBadge(true);
        setTimeout(closeKeyModal, 1500);
      } else {
        feedback.style.background = '#fef2f2';
        feedback.style.color = '#991b1b';
        feedback.textContent = '✕ ' + (data.message || 'Invalid Gemini key.');
      }
    } catch (e) {
      if (feedback) {
        feedback.style.display = 'block';
        feedback.style.background = '#fef2f2';
        feedback.style.color = '#991b1b';
        feedback.textContent = 'Error connecting to server.';
      }
    } finally {
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = 'Save & Test Connection';
      }
    }
  }

  async function clearKey() {
    try {
      await fetch('/api/ai/set_key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: '' })
      });
      isLiveAI = false;
      updateStatusBadge(false);
      const input = document.getElementById('gemini_api_key_input');
      if (input) input.value = '';
      closeKeyModal();
    } catch (e) {
      console.warn(e);
    }
  }

  // 6. Smart Budget Auto-Estimator (For Planner Step 3)
  async function autoEstimateBudget() {
    const destInput = document.getElementById('destination');
    const originInput = document.getElementById('from_location');
    const travelersInput = document.getElementById('travelers');
    const transportInput = document.getElementById('transport_mode');

    const destination = destInput ? destInput.value.trim() : '';
    if (!destination) {
      alert('Please enter a destination in Step 2 first to estimate costs!');
      if (typeof window.changeStep === 'function') window.changeStep(-1);
      return;
    }

    const btn = document.getElementById('ai_estimate_btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="ai-spinner"></span> Estimating with AI...';
    }

    try {
      const res = await fetch('/api/ai/estimate_budget', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          destination: destination,
          origin: originInput ? originInput.value : 'Bengaluru',
          travelers: parseInt(travelersInput?.value || 1, 10),
          days: 2,
          transport_mode: transportInput?.value || 'car'
        })
      });

      const data = await res.json();

      // Populate form fields
      const roomInput = document.getElementById('room_cost');
      const foodInput = document.getElementById('food_cost');
      const tollInput = document.getElementById('toll_charges');

      if (roomInput && data.room_cost_per_night) {
        roomInput.value = data.room_cost_per_night;
        highlightField(roomInput);
      }
      if (foodInput && data.food_cost_per_person_per_day) {
        foodInput.value = data.food_cost_per_person_per_day;
        highlightField(foodInput);
      }
      if (tollInput && data.estimated_tolls_total !== undefined && tollInput.closest('.field-group').style.display !== 'none') {
        tollInput.value = data.estimated_tolls_total;
        highlightField(tollInput);
      }

      showToast(`✨ AI Cost Estimate applied for ${destination.split(',')[0]}! (${data.tier_category})`);
    } catch (err) {
      alert('Could not retrieve AI estimate. Please input amounts manually.');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '✨ Auto-Estimate Costs with AI';
      }
    }
  }

  function highlightField(el) {
    el.style.transition = 'all 0.5s';
    el.style.backgroundColor = '#ecfdf5';
    el.style.borderColor = '#10b981';
    setTimeout(() => {
      el.style.backgroundColor = '';
      el.style.borderColor = '';
    }, 1500);
  }

  function showToast(msg) {
    let toast = document.getElementById('ai_toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'ai_toast';
      toast.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#0f172a;color:#fff;padding:12px 24px;border-radius:999px;font-size:0.9rem;font-weight:600;z-index:99999;box-shadow:0 10px 25px rgba(0,0,0,0.2);display:flex;align-items:center;gap:8px;';
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.display = 'flex';
    setTimeout(() => { toast.style.display = 'none'; }, 3500);
  }

  // 7. Full Itinerary Generator Modal
  async function openItineraryModal(destParam = null, originParam = null) {
    const ctx = getTripContext();
    const destination = destParam || ctx.destination;
    const origin = originParam || ctx.origin;

    let modal = document.getElementById('ai_itinerary_modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'ai_itinerary_modal';
      modal.className = 'ai-modal-backdrop';
      document.body.appendChild(modal);
    }

    modal.innerHTML = `
      <div class="ai-modal-card">
        <div class="ai-modal-header">
          <h2>✨ AI Smart Itinerary · ${destination.split(',')[0]}</h2>
          <button type="button" class="ai-modal-close" onclick="document.getElementById('ai_itinerary_modal').style.display='none'">✕</button>
        </div>
        <div class="ai-modal-body" id="ai_itinerary_content">
          <div style="text-align:center; padding:40px;">
            <div class="ai-spinner" style="width:36px; height:36px; border-width:3px; border-top-color:#0d9488;"></div>
            <p style="margin-top:16px; color:#64748b; font-weight:600;">Generating tailored day-by-day itinerary with sights, timings & food spots...</p>
          </div>
        </div>
      </div>
    `;
    modal.style.display = 'flex';

    try {
      const res = await fetch('/api/ai/itinerary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          destination: destination,
          origin: origin,
          days: 3,
          travel_style: 'Balanced, Sightseeing & Culture',
          travelers: parseInt(ctx.travelers || 1, 10)
        })
      });

      const data = await res.json();
      renderItineraryContent(data);
    } catch (e) {
      document.getElementById('ai_itinerary_content').innerHTML = `
        <div style="text-align:center; padding:30px; color:#ef4444;">
          <p>Failed to generate itinerary. Please try again later.</p>
        </div>
      `;
    }
  }

  function renderItineraryContent(data) {
    const container = document.getElementById('ai_itinerary_content');
    if (!container) return;

    let daysHtml = '';
    (data.days || []).forEach(d => {
      daysHtml += `
        <div class="ai-day-card">
          <div class="ai-day-header">
            <h4>${d.title || ('Day ' + d.day_number)}</h4>
            ${d.daily_spend_estimate ? `<span class="ai-day-spend">Est. ${d.daily_spend_estimate}</span>` : ''}
          </div>
          <div class="ai-timeline-item">
            <span class="ai-time-tag">🌅 Morning</span>
            <div>${d.morning}</div>
          </div>
          <div class="ai-timeline-item">
            <span class="ai-time-tag">☀️ Afternoon</span>
            <div>${d.afternoon}</div>
          </div>
          <div class="ai-timeline-item">
            <span class="ai-time-tag">🌆 Evening</span>
            <div>${d.evening}</div>
          </div>
          ${d.meal_recommendation ? `
            <div style="margin-top:10px; padding:8px 12px; background:#fffbeb; border-radius:8px; font-size:0.83rem; color:#92400e;">
              <strong>🍽️ Food Recommendation:</strong> ${d.meal_recommendation}
            </div>
          ` : ''}
        </div>
      `;
    });

    let gemsHtml = '';
    (data.hidden_gems || []).forEach(g => {
      gemsHtml += `
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:12px; margin-bottom:8px;">
          <strong style="color:#0f172a; font-size:0.92rem;">💎 ${g.name}</strong>
          <p style="margin:4px 0 0; font-size:0.82rem; color:#64748b;">${g.why_visit} <em>(${g.entry_tip || ''})</em></p>
        </div>
      `;
    });

    container.innerHTML = `
      <div style="margin-bottom:20px;">
        <span style="font-size:0.8rem; background:#ecfdf5; color:#065f46; padding:3px 10px; border-radius:999px; font-weight:700;">
          ${data.best_season || 'Great all year'} · ${data.ideal_duration || '3 Days'}
        </span>
        <h3 style="margin:8px 0 4px; font-size:1.15rem; color:#0f172a;">${data.tagline || ''}</h3>
        <p style="margin:0; font-size:0.85rem; color:#64748b;">${data.weather_advice || ''}</p>
      </div>

      <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:20px;">
        ${(data.packing_essentials || []).map(p => `
          <span style="background:#f1f5f9; color:#334155; padding:4px 10px; border-radius:6px; font-size:0.78rem; font-weight:600;">
            ✓ ${p}
          </span>
        `).join('')}
      </div>

      <h3 style="font-size:1rem; margin:20px 0 12px; color:#0f172a;">📅 Daily Itinerary</h3>
      ${daysHtml}

      ${gemsHtml ? `
        <h3 style="font-size:1rem; margin:24px 0 10px; color:#0f172a;">✨ Hidden Gems</h3>
        ${gemsHtml}
      ` : ''}
    `;
  }

  // 8. AI Receipt Scanner Modal
  function openReceiptModal() {
    let modal = document.getElementById('ai_receipt_modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'ai_receipt_modal';
      modal.className = 'ai-modal-backdrop';
      modal.innerHTML = `
        <div class="ai-modal-card" style="width: 520px;">
          <div class="ai-modal-header">
            <h2>📷 AI Receipt & Bill Scanner</h2>
            <button type="button" class="ai-modal-close" onclick="document.getElementById('ai_receipt_modal').style.display='none'">✕</button>
          </div>
          <div class="ai-modal-body">
            <p style="font-size:0.88rem; color:#475569; margin-top:0;">
              Upload an image of your fuel chit, restaurant bill, hotel invoice, or toll slip. Gemini Vision will extract amounts and details automatically.
            </p>

            <div class="ai-receipt-upload-zone" id="ai_receipt_dropzone" onclick="document.getElementById('ai_receipt_file').click()">
              <input type="file" id="ai_receipt_file" accept="image/*" style="display:none" onchange="TravelAI.handleReceiptUpload(event)">
              <div style="font-size:36px; margin-bottom:10px;">🧾</div>
              <strong style="color:#0f172a;">Click to browse or drop bill image here</strong>
              <p style="font-size:0.8rem; color:#94a3b8; margin:6px 0 0;">Supports JPG, PNG, WEBP</p>
            </div>

            <img id="ai_receipt_preview_img" class="ai-receipt-preview" style="display:none;" alt="Receipt Preview">

            <div id="ai_receipt_result" style="display:none; margin-top:16px;"></div>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
    }
    modal.style.display = 'flex';
  }

  async function handleReceiptUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const preview = document.getElementById('ai_receipt_preview_img');
    const resultBox = document.getElementById('ai_receipt_result');

    const reader = new FileReader();
    reader.onload = async function(e) {
      preview.src = e.target.result;
      preview.style.display = 'block';

      resultBox.style.display = 'block';
      resultBox.innerHTML = `
        <div style="text-align:center; padding:16px;">
          <div class="ai-spinner" style="border-top-color:#0d9488"></div>
          <p style="font-size:0.85rem; color:#64748b; margin-top:8px;">Scanning receipt with Gemini Vision OCR...</p>
        </div>
      `;

      try {
        const formData = new FormData();
        formData.append('receipt_image', file);

        const res = await fetch('/api/ai/scan_receipt', {
          method: 'POST',
          body: formData
        });

        const data = await res.json();
        renderReceiptResult(data);
      } catch (err) {
        resultBox.innerHTML = '<p style="color:#ef4444; font-size:0.85rem;">Failed to scan receipt image. Please try another image.</p>';
      }
    };
    reader.readAsDataURL(file);
  }

  function renderReceiptResult(data) {
    const resultBox = document.getElementById('ai_receipt_result');
    if (!resultBox) return;

    resultBox.innerHTML = `
      <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:16px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
          <div>
            <strong style="font-size:1.05rem; color:#0f172a; display:block;">${data.vendor_name || 'Travel Receipt'}</strong>
            <span style="font-size:0.78rem; color:#64748b;">${data.date || 'Recent'} · Category: <strong>${data.category || 'General'}</strong></span>
          </div>
          <div style="text-align:right;">
            <span style="font-size:1.2rem; font-weight:800; color:#0d9488;">₹${(data.total_amount || 0).toFixed(2)}</span>
            ${data.tax_amount ? `<small style="display:block; font-size:0.72rem; color:#94a3b8;">Tax: ₹${data.tax_amount}</small>` : ''}
          </div>
        </div>

        ${(data.items && data.items.length) ? `
          <div style="margin:10px 0; border-top:1px dashed #cbd5e1; padding-top:8px;">
            ${data.items.map(it => `
              <div style="display:flex; justify-content:space-between; font-size:0.82rem; margin-bottom:4px;">
                <span>${it.description}</span>
                <strong>₹${(it.amount || 0).toFixed(2)}</strong>
              </div>
            `).join('')}
          </div>
        ` : ''}

        ${data.notes ? `<p style="font-size:0.78rem; color:#64748b; margin:8px 0 12px; font-style:italic;">${data.notes}</p>` : ''}

        <button type="button" class="ai-magic-btn" style="width:100%; justify-content:center;" onclick="TravelAI.applyScannedExpense(${data.total_amount || 0}, '${data.category || 'Food'}')">
          ✓ Apply ₹${(data.total_amount || 0).toFixed(2)} to ${data.category || 'Expense'}
        </button>
      </div>
    `;
  }

  function applyScannedExpense(amount, category) {
    const catLower = (category || '').toLowerCase();
    let targetInput = null;

    if (catLower.includes('fuel')) targetInput = document.getElementById('transport_cost');
    else if (catLower.includes('food') || catLower.includes('meal')) targetInput = document.getElementById('food_cost');
    else if (catLower.includes('room') || catLower.includes('hotel') || catLower.includes('stay')) targetInput = document.getElementById('room_cost');
    else if (catLower.includes('toll')) targetInput = document.getElementById('toll_charges');
    else if (catLower.includes('park')) targetInput = document.getElementById('parking_fee');

    if (targetInput) {
      targetInput.value = amount;
      highlightField(targetInput);
      showToast(`Applied ₹${amount} to ${category}!`);
      document.getElementById('ai_receipt_modal').style.display = 'none';
    } else {
      showToast(`Scanned ₹${amount} (${category})`);
      document.getElementById('ai_receipt_modal').style.display = 'none';
    }
  }

  // 9. Setup Integrations on Planner & Result Pages
  function setupPageIntegration() {
    // If on planner form (Step 3 Costs), add the Auto-Estimate button
    const costsHeader = document.querySelector('.form-step[data-step="3"] .step-header');
    if (costsHeader && !document.getElementById('ai_estimate_btn')) {
      const banner = document.createElement('div');
      banner.className = 'ai-planner-banner animate-in';
      banner.innerHTML = `
        <div class="ai-banner-left">
          <div class="ai-sparkle-icon">✨</div>
          <div class="ai-banner-text">
            <strong>Google Gemini Smart Estimator</strong>
            <span>Auto-predict room rates, food budgets, toll charges, and entry fees</span>
          </div>
        </div>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button type="button" class="ai-magic-btn" id="ai_estimate_btn" onclick="TravelAI.autoEstimateBudget()">
            ✨ Auto-Estimate Costs
          </button>
          <button type="button" class="ai-magic-btn secondary" onclick="TravelAI.openReceiptModal()">
            📷 Scan Receipt
          </button>
        </div>
      `;
      costsHeader.parentNode.insertBefore(banner, costsHeader.nextSibling);
    }

    // Top action buttons on Planner page
    const topBarActions = document.querySelector('.top-bar-actions');
    if (topBarActions && !document.getElementById('ai_top_itinerary_btn')) {
      const btn = document.createElement('button');
      btn.id = 'ai_top_itinerary_btn';
      btn.type = 'button';
      btn.className = 'ai-magic-btn';
      btn.style.padding = '6px 12px';
      btn.style.fontSize = '0.8rem';
      btn.innerHTML = '✨ AI Itinerary';
      btn.onclick = () => openItineraryModal();
      topBarActions.prepend(btn);
    }
  }

  return {
    init,
    toggleChat,
    sendMessage,
    sendQuickPrompt,
    openKeyModal,
    closeKeyModal,
    saveKey,
    clearKey,
    autoEstimateBudget,
    openItineraryModal,
    openReceiptModal,
    handleReceiptUpload,
    applyScannedExpense
  };
})();

// Auto-run on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', TravelAI.init);
} else {
  TravelAI.init();
}
