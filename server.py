import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load root .env
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

app = FastAPI(title="UAE AI Automation Platform - Dental & Real Estate")

# CORS enabled
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

APPOINTMENTS_FILE = Path(__file__).resolve().parent / "clinic_appointments.json"
LEADS_FILE = Path(__file__).resolve().parent / "leads_database.json"

class MessageItem(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[MessageItem]] = []
    # Dental fields
    clinic_name: Optional[str] = None
    clinic_location: Optional[str] = None
    whatsapp_number: Optional[str] = None
    # Real estate fields
    agency_name: Optional[str] = None
    broker_name: Optional[str] = None
    broker_whatsapp: Optional[str] = None
    location: Optional[str] = None

class AppointmentBooking(BaseModel):
    patient_name: str
    phone_number: str
    treatment: str
    date_time: str
    clinic_name: Optional[str] = "Al Dhabi Dental Centre"

# ==================== DENTAL PROMPT & LOGIC ====================

DEFAULT_CLINIC_CONTEXT = """
You are 'Aura', a polite, empathetic, and professional AI Medical Receptionist for {clinic_name} in {clinic_location}.

Clinic Knowledge:
- Working Hours: Saturday to Thursday: 9:00 AM - 9:00 PM. Friday: 2:00 PM - 8:00 PM.
- Emergency Care: 24/7 emergency dental hotline available.
- Services Offered:
  * Teeth Whitening & Cleaning (from 350 AED)
  * Orthodontics & Invisible Aligners (Invisalign certified)
  * Dental Implants & Oral Surgery
  * Cosmetic Veneers & Smile Makeovers
  * Pediatric (Children) Dentistry
- Accepted Insurances: Daman, Thiqa, NextCare, AXA, MetLife, Oman Insurance.
- WhatsApp Direct Booking: {whatsapp_number}

CURRENTLY RESERVED SCHEDULE (SLOTS ALREADY TAKEN):
{existing_booked_slots}

CRITICAL ANTI-DOUBLE-BOOKING RULES:
1. Examine the CURRENTLY RESERVED SCHEDULE above before confirming ANY appointment.
2. If the patient requests a date/time that is already booked or overlaps with an existing appointment (for example, if another patient already has 10:00 AM):
   - You MUST NOT book the conflicting slot!
   - Inform the patient politely: "I see that [Requested Time] is already reserved for another patient."
   - Suggest 2 alternative open times (for example: "Would 10:30 AM or 11:30 AM work for you instead?").
   - DO NOT output the [BOOKING_SUCCESS: ...] tag for a conflicting slot!
3. Only when the patient agrees to an OPEN, non-conflicting time AND you have all 4 details (Full Name, Phone Number, Treatment, and Date/Time), output:
   [BOOKING_SUCCESS: PatientName | PhoneNumber | Treatment | DateTime]

Appointment Booking Protocol:
1. Politely ask for any missing details (Name, Phone, Treatment, Preferred Date and Time).
2. Check for slot conflicts.
3. Lock in only available slots.
"""

def get_clinic_appointments(clinic_name: Optional[str] = None) -> List[Dict]:
    if APPOINTMENTS_FILE.exists():
        try:
            data = json.loads(APPOINTMENTS_FILE.read_text(encoding="utf-8"))
            if clinic_name:
                return [b for b in data if (b.get("clinic_name") or "").strip().lower() == clinic_name.strip().lower()]
            return data
        except Exception:
            return []
    return []

def save_clinic_appointment(booking: Dict):
    APPOINTMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    all_appointments = []
    if APPOINTMENTS_FILE.exists():
        try:
            all_appointments = json.loads(APPOINTMENTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            all_appointments = []
    all_appointments.append(booking)
    APPOINTMENTS_FILE.write_text(json.dumps(all_appointments, indent=2), encoding="utf-8")

# ==================== REAL ESTATE PROMPT & LOGIC ====================

REAL_ESTATE_SYSTEM_PROMPT = """
You are 'Aria', a highly sophisticated, polite, and discrete Senior Property Investment Advisor for {agency_name} in {location}.
Your primary Broker is {broker_name}.

YOUR CORE MISSION:
Engage high-net-worth investors and property buyers, provide expert insights into the Abu Dhabi and Dubai property markets, and rigorously QUALIFY their purchasing readiness.

KNOWLEDGE BASE (UAE REAL ESTATE):
1. Top Abu Dhabi Communities:
   - Saadiyat Island (Cultural District, Luxury Beachfront Villas, Saadiyat Lagoons, Louvre Residences) - from 3.5M AED
   - Yas Island (Yas Bay, Yas Acres, Waterfront Townhouses & Theme Park lifestyle) - from 1.8M AED
   - Al Reem Island (Waterfront towers, Shams Abu Dhabi, Marina Square, high rental yields) - from 850K AED
2. Top Dubai Communities:
   - Downtown Dubai & Business Bay (Burj Khalifa views, luxury apartments) - from 1.9M AED
   - Dubai Hills Estate (Golf course villas, family communities by Emaar) - from 3.2M AED
   - Palm Jumeirah (Ultra-luxury beachfront penthouses & custom villas) - from 6M to 50M+ AED
3. UAE Golden Visa:
   - Real estate investment of 2,000,000 AED ($545,000 USD) or more grants a 10-Year Renewable UAE Golden Visa for the investor and entire family.
4. Top Developers: Aldar Properties (Abu Dhabi leader), Emaar, Sobha, DAMAC, Nakheel.

YOUR 4-STEP QUALIFICATION PROTOCOL:
During the natural conversation, you must discover:
1. Target Community & Property Type (e.g., 3-bed villa in Saadiyat or 2-bed apartment in Downtown).
2. Investment Purpose: End-user (family home) or Investor (capital appreciation / rental yield / Golden Visa).
3. Purchase Budget:
   - Ultra-Luxury VIP: 5M+ AED
   - Mid-Luxury Qualified: 1.5M - 5M AED
   - Entry: Under 1.5M AED
4. Funding Status: Cash buyer vs Pre-approved mortgage vs Seeking bank mortgage financing.
5. Timeline: Immediate (within 14-30 days) vs Exploring (3-6 months).
6. Contact: Full Name and Mobile/WhatsApp number to send the private portfolio brochure.

LEAD FINALIZATION PROTOCOL:
Once you have collected the buyer's Name, Phone/WhatsApp, Target Community, Budget (e.g. 3.5M AED), and Financing readiness, provide a warm executive sign-off:
Inform them that {broker_name} is preparing a private curated portfolio of off-market and prime properties tailored to their exact criteria.

AT THE VERY END OF YOUR REPLY, OUTPUT THIS EXACT STRUCTURED TAG:
[QUALIFIED_LEAD: FullName | PhoneNumber | Community | PropertyType | BudgetAED | CashOrMortgage | Timeline]

Example:
[QUALIFIED_LEAD: Dr. Tariq Al Mansoori | +971501234567 | Saadiyat Island | 4-Bed Luxury Villa | 5,500,000 AED | Cash Ready | Within 30 Days]
"""

def get_leads_list() -> List[Dict]:
    if LEADS_FILE.exists():
        try:
            return json.loads(LEADS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_lead(lead: Dict):
    LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = get_leads_list()
    existing.append(lead)
    LEADS_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")

def calculate_lead_score(budget_str: str, cash_or_mortgage: str, timeline_str: str) -> Dict:
    score = 50
    clean_nums = re.findall(r'\d+', budget_str.replace(",", "").replace(".", ""))
    budget_val = 0
    if clean_nums:
        raw_val = int(clean_nums[0])
        if raw_val < 100:
            budget_val = raw_val * 1_000_000
        else:
            budget_val = raw_val

    if budget_val >= 5_000_000:
        score += 30
        tier = "Ultra-Luxury VIP"
        tier_class = "badge-vip"
    elif budget_val >= 1_500_000:
        score += 20
        tier = "High-Intent Buyer"
        tier_class = "badge-hot"
    else:
        score += 10
        tier = "Qualified Prospect"
        tier_class = "badge-warm"

    if "cash" in cash_or_mortgage.lower():
        score += 15
    elif "approved" in cash_or_mortgage.lower() or "pre" in cash_or_mortgage.lower():
        score += 10

    if "14" in timeline_str or "30" in timeline_str or "immediate" in timeline_str.lower() or "soon" in timeline_str.lower():
        score += 10

    final_score = min(score, 100)
    return {
        "score": final_score,
        "tier": tier,
        "tier_class": tier_class
    }

# ==================== CORE ROUTES ====================

@app.get("/")
def home():
    return {
        "status": "online",
        "services": ["Dental Clinic AI Receptionist", "UAE Real Estate AI Lead Qualification"],
        "model": GEMINI_MODEL,
        "ready": bool(GEMINI_API_KEY)
    }

@app.get("/widget.js")
def get_widget():
    """Serves standard dental widget."""
    widget_path = Path(__file__).parent / "static" / "widget.js"
    if not widget_path.exists():
        raise HTTPException(status_code=404, detail="Widget script not found")
    return FileResponse(widget_path, media_type="application/javascript")

RE_WIDGET_JS_CODE = r"""(function () {
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
"""

@app.get("/re/widget.js")
@app.get("/re-widget.js")
def get_re_widget():
    """Serves luxury real estate widget with guaranteed inline fallback."""
    widget_path = Path(__file__).parent / "static" / "re_widget.js"
    if widget_path.exists():
        return FileResponse(widget_path, media_type="application/javascript")
    return HTMLResponse(content=RE_WIDGET_JS_CODE, media_type="application/javascript")

# ==================== CHAT ENDPOINT (HYBRID) ====================

@app.post("/chat")
@app.post("/re/chat")
def chat_endpoint(req: ChatRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    # Determine vertical: Real Estate vs Dental
    is_real_estate = bool(req.agency_name or req.broker_name)

    if is_real_estate:
        agency = req.agency_name or "Apex Prime Real Estate"
        broker = req.broker_name or "Ahmad Al Zaabi"
        broker_wa = req.broker_whatsapp or "+971547400174"
        loc = req.location or "Abu Dhabi & Dubai, UAE"

        system_prompt = REAL_ESTATE_SYSTEM_PROMPT.format(
            agency_name=agency,
            broker_name=broker,
            broker_whatsapp=broker_wa,
            location=loc
        )

        conversation_text = ""
        for msg in req.history[-6:]:
            speaker = "Client" if msg.role == "user" else "Advisor"
            conversation_text += f"{speaker}: {msg.content}\n"
        full_prompt = f"{conversation_text}Client: {req.message}\nAdvisor:"

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_API_KEY)
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.6,
                max_output_tokens=350,
            )

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=full_prompt,
                config=config,
            )

            reply_text = response.text.strip() if response and response.text else "Thank you for inquiring with us."

            lead_data = None
            if "[QUALIFIED_LEAD:" in reply_text:
                try:
                    match = re.search(r'\[QUALIFIED_LEAD:\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\]]+)\]', reply_text)
                    if match:
                        name, phone, community, prop_type, budget, financing, timeline = [g.strip() for g in match.groups()]
                        lead_id = f"RE-{datetime.now().strftime('%m%d%H%M')}"
                        score_info = calculate_lead_score(budget, financing, timeline)

                        lead_data = {
                            "lead_id": lead_id,
                            "client_name": name,
                            "phone_number": phone,
                            "target_community": community,
                            "property_type": prop_type,
                            "budget": budget,
                            "financing": financing,
                            "timeline": timeline,
                            "score": score_info["score"],
                            "tier": score_info["tier"],
                            "tier_class": score_info["tier_class"],
                            "agency_name": agency,
                            "broker_name": broker,
                            "captured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        save_lead(lead_data)
                except Exception as e:
                    print(f"Error saving lead: {e}")

            return {"reply": reply_text, "lead": lead_data}
        except Exception as e:
            return {
                "reply": f"Thank you for reaching out to {agency}. Our senior broker {broker} is available directly on WhatsApp at {broker_wa}."
            }

    else:
        # Dental Vertical
        c_name = req.clinic_name or "Al Dhabi Dental Centre"
        c_loc = req.clinic_location or "Abu Dhabi, UAE"
        wa_num = req.whatsapp_number or "+971588360378"
        clean_wa = "".join(filter(str.isdigit, wa_num))

        existing_bookings = get_clinic_appointments(clinic_name=c_name)
        existing_slots_str = ""
        if existing_bookings:
            for b in existing_bookings:
                existing_slots_str += f"- Booked: {b.get('date_time', '')} (Treatment: {b.get('treatment', '')})\n"
        else:
            existing_slots_str = "No existing appointments reserved yet today."

        system_prompt = DEFAULT_CLINIC_CONTEXT.format(
            clinic_name=c_name,
            clinic_location=c_loc,
            whatsapp_number=wa_num,
            existing_booked_slots=existing_slots_str
        )

        conversation_text = ""
        for msg in req.history[-6:]:
            speaker = "Patient" if msg.role == "user" else "Aura"
            conversation_text += f"{speaker}: {msg.content}\n"
        full_prompt = f"{conversation_text}Patient: {req.message}\nAura:"

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_API_KEY)
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.5,
                max_output_tokens=300,
            )

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=full_prompt,
                config=config,
            )

            reply_text = response.text.strip() if response and response.text else "Thank you for contacting our clinic."

            booking_data = None
            if "[BOOKING_SUCCESS:" in reply_text:
                try:
                    match = re.search(r'\[BOOKING_SUCCESS:\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\]]+)\]', reply_text)
                    if match:
                        p_name, p_phone, p_treatment, p_datetime = [g.strip() for g in match.groups()]
                        booking_id = f"DHABI-{datetime.now().strftime('%m%d%H%M')}"
                        booking_data = {
                            "booking_id": booking_id,
                            "patient_name": p_name,
                            "phone_number": p_phone,
                            "treatment": p_treatment,
                            "date_time": p_datetime,
                            "clinic_name": c_name,
                            "booked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        save_clinic_appointment(booking_data)
                except Exception as e:
                    print(f"Error saving appointment: {e}")

            return {"reply": reply_text, "booking": booking_data}
        except Exception as e:
            return {
                "reply": f"Thank you for contacting {c_name}. Please message us on WhatsApp at https://wa.me/{clean_wa}."
            }

# ==================== REAL ESTATE DEMO & DASHBOARD ====================

@app.get("/re/demo", response_class=HTMLResponse)
@app.get("/realestate", response_class=HTMLResponse)
def get_re_demo(agency: Optional[str] = "Apex Prime Real Estate", broker: Optional[str] = "Ahmad Al Zaabi", whatsapp: Optional[str] = "+971547400174"):
    import urllib.parse
    enc_agency = urllib.parse.quote(agency)
    enc_broker = urllib.parse.quote(broker)
    dashboard_url = f"/leads?agency={enc_agency}&broker={enc_broker}"

    demo_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{agency} | Luxury Properties Abu Dhabi & Dubai</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #090d16;
    color: #f8fafc;
  }}
  header {{
    background: rgba(15, 23, 42, 0.95);
    padding: 18px 36px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #1e293b;
    position: sticky;
    top: 0;
    z-index: 100;
  }}
  .logo {{
    font-size: 20px;
    font-weight: 800;
    letter-spacing: 1px;
    color: #38bdf8;
  }}
  .tagline {{
    font-size: 11px;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 1.5px;
  }}
  .dash-link {{
    background: #0284c7;
    color: #ffffff;
    padding: 8px 18px;
    border-radius: 8px;
    text-decoration: none;
    font-size: 13px;
    font-weight: 700;
  }}
  .hero {{
    padding: 70px 24px 50px;
    max-width: 1000px;
    margin: 0 auto;
    text-align: center;
  }}
  .hero-badge {{
    display: inline-block;
    background: rgba(56, 189, 248, 0.15);
    color: #38bdf8;
    border: 1px solid #0284c7;
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    margin-bottom: 20px;
    letter-spacing: 1px;
  }}
  .hero h1 {{
    font-size: 42px;
    margin: 0 0 16px;
    font-weight: 800;
    line-height: 1.2;
    background: linear-gradient(135deg, #ffffff, #94a3b8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .hero p {{
    font-size: 17px;
    color: #94a3b8;
    max-width: 700px;
    margin: 0 auto 30px;
    line-height: 1.6;
  }}
  .interactive-hint {{
    background: #1e293b;
    border: 1px solid #38bdf8;
    color: #38bdf8;
    display: inline-block;
    padding: 12px 24px;
    border-radius: 30px;
    font-weight: 700;
    font-size: 14px;
  }}
  .properties-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 24px;
    max-width: 1100px;
    margin: 40px auto 80px;
    padding: 0 20px;
  }}
  .prop-card {{
    background: #131b2e;
    border: 1px solid #1e293b;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
  }}
  .prop-img {{
    height: 180px;
    background: linear-gradient(135deg, #1e293b, #0f172a);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 48px;
  }}
  .prop-info {{
    padding: 20px;
  }}
  .prop-tag {{
    font-size: 11px;
    color: #38bdf8;
    font-weight: 700;
    text-transform: uppercase;
  }}
  .prop-title {{
    font-size: 18px;
    font-weight: 700;
    margin: 6px 0;
  }}
  .prop-price {{
    font-size: 16px;
    font-weight: 800;
    color: #4ade80;
    margin-bottom: 8px;
  }}
  .prop-desc {{
    font-size: 13px;
    color: #94a3b8;
    line-height: 1.5;
  }}
</style>
</head>
<body>

<header>
  <div>
    <div class="logo">&#127963; {agency}</div>
    <div class="tagline">Private Client Real Estate Advisory</div>
  </div>
  <a href="{dashboard_url}" class="dash-link" target="_blank">&#128202; View Broker Lead Pipeline</a>
</header>

<div class="hero">
  <div class="hero-badge">AI PROPERTY ADVISOR PREVIEW</div>
  <h1>Luxury Waterfront & Golf Living in Abu Dhabi & Dubai</h1>
  <p>Exclusive off-plan and secondary market residences in Saadiyat Island, Yas Island, Palm Jumeirah, and Downtown Dubai. Eligible for 10-Year UAE Golden Visa.</p>
  <div class="interactive-hint">
    &#128071; Tap the blue chat bubble at the bottom-right to test the AI Lead-Qualifier!
  </div>
</div>

<div class="properties-grid">
  <div class="prop-card">
    <div class="prop-img">&#127958;</div>
    <div class="prop-info">
      <div class="prop-tag">Saadiyat Island &bull; Abu Dhabi</div>
      <div class="prop-title">Beachfront Luxury Villas</div>
      <div class="prop-price">From 4,800,000 AED</div>
      <div class="prop-desc">Exclusive private enclave by Aldar with private beach access and proximity to the Louvre Abu Dhabi.</div>
    </div>
  </div>

  <div class="prop-card">
    <div class="prop-img">&#127961;</div>
    <div class="prop-info">
      <div class="prop-tag">Downtown Dubai</div>
      <div class="prop-title">Opera District Residences</div>
      <div class="prop-price">From 2,400,000 AED</div>
      <div class="prop-desc">High-floor luxury suites with direct Burj Khalifa panoramas and high short-term rental yields (8.5%+).</div>
    </div>
  </div>

  <div class="prop-card">
    <div class="prop-img">&#9971;</div>
    <div class="prop-info">
      <div class="prop-tag">Yas Island &bull; Abu Dhabi</div>
      <div class="prop-title">Yas Acres Golf Townhouses</div>
      <div class="prop-price">From 2,100,000 AED</div>
      <div class="prop-desc">9-hole championship golf course community with international schools and marina waterfront.</div>
    </div>
  </div>
</div>

<!-- LIVE EMBEDDABLE REAL ESTATE WIDGET -->
<script 
  src="/re-widget.js" 
  data-agency="{agency}" 
  data-broker="{broker}"
  data-whatsapp="{whatsapp}">
</script>

</body>
</html>"""
    return HTMLResponse(content=demo_html, media_type="text/html; charset=utf-8")

@app.get("/api/leads")
def api_leads():
    return get_leads_list()

@app.get("/leads", response_class=HTMLResponse)
@app.get("/re/leads", response_class=HTMLResponse)
def leads_dashboard(agency: Optional[str] = None, broker: Optional[str] = None):
    all_leads = get_leads_list()
    
    if agency:
        leads = [l for l in all_leads if (l.get("agency_name") or "").strip().lower() == agency.strip().lower()]
        display_agency = agency
    else:
        leads = all_leads
        display_agency = "Apex Prime Real Estate"

    display_broker = broker or "Ahmad Al Zaabi"
    total_leads = len(leads)
    vip_leads_count = sum(1 for l in leads if l.get("score", 0) >= 80)

    rows_html = ""
    cards_html = ""

    for l in reversed(leads):
        lid = l.get("lead_id", "N/A")
        cname = l.get("client_name", "Anonymous")
        phone = l.get("phone_number", "")
        clean_phone = "".join(filter(str.isdigit, phone))
        comm = l.get("target_community", "Abu Dhabi / Dubai")
        ptype = l.get("property_type", "Residential")
        budget = l.get("budget", "Flexible")
        fin = l.get("financing", "Cash / Mortgage")
        time_frame = l.get("timeline", "30 Days")
        score = l.get("score", 70)
        tier = l.get("tier", "Qualified Buyer")
        tier_class = l.get("tier_class", "badge-hot")

        wa_msg = f"Hello {cname}, Ahmad from {display_agency} here. I have prepared your curated off-market portfolio for {comm} ({budget}). When is a good time for a brief discussion?"
        import urllib.parse
        wa_link = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_msg)}"

        rows_html += f"""
        <tr>
          <td><span class="badge badge-id">{lid}</span></td>
          <td><strong>{cname}</strong></td>
          <td><a href="tel:{clean_phone}" style="color:#0284c7; text-decoration:none; font-weight:700;">{phone}</a></td>
          <td><strong>{comm}</strong><br><span style="font-size:12px; color:#64748b;">{ptype}</span></td>
          <td><span class="budget-badge">{budget}</span></td>
          <td>{fin}</td>
          <td><span class="score-pill">{score}%</span></td>
          <td><span class="badge {tier_class}">{tier}</span></td>
          <td>
            <a href="{wa_link}" target="_blank" class="btn-wa">&#128172; WhatsApp Brochure</a>
          </td>
        </tr>
        """

        cards_html += f"""
        <div class="lead-card">
          <div class="card-head">
            <span class="badge badge-id">{lid}</span>
            <span class="badge {tier_class}">{tier}</span>
          </div>
          <div class="card-name">{cname}</div>
          <div class="meta-box">
            <div class="meta-row"><span class="meta-lbl">&#128205; Target:</span><strong>{comm} &bull; {ptype}</strong></div>
            <div class="meta-row"><span class="meta-lbl">&#128176; Budget:</span><span class="budget-val">{budget} ({fin})</span></div>
            <div class="meta-row"><span class="meta-lbl">&#128222; Mobile:</span><a href="tel:{clean_phone}">{phone}</a></div>
            <div class="meta-row"><span class="meta-lbl">&#9201; Readiness:</span><span>{time_frame} &bull; Score: {score}%</span></div>
          </div>
          <a href="{wa_link}" target="_blank" class="btn-wa-full">&#128172; Send Curated Portfolio on WhatsApp</a>
        </div>
        """

    if not rows_html:
        rows_html = "<tr><td colspan='9' style='text-align:center; padding:36px; color:#64748b;'>No investor leads captured yet. The AI is waiting for incoming property inquiries.</td></tr>"
        cards_html = "<div style='text-align:center; padding:32px; color:#64748b; background:#1e293b; border-radius:12px;'>No investor leads captured yet.</div>"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>{display_agency} &mdash; VIP Investor Lead Pipeline</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f172a;
    color: #f8fafc;
    -webkit-font-smoothing: antialiased;
  }}
  .navbar {{
    background: linear-gradient(135deg, #1e293b, #0f172a);
    padding: 18px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #334155;
    flex-wrap: wrap;
    gap: 12px;
  }}
  .navbar h1 {{
    margin: 0;
    font-size: 19px;
    font-weight: 800;
    color: #f1f5f9;
    letter-spacing: 0.5px;
  }}
  .navbar-broker {{
    font-size: 13px;
    background: #1e293b;
    border: 1px solid #475569;
    padding: 6px 14px;
    border-radius: 20px;
    color: #38bdf8;
    font-weight: 600;
  }}
  .container {{
    max-width: 1240px;
    margin: 28px auto;
    padding: 0 20px;
  }}
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 24px;
  }}
  .stat-card {{
    background: #1e293b;
    padding: 22px;
    border-radius: 14px;
    border: 1px solid #334155;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  }}
  .stat-title {{
    font-size: 12px;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
  }}
  .stat-val {{
    font-size: 28px;
    font-weight: 800;
    color: #38bdf8;
  }}
  .table-card {{
    background: #1e293b;
    border-radius: 14px;
    border: 1px solid #334155;
    overflow: hidden;
    box-shadow: 0 4px 12px rgba(0,0,0,0.25);
  }}
  .table-header {{
    padding: 18px 24px;
    border-bottom: 1px solid #334155;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #1e293b;
  }}
  .table-header h2 {{
    margin: 0;
    font-size: 16px;
    color: #f1f5f9;
  }}
  .refresh-btn {{
    font-size: 13px;
    color: #38bdf8;
    text-decoration: none;
    font-weight: 600;
  }}
  .table-scroll {{
    width: 100%;
    overflow-x: auto;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    text-align: left;
    font-size: 13px;
    min-width: 850px;
  }}
  th {{
    background: #0f172a;
    color: #94a3b8;
    padding: 14px 18px;
    border-bottom: 1px solid #334155;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.5px;
  }}
  td {{
    padding: 14px 18px;
    border-bottom: 1px solid #334155;
    vertical-align: middle;
  }}
  tr:hover {{
    background: #253349;
  }}
  .badge {{
    display: inline-block;
    padding: 4px 10px;
    border-radius: 16px;
    font-size: 11px;
    font-weight: 700;
    white-space: nowrap;
  }}
  .badge-id {{ background: #0f172a; color: #38bdf8; border: 1px solid #38bdf8; }}
  .badge-vip {{ background: #701a75; color: #f0abfc; border: 1px solid #c026d3; font-weight: 800; }}
  .badge-hot {{ background: #7c2d12; color: #fdba74; border: 1px solid #ea580c; }}
  .badge-warm {{ background: #713f12; color: #fde047; border: 1px solid #ca8a04; }}
  .score-pill {{
    background: #064e3b;
    color: #6ee7b7;
    padding: 4px 8px;
    border-radius: 12px;
    font-weight: 800;
    font-size: 12px;
  }}
  .budget-badge {{
    background: #0284c7;
    color: #ffffff;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 12px;
  }}
  .btn-wa {{
    background: #25D366;
    color: #ffffff !important;
    text-decoration: none;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }}
  .btn-wa:hover {{ background: #20ba5a; }}
  .mobile-cards-view {{
    display: none;
    padding: 14px;
    gap: 14px;
    flex-direction: column;
  }}
  .lead-card {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .card-head {{ display: flex; justify-content: space-between; align-items: center; }}
  .card-name {{ font-size: 18px; font-weight: 800; color: #f1f5f9; }}
  .meta-box {{
    background: #0f172a;
    padding: 12px;
    border-radius: 8px;
    border: 1px solid #334155;
    font-size: 13px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .meta-row {{ display: flex; justify-content: space-between; }}
  .meta-lbl {{ color: #94a3b8; }}
  .budget-val {{ color: #38bdf8; font-weight: 700; }}
  .btn-wa-full {{
    background: #25D366;
    color: #ffffff !important;
    text-decoration: none;
    padding: 12px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 700;
    text-align: center;
    display: block;
  }}
  @media (max-width: 768px) {{
    .stats-grid {{ grid-template-columns: 1fr; gap: 10px; }}
    .desktop-table-view {{ display: none; }}
    .mobile-cards-view {{ display: flex; }}
    .navbar h1 {{ font-size: 16px; }}
  }}
</style>
</head>
<body>

<div class="navbar">
  <h1>&#127970; {display_agency} &mdash; VIP Lead Pipeline</h1>
  <div class="navbar-broker">&#128100; Broker: {display_broker}</div>
</div>

<div class="container">
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-title">Total Inquiries Qualified</div>
      <div class="stat-val">{total_leads}</div>
    </div>
    <div class="stat-card">
      <div class="stat-title">&#128293; High-Net-Worth VIP Leads</div>
      <div class="stat-val" style="color: #f0abfc;">{vip_leads_count}</div>
    </div>
    <div class="stat-card">
      <div class="stat-title">Speed-To-Lead Status</div>
      <div class="stat-val" style="color: #4ade80; font-size: 20px; padding-top: 6px;">&#128994; Instant AI Active</div>
    </div>
  </div>

  <div class="table-card">
    <div class="table-header">
      <h2>Curated Buyer Pipeline (Ranked by Intent & Budget)</h2>
      <a href="/leads{f'?agency=' + agency if agency else ''}" class="refresh-btn">&#128260; Refresh Pipeline</a>
    </div>

    <div class="desktop-table-view table-scroll">
      <table>
        <thead>
          <tr>
            <th>Ref ID</th>
            <th>Investor Name</th>
            <th>Contact Phone</th>
            <th>Target Community</th>
            <th>Budget (AED)</th>
            <th>Financing</th>
            <th>AI Score</th>
            <th>Buyer Tier</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>

    <div class="mobile-cards-view">
      {cards_html}
    </div>
  </div>
</div>

</body>
</html>"""
    return HTMLResponse(content=html_content, media_type="text/html; charset=utf-8")

# ==================== DENTAL DEMO & DASHBOARD (BACKWARD COMPATIBLE) ====================

@app.get("/demo", response_class=HTMLResponse)
def get_demo_page(clinic: Optional[str] = None, agency: Optional[str] = None, broker: Optional[str] = None, whatsapp: Optional[str] = None, location: Optional[str] = None):
    # If clinic is not specified, ALWAYS serve luxury real estate!
    if not clinic:
        display_agency = agency or "Apex Prime Real Estate"
        display_broker = broker or "Ahmad Al Zaabi"
        display_whatsapp = whatsapp or "+971547400174"
        return get_re_demo(agency=display_agency, broker=display_broker, whatsapp=display_whatsapp)

    # Otherwise dental clinic demo
    display_clinic = clinic
    display_whatsapp = whatsapp or "+971588360378"
    display_loc = location or "Abu Dhabi, UAE"

    import urllib.parse
    enc_clinic = urllib.parse.quote(display_clinic)
    enc_loc = urllib.parse.quote(display_loc)
    dashboard_url = f"/appointments?clinic={enc_clinic}&location={enc_loc}"
    
    demo_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{display_clinic} | Live AI Preview</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #1e293b;
    background: #f8fafc;
  }}
  header {{
    background: #ffffff;
    padding: 16px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #e2e8f0;
    flex-wrap: wrap;
    gap: 12px;
  }}
  .logo {{
    font-size: 20px;
    font-weight: 800;
    color: #0284c7;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .badge-demo {{
    background: #e0f2fe;
    color: #0369a1;
    font-size: 11px;
    font-weight: 700;
    padding: 4px 8px;
    border-radius: 12px;
  }}
  .nav-btn {{
    background: #0284c7;
    color: #ffffff;
    padding: 8px 16px;
    border-radius: 8px;
    text-decoration: none;
    font-size: 13px;
    font-weight: 600;
  }}
  .hero {{
    padding: 48px 20px;
    max-width: 900px;
    margin: 0 auto;
    text-align: center;
  }}
  .hero h1 {{
    font-size: 32px;
    color: #0f172a;
    margin-bottom: 14px;
  }}
  .hero p {{
    font-size: 16px;
    color: #64748b;
    max-width: 650px;
    margin: 0 auto 24px;
    line-height: 1.5;
  }}
  .services-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 20px;
    max-width: 1000px;
    margin: 30px auto 60px;
    padding: 0 20px;
  }}
  .service-card {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 24px;
    text-align: left;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  }}
  .service-icon {{
    font-size: 28px;
    margin-bottom: 12px;
  }}
  .service-title {{
    font-size: 16px;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 6px;
  }}
  .service-desc {{
    font-size: 13px;
    color: #64748b;
    line-height: 1.4;
  }}
  .demo-callout {{
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    color: #166534;
    padding: 14px 20px;
    border-radius: 10px;
    display: inline-block;
    margin-bottom: 24px;
    font-weight: 600;
    font-size: 14px;
  }}
</style>
</head>
<body>

<header>
  <div class="logo">
    <span>&#129463;</span> {display_clinic} <span class="badge-demo">Live AI Preview</span>
  </div>
  <a href="{dashboard_url}" class="nav-btn" target="_blank">&#128203; View Reception Dashboard</a>
</header>

<div class="hero">
  <div class="demo-callout">
    &#10024; Experience your live 24/7 AI Medical Receptionist below!
  </div>
  <h1>Advanced Dental Care & Orthodontics in {display_loc}</h1>
  <p>Providing premier cosmetic dentistry, dental implants, Invisalign, and pediatric dental care with compassionate excellence.</p>
</div>

<div class="services-grid">
  <div class="service-card">
    <div class="service-icon">&#10024;</div>
    <div class="service-title">Cosmetic Teeth Whitening</div>
    <div class="service-desc">Professional in-office whitening and smile makeovers starting from 350 AED.</div>
  </div>
  <div class="service-card">
    <div class="service-icon">&#128522;</div>
    <div class="service-title">Invisalign & Orthodontics</div>
    <div class="service-desc">Certified invisible aligners and discreet orthodontic treatment for adults and teens.</div>
  </div>
  <div class="service-card">
    <div class="service-icon">&#129463;</div>
    <div class="service-title">Dental Implants</div>
    <div class="service-desc">Permanent tooth replacement utilizing state-of-the-art titanium implants.</div>
  </div>
</div>

<!-- EMBEDDED DENTAL AI WIDGET -->
<script 
  src="/widget.js" 
  data-clinic="{display_clinic}" 
  data-whatsapp="{display_whatsapp}">
</script>

</body>
</html>"""
    return HTMLResponse(content=demo_html, media_type="text/html; charset=utf-8")

@app.get("/appointments", response_class=HTMLResponse)
@app.get("/dashboard-dental", response_class=HTMLResponse)
def appointments_dashboard(clinic: Optional[str] = None, location: Optional[str] = None):
    all_bookings = get_clinic_appointments()
    
    if clinic:
        bookings = [b for b in all_bookings if (b.get("clinic_name") or "").strip().lower() == clinic.strip().lower()]
        display_clinic = clinic
    else:
        bookings = all_bookings
        display_clinic = "Al Dhabi Dental Centre"

    display_location = location or ("MBZ City, Abu Dhabi" if "Bloom" in display_clinic else "Mussafah, Abu Dhabi")
    total_bookings = len(bookings)

    rows_html = ""
    cards_html = ""

    for b in reversed(bookings):
        bid = b.get("booking_id", "N/A")
        pname = b.get("patient_name", "Anonymous")
        phone = b.get("phone_number", "")
        clean_phone = "".join(filter(str.isdigit, phone))
        treat = b.get("treatment", "Consultation")
        dtime = b.get("date_time", "Pending")
        booked_at = b.get("booked_at", "")

        wa_msg = f"Hello {pname}, this is {display_clinic} confirming your appointment for {treat} on {dtime}. Please reply YES to confirm."
        import urllib.parse
        wa_link = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_msg)}"

        rows_html += f"""
        <tr>
          <td><span class="badge badge-id">{bid}</span></td>
          <td><strong>{pname}</strong></td>
          <td><a href="tel:{clean_phone}" style="color:#0284c7; text-decoration:none; font-weight:600;">{phone}</a></td>
          <td>{treat}</td>
          <td><span class="badge badge-time">{dtime}</span></td>
          <td style="color:#64748b; font-size:12px;">{booked_at}</td>
          <td><span class="badge badge-confirmed">Confirmed</span></td>
          <td>
            <a href="{wa_link}" target="_blank" class="btn-wa">&#128172; WhatsApp SMS</a>
          </td>
        </tr>
        """

        cards_html += f"""
        <div class="booking-card">
          <div class="card-head">
            <span class="badge badge-id">{bid}</span>
            <span class="badge badge-confirmed">Confirmed</span>
          </div>
          <div class="card-name">{pname}</div>
          <div class="meta-box">
            <div class="meta-row"><span class="meta-lbl">Treatment:</span><strong>{treat}</strong></div>
            <div class="meta-row"><span class="meta-lbl">Requested Time:</span><span style="color:#0284c7; font-weight:700;">{dtime}</span></div>
            <div class="meta-row"><span class="meta-lbl">Phone:</span><a href="tel:{clean_phone}">{phone}</a></div>
          </div>
          <a href="{wa_link}" target="_blank" class="btn-wa-full">&#128172; Send WhatsApp Confirmation</a>
        </div>
        """

    if not rows_html:
        rows_html = "<tr><td colspan='8' style='text-align:center; padding:32px; color:#64748b;'>No patient bookings captured yet.</td></tr>"
        cards_html = "<div style='text-align:center; padding:24px; color:#64748b; background:#fff; border-radius:12px;'>No bookings captured yet.</div>"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>{display_clinic} &mdash; Reception Dashboard</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f8fafc;
    color: #1e293b;
    -webkit-font-smoothing: antialiased;
  }}
  .navbar {{
    background: #ffffff;
    padding: 16px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #e2e8f0;
    flex-wrap: wrap;
    gap: 8px;
  }}
  .navbar h1 {{
    margin: 0;
    font-size: 18px;
    font-weight: 800;
    color: #0284c7;
  }}
  .navbar-status {{
    font-size: 13px;
    background: #dcfce7;
    color: #166534;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: 600;
  }}
  .container {{
    max-width: 1200px;
    margin: 24px auto;
    padding: 0 16px;
  }}
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 24px;
  }}
  .stat-card {{
    background: #ffffff;
    padding: 20px;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  }}
  .stat-title {{
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    margin-bottom: 6px;
  }}
  .stat-val {{
    font-size: 26px;
    font-weight: 800;
    color: #0f172a;
  }}
  .table-card {{
    background: #ffffff;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    overflow: hidden;
  }}
  .table-header {{
    padding: 16px 20px;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .table-header h2 {{
    margin: 0;
    font-size: 16px;
    color: #0f172a;
  }}
  .table-scroll {{
    width: 100%;
    overflow-x: auto;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    text-align: left;
    font-size: 13px;
    min-width: 800px;
  }}
  th {{
    background: #f1f5f9;
    color: #475569;
    padding: 12px 16px;
    border-bottom: 1px solid #e2e8f0;
    font-weight: 600;
  }}
  td {{
    padding: 14px 16px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: middle;
  }}
  .badge {{
    display: inline-block;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
  }}
  .badge-id {{ background: #f1f5f9; color: #475569; font-family: monospace; }}
  .badge-confirmed {{ background: #dcfce7; color: #166534; }}
  .badge-time {{ background: #e0f2fe; color: #0369a1; font-weight: 700; }}
  .btn-wa {{
    background: #25D366;
    color: #ffffff !important;
    text-decoration: none;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
  }}
  .mobile-cards-view {{
    display: none;
    padding: 12px;
    gap: 12px;
    flex-direction: column;
  }}
  .booking-card {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}
  .card-head {{ display: flex; justify-content: space-between; }}
  .card-name {{ font-size: 16px; font-weight: 700; }}
  .meta-box {{
    background: #f8fafc;
    padding: 10px;
    border-radius: 8px;
    font-size: 13px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}
  .meta-row {{ display: flex; justify-content: space-between; }}
  .meta-lbl {{ color: #64748b; }}
  .btn-wa-full {{
    background: #25D366;
    color: #ffffff !important;
    text-decoration: none;
    padding: 10px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    text-align: center;
  }}
  @media (max-width: 768px) {{
    .stats-grid {{ grid-template-columns: 1fr; }}
    .desktop-table-view {{ display: none; }}
    .mobile-cards-view {{ display: flex; }}
  }}
</style>
</head>
<body>

<div class="navbar">
  <h1>&#129463; {display_clinic} &mdash; Reception Dashboard</h1>
  <div class="navbar-status">&#9679; 24/7 AI Receptionist: Active</div>
</div>

<div class="container">
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-title">Total Bookings Captured</div>
      <div class="stat-val">{total_bookings}</div>
    </div>
    <div class="stat-card">
      <div class="stat-title">Location</div>
      <div class="stat-val" style="font-size: 16px; font-weight: 700;">{display_location}</div>
    </div>
    <div class="stat-card">
      <div class="stat-title">AI Status</div>
      <div class="stat-val" style="font-size: 16px; color: #16a34a; font-weight: 700;">100% Online</div>
    </div>
  </div>

  <div class="table-card">
    <div class="table-header">
      <h2>Recent Patient Bookings (Live Schedule)</h2>
      <a href="/appointments{f'?clinic=' + clinic if clinic else ''}" style="font-size: 13px; color: #0284c7; text-decoration: none; font-weight: 600;">&#128260; Refresh Table</a>
    </div>

    <div class="desktop-table-view table-scroll">
      <table>
        <thead>
          <tr>
            <th>Booking ID</th>
            <th>Patient Name</th>
            <th>Phone</th>
            <th>Treatment</th>
            <th>Requested Date & Time</th>
            <th>Time Booked</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>

    <div class="mobile-cards-view">
      {cards_html}
    </div>
  </div>
</div>

</body>
</html>"""
    return HTMLResponse(content=html_content, media_type="text/html; charset=utf-8")
