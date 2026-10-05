(function () {
  // Determine server base URL
  const scriptTag = document.currentScript;
  let serverUrl = "https://dental-ai-bot-0j49.onrender.com";
  if (scriptTag && scriptTag.src) {
    try {
      const urlObj = new URL(scriptTag.src);
      serverUrl = urlObj.origin;
    } catch (e) {
      serverUrl = window.location.origin;
    }
  }

  const agencyName = (scriptTag && scriptTag.getAttribute("data-agency")) || "Apex Prime Real Estate";
  const brokerName = (scriptTag && scriptTag.getAttribute("data-broker")) || "Ahmad Al Zaabi";
  const whatsappNumber = (scriptTag && scriptTag.getAttribute("data-whatsapp")) || "+971547400174";
  const locationName = (scriptTag && scriptTag.getAttribute("data-location")) || "Abu Dhabi & Dubai";
  const cleanPhone = whatsappNumber.replace(/[^0-9]/g, "");

  // Inject Styles
  const style = document.createElement("style");
  style.innerHTML = `
    .re-chat-bubble-btn {
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 62px;
      height: 62px;
      border-radius: 50%;
      background: linear-gradient(135deg, #0284c7, #0ea5e9);
      color: #ffffff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 30px;
      cursor: pointer;
      box-shadow: 0 10px 28px rgba(2, 132, 199, 0.55);
      z-index: 99999999;
      transition: transform 0.25s ease, box-shadow 0.25s ease;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      user-select: none;
      -webkit-tap-highlight-color: transparent;
    }
    .re-chat-bubble-btn:hover {
      transform: scale(1.1);
      box-shadow: 0 14px 35px rgba(14, 165, 233, 0.7);
    }
    .re-bubble-badge {
      position: absolute;
      top: -2px;
      right: -2px;
      background: #22c55e;
      border: 2px solid #0f172a;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      box-shadow: 0 0 8px #22c55e;
      animation: rePulse 2s infinite;
    }
    @keyframes rePulse {
      0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
      70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
      100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
    }
    .re-chat-window {
      position: fixed;
      bottom: 98px;
      right: 24px;
      width: 400px;
      max-width: calc(100vw - 32px);
      height: 560px;
      max-height: calc(100vh - 120px);
      background: #0b1120;
      border-radius: 18px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.65);
      display: none;
      flex-direction: column;
      overflow: hidden;
      z-index: 99999999;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      border: 1px solid #1e293b;
    }
    .re-chat-header {
      background: linear-gradient(135deg, #0f172a, #1e293b);
      color: #ffffff;
      padding: 16px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #334155;
    }
    .re-header-title {
      font-weight: 800;
      font-size: 15px;
      color: #f8fafc;
      letter-spacing: 0.3px;
    }
    .re-header-subtitle {
      font-size: 12px;
      color: #38bdf8;
      display: flex;
      align-items: center;
      gap: 6px;
      margin-top: 2px;
    }
    .re-pulse-dot {
      width: 7px;
      height: 7px;
      background: #22c55e;
      border-radius: 50%;
      box-shadow: 0 0 6px #22c55e;
    }
    .re-close-btn {
      background: transparent;
      border: none;
      color: #94a3b8;
      font-size: 24px;
      cursor: pointer;
      line-height: 1;
      padding: 4px;
    }
    .re-close-btn:hover { color: #ffffff; }
    .re-chat-messages {
      flex: 1;
      padding: 16px;
      overflow-y: auto;
      overflow-x: hidden;
      background: #070c18;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .re-msg {
      max-width: 86%;
      padding: 12px 16px;
      border-radius: 14px;
      font-size: 13.5px;
      line-height: 1.5;
      word-break: break-word;
      overflow-wrap: anywhere;
    }
    .re-msg-bot {
      background: #131d33;
      color: #e2e8f0;
      align-self: flex-start;
      border: 1px solid #1e293b;
      border-bottom-left-radius: 4px;
    }
    .re-msg-user {
      background: linear-gradient(135deg, #0284c7, #0369a1);
      color: #ffffff;
      align-self: flex-end;
      border-bottom-right-radius: 4px;
      font-weight: 500;
    }
    .re-portfolio-card {
      margin-top: 10px;
      background: #0f172a;
      border: 1px solid #38bdf8;
      border-radius: 12px;
      padding: 14px;
      color: #f1f5f9;
      font-size: 12.5px;
      box-shadow: 0 4px 14px rgba(2, 132, 199, 0.2);
    }
    .re-card-header {
      font-weight: 800;
      font-size: 13.5px;
      color: #38bdf8;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .re-card-row {
      margin-bottom: 5px;
      display: flex;
      justify-content: space-between;
    }
    .re-card-label { color: #94a3b8; }
    .re-card-val { font-weight: 700; color: #f8fafc; }
    .re-score-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 10px;
      background: #064e3b;
      color: #6ee7b7;
      font-weight: 800;
    }
    .re-whatsapp-btn {
      display: block;
      margin-top: 12px;
      background: #25D366;
      color: #ffffff !important;
      text-decoration: none;
      padding: 10px 14px;
      border-radius: 8px;
      font-weight: 700;
      font-size: 13px;
      text-align: center;
      box-shadow: 0 2px 10px rgba(37, 211, 102, 0.3);
      transition: background 0.2s, transform 0.2s;
    }
    .re-whatsapp-btn:hover {
      background: #20ba5a;
      transform: scale(1.02);
    }
    .re-chat-quick-actions {
      padding: 10px 14px;
      background: #0f172a;
      display: flex;
      gap: 8px;
      overflow-x: auto;
      border-top: 1px solid #1e293b;
      scrollbar-width: none;
    }
    .re-chat-quick-actions::-webkit-scrollbar { display: none; }
    .re-quick-btn {
      background: #1e293b;
      border: 1px solid #334155;
      color: #94a3b8;
      padding: 6px 12px;
      border-radius: 16px;
      font-size: 11.5px;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s;
    }
    .re-quick-btn:hover {
      background: #334155;
      color: #38bdf8;
      border-color: #38bdf8;
    }
    .re-chat-input-area {
      padding: 12px 16px;
      background: #0f172a;
      border-top: 1px solid #1e293b;
      display: flex;
      gap: 8px;
      align-items: center;
    }
    .re-chat-input {
      flex: 1;
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 20px;
      padding: 9px 16px;
      font-size: 13.5px;
      color: #f8fafc;
      outline: none;
    }
    .re-chat-input:focus { border-color: #38bdf8; }
    .re-chat-send-btn {
      background: linear-gradient(135deg, #0284c7, #0369a1);
      border: none;
      color: #ffffff;
      width: 38px;
      height: 38px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 15px;
      transition: transform 0.15s;
    }
    .re-chat-send-btn:hover { transform: scale(1.05); }
    .re-typing {
      font-size: 12px;
      color: #94a3b8;
      font-style: italic;
    }
  `;
  document.head.appendChild(style);

  // Inject HTML UI
  const container = document.createElement("div");
  container.innerHTML = `
    <div id="re-chat-bubble" class="re-chat-bubble-btn" title="Speak with Luxury Property Advisor">
      <span class="re-bubble-badge"></span>
      <span>&#128172;</span>
    </div>

    <div id="re-chat-window" class="re-chat-window">
      <div class="re-chat-header">
        <div>
          <div class="re-header-title">${agencyName}</div>
          <div class="re-header-subtitle">
            <span class="re-pulse-dot"></span>
            Aria &bull; Senior Investment Advisor
          </div>
        </div>
        <button id="re-chat-close" class="re-close-btn">&times;</button>
      </div>

      <div id="re-chat-messages" class="re-chat-messages">
        <div class="re-msg re-msg-bot">
          Welcome to <strong>${agencyName}</strong>. I am Aria, Senior Property Advisor for ${brokerName}.
          <br><br>
          Are you looking for luxury beachfront villas (Saadiyat/Yas), prime Dubai penthouses, or 10-Year UAE Golden Visa investment properties?
        </div>
      </div>

      <div class="re-chat-quick-actions">
        <button class="re-quick-btn" data-text="I am looking for a beachfront villa in Saadiyat Island Abu Dhabi.">&#127958; Saadiyat Villa</button>
        <button class="re-quick-btn" data-text="I want a luxury apartment or penthouse in Downtown Dubai.">&#127961; Downtown Dubai</button>
        <button class="re-quick-btn" data-text="What properties qualify for the UAE 10-Year Golden Visa?">&#128706; Golden Visa (2M+ AED)</button>
        <button class="re-quick-btn" data-text="I would like to speak directly with broker ${brokerName} on WhatsApp.">&#128242; WhatsApp Broker</button>
      </div>

      <form id="re-chat-form" class="re-chat-input-area">
        <input id="re-chat-input" class="re-chat-input" type="text" placeholder="Inquire about communities, budget..." autocomplete="off" />
        <button type="submit" class="re-chat-send-btn">&#10148;</button>
      </form>
    </div>
  `;
  document.body.appendChild(container);

  // Widget Interaction Logic
  const bubble = document.getElementById("re-chat-bubble");
  const win = document.getElementById("re-chat-window");
  const closeBtn = document.getElementById("re-chat-close");
  const form = document.getElementById("re-chat-form");
  const input = document.getElementById("re-chat-input");
  const msgContainer = document.getElementById("re-chat-messages");

  let conversationHistory = [];

  function toggleChat() {
    const isVisible = win.style.display === "flex";
    win.style.display = isVisible ? "none" : "flex";
    if (!isVisible) {
      input.focus();
    }
  }

  bubble.addEventListener("click", toggleChat);
  closeBtn.addEventListener("click", toggleChat);

  function appendMessage(text, role, lead) {
    const div = document.createElement("div");
    div.className = `re-msg ${role === "user" ? "re-msg-user" : "re-msg-bot"}`;

    // Clean internal lead tags safely
    let cleanText = text.replace(/\[QUALIFIED_LEAD:[^\]]+\]/g, "").trim();

    // Format newlines safely without broken regex
    let html = cleanText.split(String.fromCharCode(10)).join("<br>");

    // If an investor lead was finalized and captured
    if (lead) {
      const waMsg = encodeURIComponent(
        `Hello ${brokerName}, I am ${lead.client_name}. I just spoke with Aria on your portal regarding properties in ${lead.target_community} (${lead.budget}). Please send me your curated private portfolio.`
      );
      const waUrl = `https://wa.me/${cleanPhone}?text=${waMsg}`;

      html += `
        <div class="re-portfolio-card">
          <div class="re-card-header">&#10024; Curated Portfolio Prepared</div>
          <div class="re-card-row"><span class="re-card-label">Investor:</span><span class="re-card-val">${lead.client_name}</span></div>
          <div class="re-card-row"><span class="re-card-label">Location:</span><span class="re-card-val">${lead.target_community}</span></div>
          <div class="re-card-row"><span class="re-card-label">Budget:</span><span class="re-card-val">${lead.budget}</span></div>
          <div class="re-card-row"><span class="re-card-label">Readiness:</span><span class="re-score-badge">${lead.score}% Match &bull; ${lead.tier}</span></div>
          <a href="${waUrl}" target="_blank" class="re-whatsapp-btn">&#128172; Receive Portfolio on WhatsApp</a>
        </div>
      `;
    }

    div.innerHTML = html;
    msgContainer.appendChild(div);
    msgContainer.scrollTop = msgContainer.scrollHeight;
  }

  async function handleSend(userText) {
    if (!userText.trim()) return;
    appendMessage(userText, "user");
    input.value = "";

    conversationHistory.push({ role: "user", content: userText });

    // Typing indicator
    const typingDiv = document.createElement("div");
    typingDiv.className = "re-msg re-msg-bot re-typing";
    typingDiv.id = "re-typing-indicator";
    typingDiv.textContent = "Aria is analyzing prime properties...";
    msgContainer.appendChild(typingDiv);
    msgContainer.scrollTop = msgContainer.scrollHeight;

    try {
      const resp = await fetch(`${serverUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userText,
          history: conversationHistory,
          agency_name: agencyName,
          broker_name: brokerName,
          broker_whatsapp: whatsappNumber,
          location: locationName,
        }),
      });

      const data = await resp.json();
      const currentIndicator = document.getElementById("re-typing-indicator");
      if (currentIndicator) currentIndicator.remove();

      const reply = data.reply || `Thank you for your interest. ${brokerName} is available directly on WhatsApp at ${whatsappNumber}.`;
      appendMessage(reply, "assistant", data.lead);
      conversationHistory.push({ role: "assistant", content: reply });
    } catch (err) {
      const currentIndicator = document.getElementById("re-typing-indicator");
      if (currentIndicator) currentIndicator.remove();
      appendMessage(
        `Aria is currently connecting to our live MLS feeds. You can consult directly with ${brokerName} on WhatsApp: <a href="https://wa.me/${cleanPhone}" target="_blank" style="color:#38bdf8; font-weight:700;">Click here</a>`,
        "assistant"
      );
    }
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    handleSend(input.value);
  });

  // Quick Action Buttons
  document.querySelectorAll(".re-quick-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const text = btn.getAttribute("data-text");
      if (text) {
        handleSend(text);
      }
    });
  });
})();
