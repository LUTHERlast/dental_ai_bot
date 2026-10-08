import os
import json
import re
import urllib.parse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

# Load root .env
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

app = FastAPI(title="Apex Luxury Real Estate AI Platform - Dubai and Abu Dhabi")

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
    """Redirects visitors directly to the Luxury Real Estate Agency Demo preview."""
    return RedirectResponse(url="/demo", status_code=302)

@app.get("/status")
def api_status():
    return {
        "status": "online",
        "platform": "Apex Luxury Real Estate AI Advisor",
        "market": "UAE (Dubai and Abu Dhabi)",
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
  let serverUrl = "https://apex-luxury-ai.onrender.com";
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

# ==================== REAL ESTATE CLIENT PORTAL & BROKER DEMO ====================

def build_client_portal_html(agency: str, broker: str, whatsapp: str) -> str:
    import urllib.parse
    enc_agency = urllib.parse.quote(agency)
    enc_broker = urllib.parse.quote(broker)
    clean_wa = re.sub(r'[^0-9]', '', whatsapp or "971547400174")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{agency} | Exclusive Luxury Residences Abu Dhabi & Dubai</title>
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
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .tagline {{
    font-size: 11px;
    color: #38bdf8;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 600;
  }}
  .btn-wa {{
    background: #25D366;
    color: #ffffff;
    padding: 9px 20px;
    border-radius: 8px;
    text-decoration: none;
    font-size: 13px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 14px rgba(37, 211, 102, 0.3);
  }}
  .btn-wa:hover {{ background: #22c35e; }}
  .hero {{
    padding: 60px 24px 40px;
    max-width: 960px;
    margin: 0 auto;
    text-align: center;
  }}
  .hero-badge {{
    display: inline-block;
    background: rgba(234, 179, 8, 0.12);
    color: #facc15;
    border: 1px solid #ca8a04;
    padding: 6px 18px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 800;
    margin-bottom: 18px;
    letter-spacing: 1.2px;
  }}
  .hero h1 {{
    font-size: 40px;
    margin: 0 0 16px;
    font-weight: 800;
    line-height: 1.25;
    background: linear-gradient(135deg, #ffffff, #94a3b8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .hero p {{
    font-size: 16px;
    color: #94a3b8;
    max-width: 680px;
    margin: 0 auto 26px;
    line-height: 1.6;
  }}
  .properties-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 24px;
    max-width: 1100px;
    margin: 20px auto 80px;
    padding: 0 20px;
  }}
  .prop-card {{
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 16px;
    overflow: hidden;
    transition: transform 0.2s, border-color 0.2s;
  }}
  .prop-card:hover {{ transform: translateY(-4px); border-color: #38bdf8; }}
  .prop-img {{
    height: 180px;
    background: linear-gradient(135deg, #1e293b, #0f172a);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 48px;
  }}
  .prop-info {{ padding: 20px; }}
  .prop-loc {{ font-size: 11px; color: #38bdf8; font-weight: 700; text-transform: uppercase; }}
  .prop-title {{ font-size: 18px; font-weight: 700; margin: 6px 0; color: #ffffff; }}
  .prop-price {{ font-size: 16px; font-weight: 800; color: #4ade80; margin-bottom: 8px; }}
  .prop-desc {{ font-size: 13px; color: #94a3b8; line-height: 1.5; margin-bottom: 16px; }}
  .prop-cta {{
    display: block;
    text-align: center;
    background: #1e293b;
    color: #38bdf8;
    border: 1px solid #334155;
    padding: 10px;
    border-radius: 8px;
    text-decoration: none;
    font-size: 13px;
    font-weight: 700;
  }}
  .prop-cta:hover {{ background: #25D366; color: #ffffff; border-color: #25D366; }}
</style>
</head>
<body>

<header>
  <div>
    <div class="logo">&#127963; {agency}</div>
    <div class="tagline">Private Client Real Estate Advisory</div>
  </div>
  <a href="https://wa.me/{clean_wa}?text=Hello%20{enc_broker},%20I%20am%20inquiring%20about%20your%20luxury%20residences" class="btn-wa" target="_blank">&#128172; WhatsApp {broker}</a>
</header>

<div class="hero">
  <div class="hero-badge">&#11088; PRIVATE CLIENT LUXURY SHOWCASE</div>
  <h1>Luxury Waterfront &amp; Golf Residences in UAE</h1>
  <p>Curated portfolio of prime villas, penthouses, and high-yield off-plan developments across Saadiyat Island, Yas Island, and Palm Jumeirah. Eligible for 10-Year UAE Golden Visa.</p>
</div>

<div class="properties-grid">
  <div class="prop-card">
    <div class="prop-img">&#127958;</div>
    <div class="prop-info">
      <div class="prop-loc">Saadiyat Island &bull; Abu Dhabi</div>
      <div class="prop-title">Beachfront Luxury Villas</div>
      <div class="prop-price">From 4,800,000 AED</div>
      <div class="prop-desc">Exclusive private enclave by Aldar with private beach access and proximity to the Louvre Abu Dhabi.</div>
      <a href="https://wa.me/{clean_wa}?text=Hello%20{enc_broker},%20please%20send%20brochure%20for%20Saadiyat%20Beachfront%20Villas" class="prop-cta" target="_blank">&#128172; Inquire on WhatsApp</a>
    </div>
  </div>

  <div class="prop-card">
    <div class="prop-img">&#127961;</div>
    <div class="prop-info">
      <div class="prop-loc">Downtown Dubai</div>
      <div class="prop-title">Opera District Residences</div>
      <div class="prop-price">From 2,400,000 AED</div>
      <div class="prop-desc">High-floor luxury suites with direct Burj Khalifa panoramas and high short-term rental yields (8.5%+).</div>
      <a href="https://wa.me/{clean_wa}?text=Hello%20{enc_broker},%20please%20send%20brochure%20for%20Downtown%20Opera%20District" class="prop-cta" target="_blank">&#128172; Inquire on WhatsApp</a>
    </div>
  </div>

  <div class="prop-card">
    <div class="prop-img">&#9971;</div>
    <div class="prop-info">
      <div class="prop-loc">Yas Island &bull; Abu Dhabi</div>
      <div class="prop-title">Yas Acres Golf Townhouses</div>
      <div class="prop-price">From 2,100,000 AED</div>
      <div class="prop-desc">9-hole championship golf course community with international schools and marina waterfront.</div>
      <a href="https://wa.me/{clean_wa}?text=Hello%20{enc_broker},%20please%20send%20brochure%20for%20Yas%20Acres%20Golf%20Townhouses" class="prop-cta" target="_blank">&#128172; Inquire on WhatsApp</a>
    </div>
  </div>
</div>

<script src="/re-widget.js" data-agency="{agency}" data-broker="{broker}" data-whatsapp="{whatsapp}"></script>
</body>
</html>"""


def build_broker_demo_html(agency: str, broker: str, whatsapp: str) -> str:
    import urllib.parse
    enc_agency = urllib.parse.quote(agency)
    enc_broker = urllib.parse.quote(broker)
    clean_wa = re.sub(r'[^0-9]', '', whatsapp or "971547400174")
    dashboard_url = f"/leads?agency={enc_agency}&broker={enc_broker}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{agency} | AI Property Advisor Demo</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #090d16;
    color: #f8fafc;
  }}
  .broker-eval-bar {{
    background: linear-gradient(90deg, #0369a1, #0284c7);
    padding: 12px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    font-weight: 700;
    color: #ffffff;
    border-bottom: 1px solid #38bdf8;
    flex-wrap: wrap;
    gap: 12px;
  }}
  .eval-pipe-btn {{
    background: #0f172a;
    color: #38bdf8;
    border: 1px solid #38bdf8;
    padding: 6px 16px;
    border-radius: 6px;
    text-decoration: none;
    font-size: 12px;
    font-weight: 800;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }}
  .eval-pipe-btn:hover {{ background: #1e293b; color: #ffffff; }}
  header {{
    background: rgba(15, 23, 42, 0.95);
    padding: 16px 36px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #1e293b;
  }}
  .logo {{
    font-size: 20px;
    font-weight: 800;
    color: #38bdf8;
  }}
  .tagline {{
    font-size: 11px;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 1.5px;
  }}
  .hero {{
    padding: 50px 24px 30px;
    max-width: 900px;
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
    font-weight: 800;
    margin-bottom: 18px;
    letter-spacing: 1px;
  }}
  .hero h1 {{
    font-size: 38px;
    margin: 0 0 16px;
    font-weight: 800;
    line-height: 1.25;
    background: linear-gradient(135deg, #ffffff, #94a3b8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .hero p {{
    font-size: 16px;
    color: #94a3b8;
    max-width: 720px;
    margin: 0 auto 24px;
    line-height: 1.6;
  }}
  .test-box {{
    background: #0f172a;
    border: 2px dashed #0284c7;
    border-radius: 14px;
    padding: 22px;
    max-width: 680px;
    margin: 0 auto 40px;
    text-align: left;
    box-shadow: 0 8px 30px rgba(0,0,0,0.4);
  }}
  .test-title {{
    font-size: 13px;
    font-weight: 800;
    color: #38bdf8;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .test-item {{
    background: #1e293b;
    border: 1px solid #334155;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 13px;
    color: #f1f5f9;
    margin-bottom: 8px;
    cursor: pointer;
    transition: all 0.2s;
  }}
  .test-item:hover {{ border-color: #38bdf8; background: #334155; }}
</style>
</head>
<body>

<div class="broker-eval-bar">
  <div>💼 <strong>BROKER EVALUATION MODE:</strong> Test how your custom AI Advisor qualifies 5M+ AED buyers and handles objections 24/7 on your listings.</div>
  <a href="{dashboard_url}" class="eval-pipe-btn" target="_blank">&#128202; View Live CRM Pipeline &rarr;</a>
</div>

<header>
  <div>
    <div class="logo">&#127963; {agency}</div>
    <div class="tagline">AI Property Advisor Interactive Preview</div>
  </div>
  <a href="{dashboard_url}" class="eval-pipe-btn" target="_blank">&#128202; View Broker Pipeline</a>
</header>

<div class="hero">
  <div class="hero-badge">&#129302; 20-SECOND AI LEAD-QUALIFIER TEST</div>
  <h1>Experience Your Agency's AI Property Advisor</h1>
  <p>When high-net-worth buyers inquire after 7 PM or from overseas (London, Europe, India), this AI pre-qualifies their liquid budget, mortgage vs. cash, and 10-Yr Golden Visa timeline, then hands the qualified lead directly to your WhatsApp.</p>

  <div class="test-box">
    <div class="test-title">&#128073; Tap any prompt below to test Aria live:</div>
    <div class="test-item" onclick="simulatePrompt(this.innerText)">"I have a 6M AED cash budget looking for a luxury beachfront villa in Saadiyat Island"</div>
    <div class="test-item" onclick="simulatePrompt(this.innerText)">"What are the payment plans and 10-Year Golden Visa requirements for Aldar off-plan?"</div>
    <div class="test-item" onclick="simulatePrompt(this.innerText)">"Can you send the brochure directly to my WhatsApp?"</div>
  </div>
</div>

<script src="/re-widget.js" data-agency="{agency}" data-broker="{broker}" data-whatsapp="{whatsapp}"></script>

<script>
function simulatePrompt(text) {{
  const win = document.getElementById("re-chat-window");
  const bubble = document.getElementById("re-chat-bubble");
  if (win && win.style.display !== "flex" && bubble) {{
    bubble.click();
  }}
  const input = document.getElementById("re-chat-input");
  if (input) {{
    input.value = text;
    input.focus();
  }}
}}

// Automatically trigger open after 1.2s for frictionless broker test
setTimeout(function() {{
  const win = document.getElementById("re-chat-window");
  const bubble = document.getElementById("re-chat-bubble");
  if (win && win.style.display !== "flex" && bubble) {{
    bubble.click();
  }}
}}, 1200);
</script>

</body>
</html>"""

CLICK_LOG_FILES = [
    Path(__file__).resolve().parent / "lead_clicks.json",
    Path(__file__).resolve().parent.parent / "outputs" / "lead_clicks.json"
]

def record_remote_click(
    agency: Optional[str] = None,
    broker: Optional[str] = None,
    route: str = "/demo",
    client_ip: str = "",
    user_agent: str = ""
):
    """
    Safely logs incoming clicks on Render or local server,
    and automatically upgrades the matched lead status to CLICKED in CRM.
    """
    if not agency:
        return
    clean_agency = str(agency).strip()
    if clean_agency.lower() in ["apex prime real estate", "null", "undefined", ""]:
        return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    click_entry = {
        "agency": clean_agency,
        "broker": str(broker or "").strip(),
        "route": route,
        "timestamp": now_str,
        "ip": client_ip,
        "user_agent": user_agent[:120] if user_agent else "",
        "count": 1
    }

    # 1. Append to clicks file
    for p in CLICK_LOG_FILES:
        try:
            clicks = []
            if p.exists():
                try:
                    clicks = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    clicks = []
            clicks.insert(0, click_entry)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(clicks[:500], indent=2, ensure_ascii=False), encoding="utf-8")
            break
        except Exception as e:
            logger.warning(f"Failed to write click log to {p}: {e}")

    # 2. Update CRM database entry
    try:
        crm = get_crm_database()
        updated = False
        for lead in crm:
            lead_ag = (lead.get("agency_name") or "").strip().lower()
            if clean_agency.lower() in lead_ag or lead_ag in clean_agency.lower():
                lead["status"] = "CLICKED"
                lead["last_clicked_at"] = now_str
                lead["click_count"] = (lead.get("click_count") or 0) + 1
                routes = lead.get("clicked_routes") or []
                if route not in routes:
                    routes.append(route)
                lead["clicked_routes"] = routes
                updated = True
        if updated:
            save_crm_database(crm)
    except Exception as e:
        logger.warning(f"Failed to auto-update CRM lead status on click: {e}")

@app.get("/portal", response_class=HTMLResponse)
@app.get("/vip", response_class=HTMLResponse)
@app.get("/showcase", response_class=HTMLResponse)
def get_client_portal(
    request: Request,
    agency: Optional[str] = "Apex Prime Real Estate",
    broker: Optional[str] = "Ahmad Al Zaabi",
    whatsapp: Optional[str] = "+971547400174"
):
    client_ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    try:
        record_remote_click(agency=agency, broker=broker, route="/portal", client_ip=client_ip, user_agent=ua)
    except Exception as ex:
        logger.warning(f"Error logging portal click: {ex}")

    try:
        display_agency = str(agency or "Apex Prime Real Estate").strip()
        display_broker = str(broker or "Ahmad Al Zaabi").strip()
        display_whatsapp = str(whatsapp or "+971547400174").strip()
        return HTMLResponse(content=build_client_portal_html(agency=display_agency, broker=display_broker, whatsapp=display_whatsapp), media_type="text/html; charset=utf-8")
    except Exception as e:
        logger.error(f"Error in get_client_portal: {e}")
        return HTMLResponse(content=build_client_portal_html(agency="Apex Prime Real Estate", broker="Ahmad Al Zaabi", whatsapp="+971547400174"), media_type="text/html; charset=utf-8")

@app.get("/re/demo", response_class=HTMLResponse)
@app.get("/realestate", response_class=HTMLResponse)
def get_re_demo_page(
    request: Request,
    agency: Optional[str] = "Apex Prime Real Estate",
    broker: Optional[str] = "Ahmad Al Zaabi",
    whatsapp: Optional[str] = "+971547400174"
):
    client_ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    try:
        record_remote_click(agency=agency, broker=broker, route="/demo", client_ip=client_ip, user_agent=ua)
    except Exception as ex:
        logger.warning(f"Error logging re demo click: {ex}")

    try:
        display_agency = str(agency or "Apex Prime Real Estate").strip()
        display_broker = str(broker or "Ahmad Al Zaabi").strip()
        display_whatsapp = str(whatsapp or "+971547400174").strip()
        return HTMLResponse(content=build_broker_demo_html(agency=display_agency, broker=display_broker, whatsapp=display_whatsapp), media_type="text/html; charset=utf-8")
    except Exception as e:
        logger.error(f"Error in get_re_demo_page: {e}")
        return HTMLResponse(content=build_broker_demo_html(agency="Apex Prime Real Estate", broker="Ahmad Al Zaabi", whatsapp="+971547400174"), media_type="text/html; charset=utf-8")



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
def get_demo_page(
    request: Request,
    clinic: Optional[str] = None, 
    agency: Optional[str] = None, 
    broker: Optional[str] = None, 
    whatsapp: Optional[str] = None, 
    location: Optional[str] = None, 
    mode: Optional[str] = "demo"
):
    client_ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")

    # If clinic is not specified, ALWAYS serve luxury real estate!
    if not clinic:
        try:
            record_remote_click(agency=agency, broker=broker, route="/demo", client_ip=client_ip, user_agent=ua)
        except Exception as ex:
            logger.warning(f"Error logging demo click: {ex}")

        try:
            display_agency = str(agency or "Apex Prime Real Estate").strip()
            display_broker = str(broker or "Ahmad Al Zaabi").strip()
            display_whatsapp = str(whatsapp or "+971547400174").strip()
            return HTMLResponse(content=build_broker_demo_html(agency=display_agency, broker=display_broker, whatsapp=display_whatsapp), media_type="text/html; charset=utf-8")
        except Exception as e:
            logger.error(f"Error generating broker demo HTML: {e}")
            return HTMLResponse(content=build_broker_demo_html(agency="Apex Prime Real Estate", broker="Ahmad Al Zaabi", whatsapp="+971547400174"), media_type="text/html; charset=utf-8")

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

# ==================== AUTONOMOUS CLIENT ACQUISITION & CRM SYSTEM ====================

def _resolve_crm_files():
    base = Path(__file__).resolve().parent
    candidates = [
        base / "outreach_crm.json",
        base.parent / "outputs" / "outreach_crm.json",
        base.parent.parent / "dental_ai_bot_clone" / "outreach_crm.json"
    ]
    return candidates

DEFAULT_MASTER_LEADS = json.loads(r'''[
  {
    "lead_id": "UAE-RE-01",
    "agency_name": "Crompton Partners Estate Agents",
    "broker_name": "Benjamin Crompton",
    "phone": "+971 50 123 4567",
    "phone_clean": "971501234567",
    "territory": "Saadiyat Island & Yas Island (Abu Dhabi)",
    "niche": "Beachfront Luxury Villas (Aldar Developments)",
    "demo_url": "https://apex-properties-ai.onrender.com/demo?agency=Crompton%20Partners%20Estate%20Agents&broker=Benjamin%20Crompton&whatsapp=%2B971%2050%20123%204567",
    "dash_url": "https://apex-properties-ai.onrender.com/leads?agency=Crompton%20Partners%20Estate%20Agents&broker=Benjamin%20Crompton",
    "status": "DISCOVERED",
    "discovered_at": "2026-10-05 20:00:00",
    "last_contacted_at": null,
    "next_followup_at": null,
    "messages": {
      "initial": "Hello Benjamin,\n\nI noticed your luxury listings in Saadiyat Island & Yas Island (Abu Dhabi) on Bayut and Property Finder.\n\nWhen high-net-worth buyers inquire after 7 PM or from overseas (London, Europe, India), competing brokers often lock in viewings before morning follow-ups happen.\n\nTo help Crompton Partners Estate Agents eliminate this drop-off and filter out tire-kickers, I built a personalized AI Property Advisor tailored for your agency:\n\n📱 Test the live buyer experience on your phone (takes 20 seconds):\n👉 https://apex-properties-ai.onrender.com/demo?agency=Crompton%20Partners%20Estate%20Agents&broker=Benjamin%20Crompton&whatsapp=%2B971%2050%20123%204567\n(Tap the glowing blue chat bubble at the bottom right)\n\n📊 View your live qualified investor pipeline:\n👉 https://apex-properties-ai.onrender.com/leads?agency=Crompton%20Partners%20Estate%20Agents&broker=Benjamin%20Crompton\n\nWhat it does for Crompton Partners Estate Agents:\n• Instant 24/7 qualification for 5M+ AED cash buyers & 10-Yr Golden Visa investors\n• Filters out time-wasters so your team only spends time with serious buyers\n• 1-click WhatsApp brochure handoff directly to your mobile\n\nWould you like to test a 7-day free trial on your active listings this week? Zero upfront payment required.\n\nBest regards,\nAthul Raj\nAI Automation Specialist — UAE\nWhatsApp: +971 54 740 0174",
      "followup1": "Hello Benjamin,\n\nQuick follow-up regarding the custom AI Advisor for Crompton Partners Estate Agents.\n\nDid you get 20 seconds to test the demo on your phone?\n👉 https://apex-properties-ai.onrender.com/demo?agency=Crompton%20Partners%20Estate%20Agents&broker=Benjamin%20Crompton&whatsapp=%2B971%2050%20123%204567\n\nA broker in Abu Dhabi tested it yesterday and had an investor qualified for a 6.2M AED beachfront villa inquiry at 11:30 PM with zero manual effort.\n\nWould you like us to activate the 7-Day Free Trial for your team this week?",
      "followup2": "Hi Benjamin,\n\nI assume you are currently busy closing deals in Saadiyat Island & Yas Island (Abu Dhabi).\n\nI don't want to clutter your inbox. Should I close your 7-day trial file for Crompton Partners Estate Agents, or would you like a 5-minute walk-through on how to automate your speed-to-lead?"
    }
  },
  {
    "lead_id": "UAE-RE-02",
    "agency_name": "Metropolitan Capital Real Estate",
    "broker_name": "Evgeny Ratskevich",
    "phone": "+971 54 740 0174",
    "phone_clean": "971547400174",
    "territory": "Downtown Dubai & Saadiyat",
    "niche": "Off-Plan & 10-Yr Golden Visa Portfolios",
    "demo_url": "https://apex-properties-ai.onrender.com/demo?agency=Metropolitan%20Capital%20Real%20Estate&broker=Evgeny%20Ratskevich&whatsapp=%2B971%2054%20740%200174",
    "dash_url": "https://apex-properties-ai.onrender.com/leads?agency=Metropolitan%20Capital%20Real%20Estate&broker=Evgeny%20Ratskevich",
    "status": "DISCOVERED",
    "discovered_at": "2026-10-05 20:00:00",
    "last_contacted_at": null,
    "next_followup_at": null,
    "messages": {
      "initial": "Hello Evgeny,\n\nI noticed your luxury listings in Downtown Dubai & Saadiyat on Bayut and Property Finder.\n\nWhen high-net-worth buyers inquire after 7 PM or from overseas (London, Europe, India), competing brokers often lock in viewings before morning follow-ups happen.\n\nTo help Metropolitan Capital Real Estate eliminate this drop-off and filter out tire-kickers, I built a personalized AI Property Advisor tailored for your agency:\n\n📱 Test the live buyer experience on your phone (takes 20 seconds):\n👉 https://apex-properties-ai.onrender.com/demo?agency=Metropolitan%20Capital%20Real%20Estate&broker=Evgeny%20Ratskevich&whatsapp=%2B971%2054%20740%200174\n(Tap the glowing blue chat bubble at the bottom right)\n\n📊 View your live qualified investor pipeline:\n👉 https://apex-properties-ai.onrender.com/leads?agency=Metropolitan%20Capital%20Real%20Estate&broker=Evgeny%20Ratskevich\n\nWhat it does for Metropolitan Capital Real Estate:\n• Instant 24/7 qualification for 5M+ AED cash buyers & 10-Yr Golden Visa investors\n• Filters out time-wasters so your team only spends time with serious buyers\n• 1-click WhatsApp brochure handoff directly to your mobile\n\nWould you like to test a 7-day free trial on your active listings this week? Zero upfront payment required.\n\nBest regards,\nAthul Raj\nAI Automation Specialist — UAE\nWhatsApp: +971 54 740 0174",
      "followup1": "Hello Evgeny,\n\nQuick follow-up regarding the custom AI Advisor for Metropolitan Capital Real Estate.\n\nDid you get 20 seconds to test the demo on your phone?\n👉 https://apex-properties-ai.onrender.com/demo?agency=Metropolitan%20Capital%20Real%20Estate&broker=Evgeny%20Ratskevich&whatsapp=%2B971%2054%20740%200174\n\nA broker in Abu Dhabi tested it yesterday and had an investor qualified for a 6.2M AED beachfront villa inquiry at 11:30 PM with zero manual effort.\n\nWould you like us to activate the 7-Day Free Trial for your team this week?",
      "followup2": "Hi Evgeny,\n\nI assume you are currently busy closing deals in Downtown Dubai & Saadiyat.\n\nI don't want to clutter your inbox. Should I close your 7-day trial file for Metropolitan Capital Real Estate, or would you like a 5-minute walk-through on how to automate your speed-to-lead?"
    }
  },
  {
    "lead_id": "UAE-RE-03",
    "agency_name": "Abubakr Real Estate Advisory",
    "broker_name": "Abubakr Siddiq",
    "phone": "+971 52 114 4517",
    "phone_clean": "971521144517",
    "territory": "Palm Jumeirah & Sheikh Zayed Road",
    "niche": "Waterfront Luxury Penthouses",
    "demo_url": "https://apex-properties-ai.onrender.com/demo?agency=Abubakr%20Real%20Estate%20Advisory&broker=Abubakr%20Siddiq&whatsapp=%2B971%2052%20114%204517",
    "dash_url": "https://apex-properties-ai.onrender.com/leads?agency=Abubakr%20Real%20Estate%20Advisory&broker=Abubakr%20Siddiq",
    "status": "DISCOVERED",
    "discovered_at": "2026-10-05 20:00:00",
    "last_contacted_at": null,
    "next_followup_at": null,
    "messages": {
      "initial": "Hello Abubakr,\n\nI noticed your luxury listings in Palm Jumeirah & Sheikh Zayed Road on Bayut and Property Finder.\n\nWhen high-net-worth buyers inquire after 7 PM or from overseas (London, Europe, India), competing brokers often lock in viewings before morning follow-ups happen.\n\nTo help Abubakr Real Estate Advisory eliminate this drop-off and filter out tire-kickers, I built a personalized AI Property Advisor tailored for your agency:\n\n📱 Test the live buyer experience on your phone (takes 20 seconds):\n👉 https://apex-properties-ai.onrender.com/demo?agency=Abubakr%20Real%20Estate%20Advisory&broker=Abubakr%20Siddiq&whatsapp=%2B971%2052%20114%204517\n(Tap the glowing blue chat bubble at the bottom right)\n\n📊 View your live qualified investor pipeline:\n👉 https://apex-properties-ai.onrender.com/leads?agency=Abubakr%20Real%20Estate%20Advisory&broker=Abubakr%20Siddiq\n\nWhat it does for Abubakr Real Estate Advisory:\n• Instant 24/7 qualification for 5M+ AED cash buyers & 10-Yr Golden Visa investors\n• Filters out time-wasters so your team only spends time with serious buyers\n• 1-click WhatsApp brochure handoff directly to your mobile\n\nWould you like to test a 7-day free trial on your active listings this week? Zero upfront payment required.\n\nBest regards,\nAthul Raj\nAI Automation Specialist — UAE\nWhatsApp: +971 54 740 0174",
      "followup1": "Hello Abubakr,\n\nQuick follow-up regarding the custom AI Advisor for Abubakr Real Estate Advisory.\n\nDid you get 20 seconds to test the demo on your phone?\n👉 https://apex-properties-ai.onrender.com/demo?agency=Abubakr%20Real%20Estate%20Advisory&broker=Abubakr%20Siddiq&whatsapp=%2B971%2052%20114%204517\n\nA broker in Abu Dhabi tested it yesterday and had an investor qualified for a 6.2M AED beachfront villa inquiry at 11:30 PM with zero manual effort.\n\nWould you like us to activate the 7-Day Free Trial for your team this week?",
      "followup2": "Hi Abubakr,\n\nI assume you are currently busy closing deals in Palm Jumeirah & Sheikh Zayed Road.\n\nI don't want to clutter your inbox. Should I close your 7-day trial file for Abubakr Real Estate Advisory, or would you like a 5-minute walk-through on how to automate your speed-to-lead?"
    }
  },
  {
    "lead_id": "UAE-RE-04",
    "agency_name": "Premium Real Estate Dubai",
    "broker_name": "Tariq Al-Hashemi",
    "phone": "+971 50 269 1859",
    "phone_clean": "971502691859",
    "territory": "Dubai Hills Estate & Business Bay",
    "niche": "Golf Course Mansions & High-Yield Apartments",
    "demo_url": "https://apex-properties-ai.onrender.com/demo?agency=Premium%20Real%20Estate%20Dubai&broker=Tariq%20Al-Hashemi&whatsapp=%2B971%2050%20269%201859",
    "dash_url": "https://apex-properties-ai.onrender.com/leads?agency=Premium%20Real%20Estate%20Dubai&broker=Tariq%20Al-Hashemi",
    "status": "DISCOVERED",
    "discovered_at": "2026-10-05 20:00:00",
    "last_contacted_at": null,
    "next_followup_at": null,
    "messages": {
      "initial": "Hello Tariq,\n\nI noticed your luxury listings in Dubai Hills Estate & Business Bay on Bayut and Property Finder.\n\nWhen high-net-worth buyers inquire after 7 PM or from overseas (London, Europe, India), competing brokers often lock in viewings before morning follow-ups happen.\n\nTo help Premium Real Estate Dubai eliminate this drop-off and filter out tire-kickers, I built a personalized AI Property Advisor tailored for your agency:\n\n📱 Test the live buyer experience on your phone (takes 20 seconds):\n👉 https://apex-properties-ai.onrender.com/demo?agency=Premium%20Real%20Estate%20Dubai&broker=Tariq%20Al-Hashemi&whatsapp=%2B971%2050%20269%201859\n(Tap the glowing blue chat bubble at the bottom right)\n\n📊 View your live qualified investor pipeline:\n👉 https://apex-properties-ai.onrender.com/leads?agency=Premium%20Real%20Estate%20Dubai&broker=Tariq%20Al-Hashemi\n\nWhat it does for Premium Real Estate Dubai:\n• Instant 24/7 qualification for 5M+ AED cash buyers & 10-Yr Golden Visa investors\n• Filters out time-wasters so your team only spends time with serious buyers\n• 1-click WhatsApp brochure handoff directly to your mobile\n\nWould you like to test a 7-day free trial on your active listings this week? Zero upfront payment required.\n\nBest regards,\nAthul Raj\nAI Automation Specialist — UAE\nWhatsApp: +971 54 740 0174",
      "followup1": "Hello Tariq,\n\nQuick follow-up regarding the custom AI Advisor for Premium Real Estate Dubai.\n\nDid you get 20 seconds to test the demo on your phone?\n👉 https://apex-properties-ai.onrender.com/demo?agency=Premium%20Real%20Estate%20Dubai&broker=Tariq%20Al-Hashemi&whatsapp=%2B971%2050%20269%201859\n\nA broker in Abu Dhabi tested it yesterday and had an investor qualified for a 6.2M AED beachfront villa inquiry at 11:30 PM with zero manual effort.\n\nWould you like us to activate the 7-Day Free Trial for your team this week?",
      "followup2": "Hi Tariq,\n\nI assume you are currently busy closing deals in Dubai Hills Estate & Business Bay.\n\nI don't want to clutter your inbox. Should I close your 7-day trial file for Premium Real Estate Dubai, or would you like a 5-minute walk-through on how to automate your speed-to-lead?"
    }
  },
  {
    "lead_id": "UAE-RE-05",
    "agency_name": "NAS Luxury Real Estate",
    "broker_name": "Nasser Al-Suwaidi",
    "phone": "+971 50 888 1234",
    "phone_clean": "971508881234",
    "territory": "Al Reem Island & Cultural District",
    "niche": "Private Client Waterfront Residences",
    "demo_url": "https://apex-properties-ai.onrender.com/demo?agency=NAS%20Luxury%20Real%20Estate&broker=Nasser%20Al-Suwaidi&whatsapp=%2B971%2050%20888%201234",
    "dash_url": "https://apex-properties-ai.onrender.com/leads?agency=NAS%20Luxury%20Real%20Estate&broker=Nasser%20Al-Suwaidi",
    "status": "DISCOVERED",
    "discovered_at": "2026-10-05 20:00:00",
    "last_contacted_at": null,
    "next_followup_at": null,
    "messages": {
      "initial": "Hello Nasser,\n\nI noticed your luxury listings in Al Reem Island & Cultural District on Bayut and Property Finder.\n\nWhen high-net-worth buyers inquire after 7 PM or from overseas (London, Europe, India), competing brokers often lock in viewings before morning follow-ups happen.\n\nTo help NAS Luxury Real Estate eliminate this drop-off and filter out tire-kickers, I built a personalized AI Property Advisor tailored for your agency:\n\n📱 Test the live buyer experience on your phone (takes 20 seconds):\n👉 https://apex-properties-ai.onrender.com/demo?agency=NAS%20Luxury%20Real%20Estate&broker=Nasser%20Al-Suwaidi&whatsapp=%2B971%2050%20888%201234\n(Tap the glowing blue chat bubble at the bottom right)\n\n📊 View your live qualified investor pipeline:\n👉 https://apex-properties-ai.onrender.com/leads?agency=NAS%20Luxury%20Real%20Estate&broker=Nasser%20Al-Suwaidi\n\nWhat it does for NAS Luxury Real Estate:\n• Instant 24/7 qualification for 5M+ AED cash buyers & 10-Yr Golden Visa investors\n• Filters out time-wasters so your team only spends time with serious buyers\n• 1-click WhatsApp brochure handoff directly to your mobile\n\nWould you like to test a 7-day free trial on your active listings this week? Zero upfront payment required.\n\nBest regards,\nAthul Raj\nAI Automation Specialist — UAE\nWhatsApp: +971 54 740 0174",
      "followup1": "Hello Nasser,\n\nQuick follow-up regarding the custom AI Advisor for NAS Luxury Real Estate.\n\nDid you get 20 seconds to test the demo on your phone?\n👉 https://apex-properties-ai.onrender.com/demo?agency=NAS%20Luxury%20Real%20Estate&broker=Nasser%20Al-Suwaidi&whatsapp=%2B971%2050%20888%201234\n\nA broker in Abu Dhabi tested it yesterday and had an investor qualified for a 6.2M AED beachfront villa inquiry at 11:30 PM with zero manual effort.\n\nWould you like us to activate the 7-Day Free Trial for your team this week?",
      "followup2": "Hi Nasser,\n\nI assume you are currently busy closing deals in Al Reem Island & Cultural District.\n\nI don't want to clutter your inbox. Should I close your 7-day trial file for NAS Luxury Real Estate, or would you like a 5-minute walk-through on how to automate your speed-to-lead?"
    }
  },
  {
    "lead_id": "UAE-RE-06",
    "agency_name": "Haus & Haus Real Estate",
    "broker_name": "Luke Remington",
    "phone": "+971 55 492 8110",
    "phone_clean": "971554928110",
    "territory": "Dubai Marina & Emirates Living",
    "niche": "Prime Secondary Luxury & Investment Portfolios",
    "demo_url": "https://apex-properties-ai.onrender.com/demo?agency=Haus%20%26%20Haus%20Real%20Estate&broker=Luke%20Remington&whatsapp=%2B971%2055%20492%208110",
    "dash_url": "https://apex-properties-ai.onrender.com/leads?agency=Haus%20%26%20Haus%20Real%20Estate&broker=Luke%20Remington",
    "status": "DISCOVERED",
    "discovered_at": "2026-10-05 20:00:00",
    "last_contacted_at": null,
    "next_followup_at": null,
    "messages": {
      "initial": "Hello Luke,\n\nI noticed your luxury listings in Dubai Marina & Emirates Living on Bayut and Property Finder.\n\nWhen high-net-worth buyers inquire after 7 PM or from overseas (London, Europe, India), competing brokers often lock in viewings before morning follow-ups happen.\n\nTo help Haus & Haus Real Estate eliminate this drop-off and filter out tire-kickers, I built a personalized AI Property Advisor tailored for your agency:\n\n📱 Test the live buyer experience on your phone (takes 20 seconds):\n👉 https://apex-properties-ai.onrender.com/demo?agency=Haus%20%26%20Haus%20Real%20Estate&broker=Luke%20Remington&whatsapp=%2B971%2055%20492%208110\n(Tap the glowing blue chat bubble at the bottom right)\n\n📊 View your live qualified investor pipeline:\n👉 https://apex-properties-ai.onrender.com/leads?agency=Haus%20%26%20Haus%20Real%20Estate&broker=Luke%20Remington\n\nWhat it does for Haus & Haus Real Estate:\n• Instant 24/7 qualification for 5M+ AED cash buyers & 10-Yr Golden Visa investors\n• Filters out time-wasters so your team only spends time with serious buyers\n• 1-click WhatsApp brochure handoff directly to your mobile\n\nWould you like to test a 7-day free trial on your active listings this week? Zero upfront payment required.\n\nBest regards,\nAthul Raj\nAI Automation Specialist — UAE\nWhatsApp: +971 54 740 0174",
      "followup1": "Hello Luke,\n\nQuick follow-up regarding the custom AI Advisor for Haus & Haus Real Estate.\n\nDid you get 20 seconds to test the demo on your phone?\n👉 https://apex-properties-ai.onrender.com/demo?agency=Haus%20%26%20Haus%20Real%20Estate&broker=Luke%20Remington&whatsapp=%2B971%2055%20492%208110\n\nA broker in Abu Dhabi tested it yesterday and had an investor qualified for a 6.2M AED beachfront villa inquiry at 11:30 PM with zero manual effort.\n\nWould you like us to activate the 7-Day Free Trial for your team this week?",
      "followup2": "Hi Luke,\n\nI assume you are currently busy closing deals in Dubai Marina & Emirates Living.\n\nI don't want to clutter your inbox. Should I close your 7-day trial file for Haus & Haus Real Estate, or would you like a 5-minute walk-through on how to automate your speed-to-lead?"
    }
  },
  {
    "lead_id": "UAE-RE-07",
    "agency_name": "Allsopp & Allsopp Luxury",
    "broker_name": "Lewis Allsopp",
    "phone": "+971 58 591 0022",
    "phone_clean": "971585910022",
    "territory": "Palm Jumeirah & Downtown Dubai",
    "niche": "Ultra-Luxury Waterfront Villas & Off-Plan Penthouses",
    "demo_url": "https://apex-properties-ai.onrender.com/demo?agency=Allsopp%20%26%20Allsopp%20Luxury&broker=Lewis%20Allsopp&whatsapp=%2B971%2058%20591%200022",
    "dash_url": "https://apex-properties-ai.onrender.com/leads?agency=Allsopp%20%26%20Allsopp%20Luxury&broker=Lewis%20Allsopp",
    "status": "DISCOVERED",
    "discovered_at": "2026-10-05 20:00:00",
    "last_contacted_at": null,
    "next_followup_at": null,
    "messages": {
      "initial": "Hello Lewis,\n\nI noticed your luxury listings in Palm Jumeirah & Downtown Dubai on Bayut and Property Finder.\n\nWhen high-net-worth buyers inquire after 7 PM or from overseas (London, Europe, India), competing brokers often lock in viewings before morning follow-ups happen.\n\nTo help Allsopp & Allsopp Luxury eliminate this drop-off and filter out tire-kickers, I built a personalized AI Property Advisor tailored for your agency:\n\n📱 Test the live buyer experience on your phone (takes 20 seconds):\n👉 https://apex-properties-ai.onrender.com/demo?agency=Allsopp%20%26%20Allsopp%20Luxury&broker=Lewis%20Allsopp&whatsapp=%2B971%2058%20591%200022\n(Tap the glowing blue chat bubble at the bottom right)\n\n📊 View your live qualified investor pipeline:\n👉 https://apex-properties-ai.onrender.com/leads?agency=Allsopp%20%26%20Allsopp%20Luxury&broker=Lewis%20Allsopp\n\nWhat it does for Allsopp & Allsopp Luxury:\n• Instant 24/7 qualification for 5M+ AED cash buyers & 10-Yr Golden Visa investors\n• Filters out time-wasters so your team only spends time with serious buyers\n• 1-click WhatsApp brochure handoff directly to your mobile\n\nWould you like to test a 7-day free trial on your active listings this week? Zero upfront payment required.\n\nBest regards,\nAthul Raj\nAI Automation Specialist — UAE\nWhatsApp: +971 54 740 0174",
      "followup1": "Hello Lewis,\n\nQuick follow-up regarding the custom AI Advisor for Allsopp & Allsopp Luxury.\n\nDid you get 20 seconds to test the demo on your phone?\n👉 https://apex-properties-ai.onrender.com/demo?agency=Allsopp%20%26%20Allsopp%20Luxury&broker=Lewis%20Allsopp&whatsapp=%2B971%2058%20591%200022\n\nA broker in Abu Dhabi tested it yesterday and had an investor qualified for a 6.2M AED beachfront villa inquiry at 11:30 PM with zero manual effort.\n\nWould you like us to activate the 7-Day Free Trial for your team this week?",
      "followup2": "Hi Lewis,\n\nI assume you are currently busy closing deals in Palm Jumeirah & Downtown Dubai.\n\nI don't want to clutter your inbox. Should I close your 7-day trial file for Allsopp & Allsopp Luxury, or would you like a 5-minute walk-through on how to automate your speed-to-lead?"
    }
  },
  {
    "lead_id": "UAE-RE-08",
    "agency_name": "Luxhabitat Sotheby's International Realty",
    "broker_name": "George Azar",
    "phone": "+971 50 456 7890",
    "phone_clean": "971504567890",
    "territory": "Palm Jumeirah & Jumeirah Bay Island",
    "niche": "Ultra-Prime 20M+ AED Mansions & Penthouses",
    "demo_url": "https://apex-properties-ai.onrender.com/demo?agency=Luxhabitat%20Sotheby%27s%20International%20Realty&broker=George%20Azar&whatsapp=%2B971%2050%20456%207890",
    "dash_url": "https://apex-properties-ai.onrender.com/leads?agency=Luxhabitat%20Sotheby%27s%20International%20Realty&broker=George%20Azar",
    "status": "DISCOVERED",
    "discovered_at": "2026-10-05 20:00:00",
    "last_contacted_at": null,
    "next_followup_at": null,
    "messages": {
      "initial": "Hello George,\n\nI noticed your luxury listings in Palm Jumeirah & Jumeirah Bay Island on Bayut and Property Finder.\n\nWhen high-net-worth buyers inquire after 7 PM or from overseas (London, Europe, India), competing brokers often lock in viewings before morning follow-ups happen.\n\nTo help Luxhabitat Sotheby's International Realty eliminate this drop-off and filter out tire-kickers, I built a personalized AI Property Advisor tailored for your agency:\n\n📱 Test the live buyer experience on your phone (takes 20 seconds):\n👉 https://apex-properties-ai.onrender.com/demo?agency=Luxhabitat%20Sotheby%27s%20International%20Realty&broker=George%20Azar&whatsapp=%2B971%2050%20456%207890\n(Tap the glowing blue chat bubble at the bottom right)\n\n📊 View your live qualified investor pipeline:\n👉 https://apex-properties-ai.onrender.com/leads?agency=Luxhabitat%20Sotheby%27s%20International%20Realty&broker=George%20Azar\n\nWhat it does for Luxhabitat Sotheby's International Realty:\n• Instant 24/7 qualification for 5M+ AED cash buyers & 10-Yr Golden Visa investors\n• Filters out time-wasters so your team only spends time with serious buyers\n• 1-click WhatsApp brochure handoff directly to your mobile\n\nWould you like to test a 7-day free trial on your active listings this week? Zero upfront payment required.\n\nBest regards,\nAthul Raj\nAI Automation Specialist — UAE\nWhatsApp: +971 54 740 0174",
      "followup1": "Hello George,\n\nQuick follow-up regarding the custom AI Advisor for Luxhabitat Sotheby's International Realty.\n\nDid you get 20 seconds to test the demo on your phone?\n👉 https://apex-properties-ai.onrender.com/demo?agency=Luxhabitat%20Sotheby%27s%20International%20Realty&broker=George%20Azar&whatsapp=%2B971%2050%20456%207890\n\nA broker in Abu Dhabi tested it yesterday and had an investor qualified for a 6.2M AED beachfront villa inquiry at 11:30 PM with zero manual effort.\n\nWould you like us to activate the 7-Day Free Trial for your team this week?",
      "followup2": "Hi George,\n\nI assume you are currently busy closing deals in Palm Jumeirah & Jumeirah Bay Island.\n\nI don't want to clutter your inbox. Should I close your 7-day trial file for Luxhabitat Sotheby's International Realty, or would you like a 5-minute walk-through on how to automate your speed-to-lead?"
    }
  },
  {
    "lead_id": "UAE-RE-09",
    "agency_name": "Savills Abu Dhabi",
    "broker_name": "Edward Carnegy",
    "phone": "+971 50 612 3456",
    "phone_clean": "971506123456",
    "territory": "Saadiyat Island & Al Raha Beach",
    "niche": "Institutional & High-Net-Worth Residential Advisory",
    "demo_url": "https://apex-properties-ai.onrender.com/demo?agency=Savills%20Abu%20Dhabi&broker=Edward%20Carnegy&whatsapp=%2B971%2050%20612%203456",
    "dash_url": "https://apex-properties-ai.onrender.com/leads?agency=Savills%20Abu%20Dhabi&broker=Edward%20Carnegy",
    "status": "DISCOVERED",
    "discovered_at": "2026-10-05 20:00:00",
    "last_contacted_at": null,
    "next_followup_at": null,
    "messages": {
      "initial": "Hello Edward,\n\nI noticed your luxury listings in Saadiyat Island & Al Raha Beach on Bayut and Property Finder.\n\nWhen high-net-worth buyers inquire after 7 PM or from overseas (London, Europe, India), competing brokers often lock in viewings before morning follow-ups happen.\n\nTo help Savills Abu Dhabi eliminate this drop-off and filter out tire-kickers, I built a personalized AI Property Advisor tailored for your agency:\n\n📱 Test the live buyer experience on your phone (takes 20 seconds):\n👉 https://apex-properties-ai.onrender.com/demo?agency=Savills%20Abu%20Dhabi&broker=Edward%20Carnegy&whatsapp=%2B971%2050%20612%203456\n(Tap the glowing blue chat bubble at the bottom right)\n\n📊 View your live qualified investor pipeline:\n👉 https://apex-properties-ai.onrender.com/leads?agency=Savills%20Abu%20Dhabi&broker=Edward%20Carnegy\n\nWhat it does for Savills Abu Dhabi:\n• Instant 24/7 qualification for 5M+ AED cash buyers & 10-Yr Golden Visa investors\n• Filters out time-wasters so your team only spends time with serious buyers\n• 1-click WhatsApp brochure handoff directly to your mobile\n\nWould you like to test a 7-day free trial on your active listings this week? Zero upfront payment required.\n\nBest regards,\nAthul Raj\nAI Automation Specialist — UAE\nWhatsApp: +971 54 740 0174",
      "followup1": "Hello Edward,\n\nQuick follow-up regarding the custom AI Advisor for Savills Abu Dhabi.\n\nDid you get 20 seconds to test the demo on your phone?\n👉 https://apex-properties-ai.onrender.com/demo?agency=Savills%20Abu%20Dhabi&broker=Edward%20Carnegy&whatsapp=%2B971%2050%20612%203456\n\nA broker in Abu Dhabi tested it yesterday and had an investor qualified for a 6.2M AED beachfront villa inquiry at 11:30 PM with zero manual effort.\n\nWould you like us to activate the 7-Day Free Trial for your team this week?",
      "followup2": "Hi Edward,\n\nI assume you are currently busy closing deals in Saadiyat Island & Al Raha Beach.\n\nI don't want to clutter your inbox. Should I close your 7-day trial file for Savills Abu Dhabi, or would you like a 5-minute walk-through on how to automate your speed-to-lead?"
    }
  },
  {
    "lead_id": "UAE-RE-10",
    "agency_name": "Betterhomes Abu Dhabi",
    "broker_name": "Richard Waind",
    "phone": "+971 52 987 6543",
    "phone_clean": "971529876543",
    "territory": "Yas Island & Al Reem Island",
    "niche": "High-Yield Family Communities & Waterfront Living",
    "demo_url": "https://apex-properties-ai.onrender.com/demo?agency=Betterhomes%20Abu%20Dhabi&broker=Richard%20Waind&whatsapp=%2B971%2052%20987%206543",
    "dash_url": "https://apex-properties-ai.onrender.com/leads?agency=Betterhomes%20Abu%20Dhabi&broker=Richard%20Waind",
    "status": "DISCOVERED",
    "discovered_at": "2026-10-05 20:00:00",
    "last_contacted_at": null,
    "next_followup_at": null,
    "messages": {
      "initial": "Hello Richard,\n\nI noticed your luxury listings in Yas Island & Al Reem Island on Bayut and Property Finder.\n\nWhen high-net-worth buyers inquire after 7 PM or from overseas (London, Europe, India), competing brokers often lock in viewings before morning follow-ups happen.\n\nTo help Betterhomes Abu Dhabi eliminate this drop-off and filter out tire-kickers, I built a personalized AI Property Advisor tailored for your agency:\n\n📱 Test the live buyer experience on your phone (takes 20 seconds):\n👉 https://apex-properties-ai.onrender.com/demo?agency=Betterhomes%20Abu%20Dhabi&broker=Richard%20Waind&whatsapp=%2B971%2052%20987%206543\n(Tap the glowing blue chat bubble at the bottom right)\n\n📊 View your live qualified investor pipeline:\n👉 https://apex-properties-ai.onrender.com/leads?agency=Betterhomes%20Abu%20Dhabi&broker=Richard%20Waind\n\nWhat it does for Betterhomes Abu Dhabi:\n• Instant 24/7 qualification for 5M+ AED cash buyers & 10-Yr Golden Visa investors\n• Filters out time-wasters so your team only spends time with serious buyers\n• 1-click WhatsApp brochure handoff directly to your mobile\n\nWould you like to test a 7-day free trial on your active listings this week? Zero upfront payment required.\n\nBest regards,\nAthul Raj\nAI Automation Specialist — UAE\nWhatsApp: +971 54 740 0174",
      "followup1": "Hello Richard,\n\nQuick follow-up regarding the custom AI Advisor for Betterhomes Abu Dhabi.\n\nDid you get 20 seconds to test the demo on your phone?\n👉 https://apex-properties-ai.onrender.com/demo?agency=Betterhomes%20Abu%20Dhabi&broker=Richard%20Waind&whatsapp=%2B971%2052%20987%206543\n\nA broker in Abu Dhabi tested it yesterday and had an investor qualified for a 6.2M AED beachfront villa inquiry at 11:30 PM with zero manual effort.\n\nWould you like us to activate the 7-Day Free Trial for your team this week?",
      "followup2": "Hi Richard,\n\nI assume you are currently busy closing deals in Yas Island & Al Reem Island.\n\nI don't want to clutter your inbox. Should I close your 7-day trial file for Betterhomes Abu Dhabi, or would you like a 5-minute walk-through on how to automate your speed-to-lead?"
    }
  }
]''')

def get_crm_database() -> List[Dict]:
    for p in _resolve_crm_files():
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data and len(data) >= 5:
                    return data
            except Exception:
                pass
    # Auto-seed default 10 verified UAE luxury brokers
    try:
        save_crm_database(DEFAULT_MASTER_LEADS)
    except Exception:
        pass
    return DEFAULT_MASTER_LEADS

def save_crm_database(data: List[Dict]):
    content = json.dumps(data, indent=2, ensure_ascii=False)
    for p in _resolve_crm_files():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        except Exception:
            pass

@app.get("/api/crm/leads")
def api_crm_leads():
    return get_crm_database()

@app.post("/api/crm/update-status")
def api_crm_update_status(payload: Dict):
    from datetime import datetime, timedelta
    lead_id = payload.get("lead_id")
    new_status = payload.get("status")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    leads = get_crm_database()
    for l in leads:
        if l.get("lead_id") == lead_id:
            l["status"] = new_status
            if new_status == "CONTACTED":
                l["last_contacted_at"] = now_str
                l["next_followup_at"] = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            elif new_status == "FOLLOWUP_1_SENT":
                l["last_contacted_at"] = now_str
                l["next_followup_at"] = (datetime.now() + timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
            elif new_status == "FOLLOWUP_2_SENT":
                l["last_contacted_at"] = now_str
                l["next_followup_at"] = None
            break

    save_crm_database(leads)
    return {"success": True, "lead_id": lead_id, "status": new_status}

@app.get("/crm", response_class=HTMLResponse)
@app.get("/outreach", response_class=HTMLResponse)
def crm_dashboard():
    import urllib.parse
    leads = get_crm_database()
    total_prospects = len(leads)
    contacted_count = sum(1 for l in leads if l.get("status") in ["CONTACTED", "FOLLOWUP_1_SENT", "FOLLOWUP_2_SENT", "REPLIED", "WON"])
    won_count = sum(1 for l in leads if l.get("status") == "WON")
    pipeline_val = len(leads) * 1500

    cards_html = ""
    for l in leads:
        lid = l.get("lead_id", "N/A")
        agency = l.get("agency_name", "UAE Brokerage")
        broker = l.get("broker_name", "Senior Broker")
        phone = l.get("phone", "")
        clean_p = l.get("phone_clean", re.sub(r'[^0-9]', '', phone))
        territory = l.get("territory", "Abu Dhabi & Dubai")
        niche = l.get("niche", "Luxury Real Estate")
        status = l.get("status", "DISCOVERED")
        demo_url = l.get("demo_url", f"/demo?agency={urllib.parse.quote(agency)}")
        
        msgs = l.get("messages", {})
        initial_msg = msgs.get("initial", "")
        followup1_msg = msgs.get("followup1", "")
        followup2_msg = msgs.get("followup2", "")

        wa_initial = f"https://wa.me/{clean_p}?text={urllib.parse.quote(initial_msg)}"
        wa_f1 = f"https://wa.me/{clean_p}?text={urllib.parse.quote(followup1_msg)}"
        wa_f2 = f"https://wa.me/{clean_p}?text={urllib.parse.quote(followup2_msg)}"

        # Status badge classes
        status_colors = {
            "DISCOVERED": ("#38bdf8", "rgba(56, 189, 248, 0.15)"),
            "CONTACTED": ("#fbbf24", "rgba(251, 191, 36, 0.15)"),
            "FOLLOWUP_1_DUE": ("#f97316", "rgba(249, 115, 22, 0.2)"),
            "FOLLOWUP_1_SENT": ("#fbbf24", "rgba(251, 191, 36, 0.15)"),
            "FOLLOWUP_2_DUE": ("#ef4444", "rgba(239, 68, 68, 0.2)"),
            "REPLIED": ("#a855f7", "rgba(168, 85, 247, 0.2)"),
            "WON": ("#4ade80", "rgba(74, 222, 128, 0.2)")
        }
        badge_fg, badge_bg = status_colors.get(status, ("#94a3b8", "rgba(148, 163, 184, 0.15)"))

        cards_html += f"""
        <div class="prospect-card" id="card-{lid}">
          <div class="prospect-head">
            <div>
              <div class="prospect-agency">{agency}</div>
              <div class="prospect-broker">&#128100; {broker} &bull; <a href="tel:{clean_p}" style="color:#38bdf8; text-decoration:none;">{phone}</a></div>
            </div>
            <span class="status-badge" style="color:{badge_fg}; background:{badge_bg}; border: 1px solid {badge_fg};">{status}</span>
          </div>

          <div class="prospect-meta">
            <div><strong>Territory:</strong> {territory}</div>
            <div><strong>Niche:</strong> {niche}</div>
          </div>

          <div class="demo-box">
            <span style="color:#94a3b8; font-size:11px;">PERSONALIZED CLIENT DEMO LINK:</span><br>
            <a href="{demo_url}" target="_blank" class="demo-link">&#128279; {demo_url}</a>
          </div>

          <div class="actions-grid">
            <a href="{wa_initial}" target="_blank" onclick="updateStatus('{lid}', 'CONTACTED')" class="btn-action btn-initial">
              &#128172; 1-Click Initial Pitch
            </a>
            <a href="{wa_f1}" target="_blank" onclick="updateStatus('{lid}', 'FOLLOWUP_1_SENT')" class="btn-action btn-f1">
              &#9201; Send 24h Follow-Up
            </a>
            <a href="{wa_f2}" target="_blank" onclick="updateStatus('{lid}', 'FOLLOWUP_2_SENT')" class="btn-action btn-f2">
              &#9888;&#65039; Send 48h Breakup
            </a>
            <button onclick="updateStatus('{lid}', 'WON')" class="btn-action btn-won">
              &#127942; Mark Won (1,500 AED)
            </button>
          </div>
        </div>
        """

    crm_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AutoSales Agent &mdash; UAE Real Estate Client Acquisition & Follow-Up Engine</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #090d16;
    color: #f1f5f9;
    padding-bottom: 60px;
  }}
  .header {{
    background: linear-gradient(135deg, #0f172a, #1e293b);
    padding: 24px 32px;
    border-bottom: 1px solid #334155;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
  }}
  .logo {{ font-size: 20px; font-weight: 800; color: #38bdf8; }}
  .container {{ max-width: 1200px; margin: 32px auto; padding: 0 20px; }}
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
  }}
  .kpi-card {{
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 20px;
  }}
  .kpi-title {{ font-size: 11px; text-transform: uppercase; color: #94a3b8; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 6px; }}
  .kpi-val {{ font-size: 30px; font-weight: 800; color: #38bdf8; }}
  .section-h {{ font-size: 18px; font-weight: 800; margin-bottom: 18px; display: flex; justify-content: space-between; align-items: center; }}
  .prospect-grid {{ display: flex; flex-direction: column; gap: 16px; }}
  .prospect-card {{
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 16px;
    padding: 22px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
  }}
  .prospect-head {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; flex-wrap: wrap; gap: 10px; }}
  .prospect-agency {{ font-size: 20px; font-weight: 800; color: #f8fafc; }}
  .prospect-broker {{ font-size: 13px; color: #94a3b8; margin-top: 4px; }}
  .status-badge {{
    font-size: 11px;
    font-weight: 800;
    padding: 4px 12px;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .prospect-meta {{
    font-size: 13px;
    color: #cbd5e1;
    background: #131d33;
    padding: 12px 16px;
    border-radius: 10px;
    margin-bottom: 14px;
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
  }}
  .demo-box {{
    background: #090d16;
    border: 1px solid #1e293b;
    padding: 10px 14px;
    border-radius: 8px;
    margin-bottom: 16px;
    font-size: 12px;
  }}
  .demo-link {{ color: #38bdf8; text-decoration: none; word-break: break-all; font-weight: 600; }}
  .demo-link:hover {{ text-decoration: underline; }}
  .actions-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 10px;
  }}
  .btn-action {{
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
    text-align: center;
    text-decoration: none;
    cursor: pointer;
    border: none;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    transition: transform 0.15s, opacity 0.15s;
  }}
  .btn-action:hover {{ opacity: 0.9; transform: translateY(-1px); }}
  .btn-initial {{ background: #25D366; color: #ffffff !important; }}
  .btn-f1 {{ background: #0284c7; color: #ffffff !important; }}
  .btn-f2 {{ background: #ea580c; color: #ffffff !important; }}
  .btn-won {{ background: #16a34a; color: #ffffff !important; }}
</style>
<script>
async function updateStatus(leadId, newStatus) {{
  try {{
    await fetch('/api/crm/update-status', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ lead_id: leadId, status: newStatus }})
    }});
    const badge = document.querySelector('#card-' + leadId + ' .status-badge');
    if (badge) {{
      badge.textContent = newStatus;
    }}
  }} catch (e) {{
    console.error('Error updating lead status:', e);
  }}
}}
</script>
</head>
<body>

<div class="header">
  <div class="logo">&#9881;&#65039; AutoSales Agent &mdash; UAE Broker Acquisition Engine</div>
  <a href="/leads" target="_blank" style="color:#38bdf8; text-decoration:none; font-size:13px; font-weight:700;">&#128202; View Buyer Leads Dashboard &rarr;</a>
</div>

<div class="container">
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-title">Verified UAE Brokers Loaded</div>
      <div class="kpi-val">{total_prospects}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">In Active Outreach</div>
      <div class="kpi-val" style="color:#fbbf24;">{contacted_count}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Broker Contracts Won</div>
      <div class="kpi-val" style="color:#4ade80;">{won_count}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">Pipeline Revenue Potential</div>
      <div class="kpi-val" style="color:#38bdf8;">{pipeline_val:,} AED</div>
    </div>
  </div>

  <div class="section-h">
    <span>Autonomous Outreach Queue (1-Click Personalized WhatsApp Dispatch)</span>
  </div>

  <div class="prospect-grid">
    {cards_html}
  </div>
</div>

</body>
</html>"""
    return HTMLResponse(content=crm_html, media_type="text/html; charset=utf-8")

# ==================== VIRTUAL SALES AGENT COCKPIT & AUTONOMOUS DAEMON ====================

try:
    from services.virtual_sales_daemon import get_daemon
    agent_daemon = get_daemon()
except Exception as e:
    logger.error(f"Could not initialize virtual sales daemon: {e}")
    agent_daemon = None

@app.on_event("startup")
def on_app_startup():
    if agent_daemon:
        try:
            agent_daemon.start_background()
        except Exception as e:
            logger.error(f"Startup daemon error: {e}")

@app.get("/api/agent/status")
def get_agent_status():
    if not agent_daemon:
        return {"status": "offline", "autopilot_enabled": False}
    return {
        "status": "online",
        "autopilot_enabled": agent_daemon.autopilot_enabled,
        "last_cycle": agent_daemon.last_cycle_time.strftime("%Y-%m-%d %H:%M:%S") if agent_daemon.last_cycle_time else None,
        "next_cycle": agent_daemon.next_cycle_time.strftime("%Y-%m-%d %H:%M:%S") if agent_daemon.next_cycle_time else None,
        "gmail_sender": "athulaisolutions@gmail.com",
        "ollama_active": bool(agent_daemon.agent.ollama.is_available())
    }

@app.get("/api/agent/activity")
def get_agent_activity():
    if not agent_daemon:
        return []
    return agent_daemon.get_recent_activity(limit=40)

@app.post("/api/agent/trigger-cycle")
def api_trigger_cycle():
    if not agent_daemon:
        raise HTTPException(status_code=500, detail="Daemon not initialized")
    summary = agent_daemon.execute_autonomous_cycle()
    return {"success": True, "summary": summary}

@app.post("/api/agent/trigger-hunt")
def api_trigger_hunt():
    if not agent_daemon:
        raise HTTPException(status_code=500, detail="Daemon not initialized")
    new_leads = agent_daemon.agent.hunt_fresh_leads(target_count=3)
    agent_daemon.log_activity(f"🔍 Autonomously hunted {len(new_leads)} new brokers.", level="HUNT")
    return {"success": True, "count": len(new_leads)}

@app.post("/api/agent/toggle-autopilot")
def api_toggle_autopilot():
    if not agent_daemon:
        raise HTTPException(status_code=500, detail="Daemon not initialized")
    new_state = agent_daemon.toggle_autopilot()
    return {"success": True, "autopilot_enabled": new_state}

@app.post("/api/agent/send-email")
def api_send_email(payload: Dict[str, Any] = Body(...)):
    lead_id = payload.get("lead_id")
    if not agent_daemon or not lead_id:
        raise HTTPException(status_code=400, detail="Invalid request")
    res = agent_daemon.agent.dispatch_email_pitch(lead_id)
    agent_daemon.log_activity(f"📧 Dispatched cold email to {lead_id} ({res.get('status')})", level="EMAIL")
    return res

@app.post("/api/agent/send-followup")
def api_send_followup(payload: Dict[str, Any] = Body(...)):
    lead_id = payload.get("lead_id")
    stage = payload.get("stage", "followup1")
    if not agent_daemon or not lead_id:
        raise HTTPException(status_code=400, detail="Invalid request")
    res = agent_daemon.agent.dispatch_email_followup(lead_id, stage=stage)
    agent_daemon.log_activity(f"📤 Dispatched {stage} email to {lead_id} ({res.get('status')})", level="EMAIL")
    return res

def fetch_and_sync_remote_clicks() -> Dict[str, Any]:
    """Fetches real-time clicks from Render and updates local/remote CRM leads."""
    import urllib.request
    remote_url = "https://apex-properties-ai.onrender.com/api/agent/remote-clicks"
    synced = []
    try:
        req = urllib.request.Request(remote_url, headers={"User-Agent": "AthulAI-LocalSync/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=6) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                clicks = data.get("clicks", [])
                crm_leads = agent_daemon.agent.get_crm_leads() if agent_daemon else get_crm_database()
                updated = False
                for c in clicks:
                    c_ag = str(c.get("agency") or "").strip().lower()
                    c_time = c.get("timestamp")
                    c_route = c.get("route", "/demo")
                    if not c_ag or c_ag in ["apex prime real estate", "null", "undefined"]:
                        continue
                    for lead in crm_leads:
                        l_ag = str(lead.get("agency_name") or "").strip().lower()
                        if c_ag in l_ag or l_ag in c_ag:
                            if lead.get("status") != "WON":
                                prev = lead.get("status")
                                lead["status"] = "CLICKED"
                                lead["last_clicked_at"] = c_time
                                lead["click_count"] = max(lead.get("click_count") or 0, c.get("count", 1))
                                routes = lead.get("clicked_routes") or []
                                if c_route not in routes:
                                    routes.append(c_route)
                                lead["clicked_routes"] = routes
                                updated = True
                                if lead.get("agency_name") not in synced:
                                    synced.append(lead.get("agency_name"))
                                if prev != "CLICKED" and agent_daemon:
                                    agent_daemon.log_activity(
                                        f"🎯 Client verified active click! {lead.get('agency_name')} ({c_route}) -> Status upgraded to CLICKED (Hot Lead).",
                                        level="CLICK"
                                    )
                if updated:
                    if agent_daemon:
                        agent_daemon.agent._save_crm(crm_leads)
                    save_crm_database(crm_leads)
    except Exception as e:
        logger.warning(f"Remote click sync note: {e}")
    return {"success": True, "synced_count": len(synced), "synced_agencies": synced}

@app.get("/api/agent/remote-clicks")
def get_remote_clicks():
    clicks = []
    for p in CLICK_LOG_FILES:
        if p.exists():
            try:
                clicks = json.loads(p.read_text(encoding="utf-8"))
                break
            except Exception:
                pass
    return {
        "success": True,
        "total_clicks": len(clicks),
        "clicks": clicks[:100]
    }

@app.post("/api/agent/record-click")
async def api_record_click(request: Request):
    try:
        body = await request.json()
        agency = body.get("agency")
        broker = body.get("broker")
        route = body.get("route", "/demo")
        record_remote_click(agency=agency, broker=broker, route=route, client_ip=request.client.host if request.client else "", user_agent=request.headers.get("user-agent", ""))
        return {"success": True, "message": f"Click recorded for {agency}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/agent/sync-clicks")
@app.post("/api/agent/sync-clicks")
def api_sync_clicks():
    return fetch_and_sync_remote_clicks()

@app.get("/agent", response_class=HTMLResponse)
@app.get("/cockpit", response_class=HTMLResponse)
def virtual_agent_cockpit():
    leads = agent_daemon.agent.get_crm_leads() if agent_daemon else get_crm_database()
    total_leads = len(leads)
    won_leads = sum(1 for l in leads if l.get("status") == "WON")
    clicked_leads = sum(1 for l in leads if l.get("status") == "CLICKED")
    contacted_leads = sum(1 for l in leads if l.get("status") in ["CONTACTED", "FOLLOWUP_1_SENT", "FOLLOWUP_2_SENT", "REPLIED"])
    pipeline_val = (total_leads - won_leads) * 2500
    won_val = won_leads * 2500

    cards_html = ""
    for l in leads:
        lid = l.get("lead_id", "N/A")
        agency = l.get("agency_name", "UAE Agency")
        broker = l.get("broker_name", "Senior Advisor")
        phone = l.get("phone", "+971547400174")
        email = l.get("email") or (agent_daemon.agent.get_or_assign_lead_email(l) if agent_daemon else "info@agency.ae")
        territory = l.get("territory") or l.get("area") or "Dubai & Abu Dhabi"
        score = l.get("ml_score", 75)
        angle = l.get("optimal_pitch_angle", "speed_to_lead")
        status = l.get("status", "DISCOVERED")
        demo_url = l.get("demo_url", f"/demo?agency={urllib.parse.quote(agency)}")
        portal_url = l.get("portal_url", f"/portal?agency={urllib.parse.quote(agency)}")
        
        # WhatsApp message link
        clean_p = l.get("phone_clean", re.sub(r'[^0-9]', '', phone))
        wa_text = l.get("messages", {}).get("initial", "")
        wa_url = f"https://wa.me/{clean_p}?text={urllib.parse.quote(wa_text)}"

        # Status badge colors
        st_colors = {
            "DISCOVERED": ("#38bdf8", "rgba(56,189,248,0.15)"),
            "CONTACTED": ("#fbbf24", "rgba(251,191,36,0.15)"),
            "CLICKED": ("#c084fc", "rgba(192,132,252,0.25)"),
            "FOLLOWUP_1_DUE": ("#f97316", "rgba(249,115,22,0.2)"),
            "FOLLOWUP_1_SENT": ("#fbbf24", "rgba(251,191,36,0.15)"),
            "FOLLOWUP_2_DUE": ("#ef4444", "rgba(239,68,68,0.2)"),
            "REPLIED": ("#a855f7", "rgba(168,85,247,0.2)"),
            "WON": ("#4ade80", "rgba(74,222,128,0.2)")
        }
        badge_fg, badge_bg = st_colors.get(status, ("#94a3b8", "rgba(148,163,184,0.15)"))
        status_label = f"🔥 CLICKED ({l.get('click_count', 1)}x)" if status == "CLICKED" else status
        click_time_html = f'<div style="font-size:11px; color:#c084fc; margin-top:4px; font-weight:700;">🕒 Clicked: {l.get("last_clicked_at")}</div>' if status == "CLICKED" and l.get("last_clicked_at") else ''

        cards_html += f"""
        <div class="lead-card" id="card-{lid}" style="{'border-color:#a855f7; box-shadow:0 0 15px rgba(168,85,247,0.15);' if status == 'CLICKED' else ''}">
          <div class="lead-header">
            <div>
              <div class="lead-agency">{agency}</div>
              <div class="lead-broker">&#128100; {broker} &bull; <span style="color:#94a3b8;">{territory}</span></div>
            </div>
            <div style="text-align:right;">
              <span class="status-pill" style="color:{badge_fg}; background:{badge_bg}; border:1px solid {badge_fg};">{status_label}</span>
              <div class="ml-badge">&#129504; ML Score: <strong>{score}/100</strong></div>
              {click_time_html}
            </div>
          </div>

          <div class="lead-contacts">
            <div>&#9993;&#65039; <strong>Email:</strong> <a href="mailto:{email}" style="color:#38bdf8; text-decoration:none;">{email}</a></div>
            <div>&#128241; <strong>WhatsApp:</strong> <a href="tel:{clean_p}" style="color:#38bdf8; text-decoration:none;">{phone}</a></div>
            <div>&#127919; <strong>ML Angle:</strong> <span style="color:#facc15;">{angle}</span></div>
          </div>

          <div class="links-row">
            <a href="{portal_url}" target="_blank" class="link-btn portal-btn">&#127775; Instagram Bio Portal</a>
            <a href="{demo_url}" target="_blank" class="link-btn demo-btn">&#128241; Broker Pitch Demo</a>
          </div>

          <div class="actions-row">
            <button onclick="sendLeadEmail('{lid}')" class="btn-cta btn-email">&#9993;&#65039; Send Email</button>
            <a href="{wa_url}" target="_blank" onclick="markContacted('{lid}')" class="btn-cta btn-wa">&#128172; WhatsApp</a>
            <button onclick="sendFollowup('{lid}')" class="btn-cta btn-fu">&#9201; Follow-Up</button>
            <button onclick="markWon('{lid}')" class="btn-cta btn-win">&#127942; Won Deal</button>
          </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Virtual Sales Agent &mdash; Autonomous Cockpit</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #070b12;
    color: #f8fafc;
    min-height: 100vh;
  }}
  .top-bar {{
    background: rgba(15, 23, 42, 0.95);
    border-bottom: 1px solid #1e293b;
    padding: 16px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(12px);
  }}
  .agent-brand {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}
  .pulse-orb {{
    width: 14px;
    height: 14px;
    background: #22c55e;
    border-radius: 50%;
    box-shadow: 0 0 14px #22c55e;
    animation: pulse 1.8s infinite;
  }}
  @keyframes pulse {{
    0% {{ box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }}
    70% {{ box-shadow: 0 0 0 10px rgba(34, 197, 94, 0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }}
  }}
  .brand-title {{
    font-size: 18px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 0.5px;
  }}
  .brand-sub {{
    font-size: 11px;
    color: #38bdf8;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}
  .top-controls {{
    display: flex;
    gap: 12px;
    align-items: center;
  }}
  .btn-toolbar {{
    background: #1e293b;
    border: 1px solid #334155;
    color: #ffffff;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
  }}
  .btn-toolbar:hover {{
    background: #334155;
    border-color: #38bdf8;
  }}
  .btn-primary {{
    background: linear-gradient(135deg, #0284c7, #0369a1);
    border: 1px solid #38bdf8;
  }}
  .btn-primary:hover {{
    background: #0284c7;
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.4);
  }}
  .container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px;
  }}
  .kpi-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }}
  .kpi-card {{
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 18px 20px;
  }}
  .kpi-label {{
    font-size: 11px;
    color: #94a3b8;
    text-transform: uppercase;
    font-weight: 700;
    letter-spacing: 1px;
  }}
  .kpi-value {{
    font-size: 26px;
    font-weight: 800;
    margin-top: 6px;
  }}
  .cockpit-split {{
    display: grid;
    grid-template-columns: 420px 1fr;
    gap: 24px;
  }}
  @media (max-width: 1024px) {{
    .cockpit-split {{ grid-template-columns: 1fr; }}
  }}
  .stream-card {{
    background: rgba(15, 23, 42, 0.9);
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 20px;
    height: 750px;
    display: flex;
    flex-direction: column;
  }}
  .stream-title {{
    font-size: 14px;
    font-weight: 800;
    color: #38bdf8;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .stream-box {{
    flex: 1;
    overflow-y: auto;
    background: #030712;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 12px;
  }}
  .log-row {{
    padding: 6px 0;
    border-bottom: 1px solid #111827;
    line-height: 1.4;
  }}
  .log-time {{ color: #64748b; font-size: 11px; margin-right: 6px; }}
  .log-badge {{
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    margin-right: 6px;
  }}
  .badge-CYCLE {{ background: rgba(56, 189, 248, 0.2); color: #38bdf8; }}
  .badge-ML {{ background: rgba(168, 85, 247, 0.2); color: #c084fc; }}
  .badge-EMAIL {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; }}
  .badge-FOLLOWUP {{ background: rgba(249, 115, 22, 0.2); color: #fb923c; }}
  .badge-HUNT {{ background: rgba(250, 204, 21, 0.2); color: #facc15; }}
  .leads-section {{
    display: flex;
    flex-direction: column;
    gap: 16px;
  }}
  .section-h {{
    font-size: 16px;
    font-weight: 800;
    color: #ffffff;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .lead-card {{
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 20px;
    transition: border-color 0.2s;
  }}
  .lead-card:hover {{
    border-color: #38bdf8;
  }}
  .lead-header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
  }}
  .lead-agency {{
    font-size: 18px;
    font-weight: 800;
    color: #ffffff;
  }}
  .lead-broker {{
    font-size: 13px;
    color: #94a3b8;
    margin-top: 4px;
  }}
  .status-pill {{
    font-size: 11px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 12px;
  }}
  .ml-badge {{
    font-size: 11px;
    color: #a855f7;
    margin-top: 6px;
  }}
  .lead-contacts {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 8px;
    font-size: 13px;
    background: #0b1120;
    padding: 10px 14px;
    border-radius: 8px;
    margin-bottom: 14px;
  }}
  .links-row {{
    display: flex;
    gap: 10px;
    margin-bottom: 14px;
    flex-wrap: wrap;
  }}
  .link-btn {{
    font-size: 12px;
    font-weight: 700;
    padding: 6px 14px;
    border-radius: 6px;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }}
  .portal-btn {{ background: rgba(250, 204, 21, 0.15); color: #facc15; border: 1px solid #ca8a04; }}
  .demo-btn {{ background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid #0284c7; }}
  .actions-row {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }}
  .btn-cta {{
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    border: none;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }}
  .btn-email {{ background: #2563eb; color: #ffffff; }}
  .btn-email:hover {{ background: #1d4ed8; }}
  .btn-wa {{ background: #16a34a; color: #ffffff; }}
  .btn-wa:hover {{ background: #15803d; }}
  .btn-fu {{ background: #d97706; color: #ffffff; }}
  .btn-fu:hover {{ background: #b45309; }}
  .btn-win {{ background: #10b981; color: #ffffff; }}
  .btn-win:hover {{ background: #059669; }}
  #toast {{
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: #0f172a;
    border: 1px solid #38bdf8;
    color: #ffffff;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 700;
    display: none;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    z-index: 1000;
  }}
</style>
<script>
function showToast(msg) {{
  const t = document.getElementById('toast');
  t.innerText = msg;
  t.style.display = 'block';
  setTimeout(() => {{ t.style.display = 'none'; }}, 4000);
}}

async function refreshActivity() {{
  try {{
    const res = await fetch('/api/agent/activity');
    const logs = await res.json();
    const box = document.getElementById('stream-content');
    if (logs && logs.length > 0) {{
      box.innerHTML = logs.map(l => `
        <div class="log-row">
          <span class="log-time">${{l.time || ''}}</span>
          <span class="log-badge badge-${{l.level || 'INFO'}}">${{l.level || 'LOG'}}</span>
          <span>${{l.message || ''}}</span>
        </div>
      `).join('');
    }}
  }} catch (e) {{
    console.error('Activity poll error:', e);
  }}
}}

setInterval(refreshActivity, 3000);

async function triggerCycle() {{
  showToast('⚡ Triggering autonomous cycle...');
  try {{
    const res = await fetch('/api/agent/trigger-cycle', {{ method: 'POST' }});
    const d = await res.json();
    showToast('✨ Autonomous cycle completed successfully!');
    refreshActivity();
  }} catch (e) {{
    showToast('Error triggering cycle: ' + e);
  }}
}}

async function triggerHunt() {{
  showToast('🔍 Hunting fresh luxury brokers with Ollama GPU...');
  try {{
    const res = await fetch('/api/agent/trigger-hunt', {{ method: 'POST' }});
    const d = await res.json();
    showToast('✅ Discovered ' + (d.count || 3) + ' new broker profiles!');
    setTimeout(() => location.reload(), 1500);
  }} catch (e) {{
    showToast('Error during broker discovery: ' + e);
  }}
}}

async function toggleAutopilot() {{
  try {{
    const res = await fetch('/api/agent/toggle-autopilot', {{ method: 'POST' }});
    const d = await res.json();
    const txt = d.autopilot_enabled ? 'Autopilot Resumed (Running every 15m)' : 'Autopilot Paused';
    document.getElementById('autopilot-toggle-btn').innerText = d.autopilot_enabled ? '⏸️ Pause Autopilot' : '▶️ Resume Autopilot';
    showToast(txt);
  }} catch (e) {{
    showToast('Error toggling autopilot: ' + e);
  }}
}}

async function sendLeadEmail(leadId) {{
  showToast('📧 Sending cold email via athulaisolutions@gmail.com...');
  try {{
    const res = await fetch('/api/agent/send-email', {{
      method: 'POST',
      headers: {{ 'content-type': 'application/json' }},
      body: JSON.stringify({{ lead_id: leadId }})
    }});
    const d = await res.json();
    showToast('Email result: ' + (d.status || 'SENT'));
    if (d.mailto_url) {{ window.open(d.mailto_url); }}
    refreshActivity();
  }} catch (e) {{
    showToast('Error sending email: ' + e);
  }}
}}

async function sendFollowup(leadId) {{
  showToast('📤 Dispatching automated follow-up...');
  try {{
    const res = await fetch('/api/agent/send-followup', {{
      method: 'POST',
      headers: {{ 'content-type': 'application/json' }},
      body: JSON.stringify({{ lead_id: leadId, stage: 'followup1' }})
    }});
    const d = await res.json();
    showToast('Follow-up status: ' + (d.status || 'SENT'));
    refreshActivity();
  }} catch (e) {{
    showToast('Error sending follow-up: ' + e);
  }}
}}

async function markWon(leadId) {{
  try {{
    const res = await fetch('/api/crm/update-status', {{
      method: 'POST',
      headers: {{ 'content-type': 'application/json' }},
      body: JSON.stringify({{ lead_id: leadId, status: 'WON' }})
    }});
    showToast('🏆 Marked Deal as WON (+2,500 AED)!');
    setTimeout(() => location.reload(), 1000);
  }} catch (e) {{
    showToast('Error updating status: ' + e);
  }}
}}

async function markContacted(leadId) {{
  try {{
    await fetch('/api/crm/update-status', {{
      method: 'POST',
      headers: {{ 'content-type': 'application/json' }},
      body: JSON.stringify({{ lead_id: leadId, status: 'CONTACTED' }})
    }});
  }} catch (e) {{}}
}}

async function syncClicks() {{
  showToast('🔄 Syncing live client clicks from Render...');
  try {{
    const res = await fetch('/api/agent/sync-clicks', {{ method: 'POST' }});
    const d = await res.json();
    if (d.synced_count > 0) {{
      showToast('🔥 Synced ' + d.synced_count + ' active client clicks! Reloading...');
      setTimeout(() => location.reload(), 800);
    }} else {{
      showToast('✅ Client engagement verified and up to date.');
      setTimeout(() => location.reload(), 1200);
    }}
  }} catch (e) {{
    showToast('Sync check finished');
  }}
}}
</script>
</head>
<body>

<div id="toast"></div>

<div class="top-bar">
  <div class="agent-brand">
    <div class="pulse-orb"></div>
    <div>
      <div class="brand-title">Athul AI Virtual Sales Agent</div>
      <div class="brand-sub">Operating autonomously for Athul Raj &bull; athulaisolutions@gmail.com</div>
    </div>
  </div>

  <div class="top-controls">
    <button onclick="syncClicks()" class="btn-toolbar" style="border-color:#a855f7; color:#c084fc; font-weight:800;">🔄 Sync Clicks</button>
    <button id="autopilot-toggle-btn" onclick="toggleAutopilot()" class="btn-toolbar">&#9208;&#65039; Pause Autopilot</button>
    <button onclick="triggerHunt()" class="btn-toolbar">&#128269; Auto-Hunt Brokers</button>
    <button onclick="triggerCycle()" class="btn-toolbar btn-primary">&#9889; Run Cycle Now</button>
  </div>
</div>

<div class="container">
  <div class="kpi-row">
    <div class="kpi-card">
      <div class="kpi-label">Active Prospects in CRM</div>
      <div class="kpi-value">{total_leads}</div>
    </div>
    <div class="kpi-card" style="border-color:#a855f7; background:rgba(168,85,247,0.08);">
      <div class="kpi-label" style="color:#c084fc;">🔥 Verified Client Clicks</div>
      <div class="kpi-value" style="color:#c084fc;">{clicked_leads} <span style="font-size:14px; font-weight:600; color:#e9d5ff;">Hot Leads</span></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">In Active Outreach</div>
      <div class="kpi-value" style="color:#fbbf24;">{contacted_leads}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Closed Retainers Won</div>
      <div class="kpi-value" style="color:#4ade80;">{won_leads} ({won_val:,} AED)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">ML Expected Pipeline Potential</div>
      <div class="kpi-value" style="color:#38bdf8;">{pipeline_val:,} AED</div>
    </div>
  </div>

  <div class="cockpit-split">
    <!-- LIVE AGENT STREAM -->
    <div class="stream-card">
      <div class="stream-title">
        <span>&#129504; Virtual Agent Real-Time Stream</span>
        <span style="font-size:10px; color:#22c55e;">&#9679; LIVE TICKER</span>
      </div>
      <div class="stream-box" id="stream-content">
        <div class="log-row">
          <span class="log-time">04:00</span>
          <span class="log-badge badge-CYCLE">STARTUP</span>
          <span>Virtual Sales Agent online and monitoring UAE luxury real estate pipeline.</span>
        </div>
      </div>
    </div>

    <!-- LEADS PIPELINE -->
    <div class="leads-section">
      <div class="section-h">
        <span>Autonomous Outreach Queue (Emails &amp; WhatsApp Portals)</span>
        <span style="font-size:12px; color:#94a3b8;">Prioritized by ML Expected Revenue</span>
      </div>
      {cards_html}
    </div>
  </div>
</div>

<script>
refreshActivity();
setInterval(refreshActivity, 5000);
setInterval(async () => {{
  try {{
    const r = await fetch('/api/agent/sync-clicks', {{ method: 'POST' }});
    const d = await r.json();
    if (d && d.synced_count > 0) {{
      location.reload();
    }}
  }} catch (e) {{}}
}}, 20000);
</script>
</body>
</html>"""
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")

