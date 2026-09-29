(function () {
  // Determine server base URL from script tag
  const scriptTag = document.currentScript;
  let serverUrl = "http://127.0.0.1:8000";
  if (scriptTag && scriptTag.src) {
    const urlObj = new URL(scriptTag.src);
    serverUrl = urlObj.origin;
  }

  const clinicName = (scriptTag && scriptTag.getAttribute("data-clinic")) || "Al Dhabi Dental Centre";
  const whatsappNumber = (scriptTag && scriptTag.getAttribute("data-whatsapp")) || "+971547400174";
  const cleanPhone = whatsappNumber.replace(/[^0-9]/g, "");

  // Inject Styles
  const style = document.createElement("style");
  style.innerHTML = `
    .ai-chat-bubble-btn {
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, #0284c7, #0369a1);
      color: #ffffff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 28px;
      cursor: pointer;
      box-shadow: 0 8px 24px rgba(2, 132, 199, 0.4);
      z-index: 999999;
      transition: transform 0.25s ease, box-shadow 0.25s ease;
    }
    .ai-chat-bubble-btn:hover {
      transform: scale(1.08);
      box-shadow: 0 12px 28px rgba(2, 132, 199, 0.5);
    }
    .ai-chat-window {
      position: fixed;
      bottom: 96px;
      right: 24px;
      width: 380px;
      max-width: calc(100vw - 48px);
      height: 520px;
      max-height: calc(100vh - 120px);
      background: #ffffff;
      border-radius: 16px;
      box-shadow: 0 12px 36px rgba(0, 0, 0, 0.16);
      display: none;
      flex-direction: column;
      overflow: hidden;
      z-index: 999999;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      border: 1px solid #e2e8f0;
    }
    .ai-chat-header {
      background: linear-gradient(135deg, #0284c7, #0369a1);
      color: #ffffff;
      padding: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .ai-chat-header-title {
      font-weight: 700;
      font-size: 15px;
    }
    .ai-chat-header-subtitle {
      font-size: 12px;
      opacity: 0.9;
    }
    .ai-chat-close-btn {
      background: transparent;
      border: none;
      color: #ffffff;
      font-size: 20px;
      cursor: pointer;
      line-height: 1;
    }
    .ai-chat-messages {
      flex: 1;
      padding: 16px;
      overflow-y: auto;
      overflow-x: hidden;
      background: #f8fafc;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .ai-msg {
      max-width: 85%;
      padding: 10px 14px;
      border-radius: 14px;
      font-size: 14px;
      line-height: 1.45;
      word-break: break-word;
      overflow-wrap: anywhere;
    }
    .ai-msg-bot {
      background: #ffffff;
      color: #1e293b;
      align-self: flex-start;
      border: 1px solid #e2e8f0;
      border-bottom-left-radius: 4px;
    }
    .ai-msg-user {
      background: #0284c7;
      color: #ffffff;
      align-self: flex-end;
      border-bottom-right-radius: 4px;
    }
    .ai-whatsapp-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-top: 10px;
      background: #25D366;
      color: #ffffff !important;
      text-decoration: none;
      padding: 8px 16px;
      border-radius: 20px;
      font-weight: 600;
      font-size: 13px;
      box-shadow: 0 2px 8px rgba(37, 211, 102, 0.3);
      transition: transform 0.15s, background 0.15s;
    }
    .ai-whatsapp-btn:hover {
      background: #20ba5a;
      transform: scale(1.02);
    }
    .ai-booking-card {
      margin-top: 12px;
      background: #f0fdf4;
      border: 1px solid #86efac;
      border-radius: 12px;
      padding: 14px;
      color: #14532d;
      font-size: 13px;
    }
    .ai-booking-header {
      font-weight: 700;
      font-size: 14px;
      color: #166534;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .ai-booking-row {
      margin-bottom: 4px;
      display: flex;
      justify-content: space-between;
    }
    .ai-booking-label {
      color: #15803d;
      font-weight: 500;
    }
    .ai-booking-val {
      font-weight: 700;
      color: #14532d;
    }
    .ai-booking-footer {
      margin-top: 8px;
      padding-top: 6px;
      border-top: 1px dashed #bbf7d0;
      font-size: 11px;
      color: #166534;
      text-align: center;
    }
    .ai-chat-quick-actions {
      padding: 8px 16px;
      background: #f1f5f9;
      display: flex;
      gap: 8px;
      overflow-x: auto;
      border-top: 1px solid #e2e8f0;
      scrollbar-width: none;
      -ms-overflow-style: none;
    }
    .ai-chat-quick-actions::-webkit-scrollbar {
      display: none;
    }
    .ai-quick-btn {
      background: #ffffff;
      border: 1px solid #cbd5e1;
      color: #334155;
      padding: 6px 10px;
      border-radius: 20px;
      font-size: 12px;
      cursor: pointer;
      white-space: nowrap;
      transition: background 0.2s;
    }
    .ai-quick-btn:hover {
      background: #e2e8f0;
    }
    .ai-chat-input-area {
      padding: 12px 16px;
      background: #ffffff;
      border-top: 1px solid #e2e8f0;
      display: flex;
      gap: 8px;
    }
    .ai-chat-input {
      flex: 1;
      border: 1px solid #cbd5e1;
      border-radius: 20px;
      padding: 8px 14px;
      font-size: 14px;
      outline: none;
    }
    .ai-chat-input:focus {
      border-color: #0284c7;
    }
    .ai-chat-send-btn {
      background: #0284c7;
      border: none;
      color: #ffffff;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
    }
  `;
  document.head.appendChild(style);

  // Inject HTML Elements
  const container = document.createElement("div");
  container.innerHTML = `
    <div id="ai-chat-bubble" class="ai-chat-bubble-btn" title="Chat with Us">
      💬
    </div>
    <div id="ai-chat-window" class="ai-chat-window">
      <div class="ai-chat-header">
        <div>
          <div class="ai-chat-header-title">${clinicName}</div>
          <div class="ai-chat-header-subtitle">● Online | 24/7 AI Receptionist</div>
        </div>
        <button id="ai-chat-close" class="ai-chat-close-btn">&times;</button>
      </div>
      <div id="ai-chat-messages" class="ai-chat-messages">
        <div class="ai-msg ai-msg-bot">
          Hello! Welcome to <strong>${clinicName}</strong>. How can I help you today? You can ask about our dental services, book an appointment, or check our timings!
        </div>
      </div>
      <div class="ai-chat-quick-actions">
        <button class="ai-quick-btn" data-text="I would like to book a dental checkup appointment.">📅 Book Visit</button>
        <button class="ai-quick-btn" data-text="What are your clinic working hours?">⏱️ Timings</button>
        <button class="ai-quick-btn" data-text="Do you accept Daman or Thiqa insurance?">💳 Insurance</button>
        <a class="ai-quick-btn" href="https://wa.me/${cleanPhone}?text=Hello%20I%20would%20like%20to%20speak%20with%20reception" target="_blank" style="text-decoration:none;">📲 WhatsApp Us</a>
      </div>
      <form id="ai-chat-form" class="ai-chat-input-area">
        <input id="ai-chat-input" class="ai-chat-input" type="text" placeholder="Type your message..." autocomplete="off" />
        <button type="submit" class="ai-chat-send-btn">➤</button>
      </form>
    </div>
  `;
  document.body.appendChild(container);

  // Logic
  const bubble = document.getElementById("ai-chat-bubble");
  const win = document.getElementById("ai-chat-window");
  const closeBtn = document.getElementById("ai-chat-close");
  const form = document.getElementById("ai-chat-form");
  const input = document.getElementById("ai-chat-input");
  const msgContainer = document.getElementById("ai-chat-messages");

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

  function appendMessage(text, role, booking) {
    const div = document.createElement("div");
    div.className = `ai-msg ${role === "user" ? "ai-msg-user" : "ai-msg-bot"}`;
    
    let cleanText = text.replace(/\[BOOKING_SUCCESS:[^\]]+\]/g, "").trim();

    // Convert raw wa.me links into a sleek green WhatsApp action button
    const waRegex = /(https?:\/\/(?:wa\.me|api\.whatsapp\.com)[^\s<]+)/g;
    cleanText = cleanText.replace(waRegex, function(url) {
      return `<br><a href="${url}" target="_blank" class="ai-whatsapp-btn">📲 Open WhatsApp to Confirm</a>`;
    });

    let html = cleanText.replace(/\n/g, "<br>");

    // If an appointment was booked, append the official booking confirmation card
    if (booking) {
      html += `
        <div class="ai-booking-card">
          <div class="ai-booking-header">✅ Appointment Confirmed!</div>
          <div class="ai-booking-row"><span class="ai-booking-label">Booking ID:</span><span class="ai-booking-val">${booking.booking_id}</span></div>
          <div class="ai-booking-row"><span class="ai-booking-label">Patient:</span><span class="ai-booking-val">${booking.patient_name}</span></div>
          <div class="ai-booking-row"><span class="ai-booking-label">Phone:</span><span class="ai-booking-val">${booking.phone_number}</span></div>
          <div class="ai-booking-row"><span class="ai-booking-label">Treatment:</span><span class="ai-booking-val">${booking.treatment}</span></div>
          <div class="ai-booking-row"><span class="ai-booking-label">Date & Time:</span><span class="ai-booking-val">${booking.date_time}</span></div>
          <div class="ai-booking-footer">📅 Registered in Clinic Schedule. SMS confirmation dispatched.</div>
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

    // Show temporary typing indicator
    const typingDiv = document.createElement("div");
    typingDiv.className = "ai-msg ai-msg-bot";
    typingDiv.id = "ai-typing";
    typingDiv.textContent = "Typing...";
    msgContainer.appendChild(typingDiv);
    msgContainer.scrollTop = msgContainer.scrollHeight;

    try {
      const resp = await fetch(`${serverUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userText,
          history: conversationHistory,
          clinic_name: clinicName,
          whatsapp_number: whatsappNumber,
        }),
      });

      const data = await resp.json();
      typingDiv.remove();

      const reply = data.reply || "Thank you! Please contact us on WhatsApp for assistance.";
      appendMessage(reply, "assistant", data.booking);
      conversationHistory.push({ role: "assistant", content: reply });
    } catch (err) {
      typingDiv.remove();
      appendMessage("Our AI is currently connecting. You can chat with our team directly on WhatsApp: <a href='https://wa.me/" + cleanPhone + "' target='_blank'>Click here</a>", "assistant");
    }
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    handleSend(input.value);
  });

  // Quick Action Buttons
  document.querySelectorAll(".ai-quick-btn").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      const text = btn.getAttribute("data-text");
      if (text) {
        handleSend(text);
      }
    });
  });
})();
