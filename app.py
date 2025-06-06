import os
import json
import re
import requests
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer

# ─── Groq LLM Setup ──────────────────────────────────────────────────────────────
from groq import Groq
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))  # Ensure GROQ_API_KEY is exported

# ─── Google Calendar Setup ───────────────────────────────────────────────────────
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

def get_calendar_service():
    """
    Returns an authenticated Google Calendar service object.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(requests.Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def create_calendar_event(summary, start_datetime, end_datetime, attendee_email=None):
    """
    Creates a Google Calendar event.
    """
    service = get_calendar_service()
    event_body = {
        "summary": summary,
        "start": {"dateTime": start_datetime, "timeZone": "Asia/Kolkata"},
        "end":   {"dateTime": end_datetime,   "timeZone": "Asia/Kolkata"},
    }
    if attendee_email:
        event_body["attendees"] = [{"email": attendee_email}]
    event = service.events().insert(calendarId="primary", body=event_body).execute()
    return event.get("htmlLink")

# ─── Company & Booking System Prompts for Groq ──────────────────────────────────
SYSTEM_PROMPT = """
You are a helpful AI receptionist for BuildABrand.
BuildABrand is a digital marketing and web development agency offering:
- Website design & development
- Mobile & web app development
- Automation services (chatbots, AI integrations)
- SEO & content marketing

For any user query about services, answer concisely (1–2 sentences).
If the user wants to book a meeting, guide them step by step: first ask for date and time, then ask for email, then confirm booking.
Always be brief and clear because this is happening during a phone call.
"""

# ─── Vosk STT Setup ──────────────────────────────────────────────────────────────
q = queue.Queue()
VOSK_MODEL_PATH = "/Users/devanshmonga/Desktop/ai_caller/vosk-model-small-en-us-0.15"
model = Model(VOSK_MODEL_PATH)
samplerate = 16000
rec = KaldiRecognizer(model, samplerate)

def audio_callback(indata, frames, time, status):
    q.put(bytes(indata))

# ─── Mimic3 TTS Function ─────────────────────────────────────────────────────────
def speak(text):
    """
    Sends `text` to Mimic3 TTS and plays it.
    """
    print(f"🤖 {text}")
    url = f"http://localhost:59125/api/tts?text={requests.utils.quote(text)}"
    response = requests.get(url)
    if response.status_code == 200:
        with open("out.wav", "wb") as f:
            f.write(response.content)
        os.system("afplay out.wav")
    else:
        print("❗ TTS Error:", response.status_code, response.text)

# ─── Booking‐State Management ──────────────────────────────────────────────────
booking_state = None
booking_details = {}  # {"date":..., "start_time":..., "duration_minutes":30, "attendee_email":...}

# Simple regex to verify a conventional email format
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

def is_booking_request(text):
    """
    Simple keyword check for booking intent.
    """
    lower = text.lower()
    return any(word in lower for word in ["book", "schedule", "appointment", "meeting", "set up"])

def parse_date_time(text):
    """
    Ask Groq to extract date/time. Returns dict or None.
    """
    prompt = (
        "Extract meeting date and start_time from the user’s reply. "
        "Respond ONLY in JSON with keys: date (YYYY-MM-DD), start_time (HH:MM in 24h). "
        f"User reply: \"{text}\""
    )
    try:
        resp = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You extract date and start_time from text."},
                {"role": "user",   "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            max_tokens=50
        )
        details = json.loads(resp.choices[0].message.content.strip())
        if "date" in details and "start_time" in details:
            return details
    except Exception:
        pass
    return None

def request_via_groq(messages):
    """
    Send chat history to Groq and return assistant’s reply.
    """
    try:
        resp = groq_client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=100
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print("❗ Groq error:", repr(e))
        return "Sorry, I’m having trouble right now."

def parse_spelled_email(text):
    """
    Parses a spelled‐out email where the user says letters, 'at' for @, and 'dot' for '.'.
    Example: 'd e v a n s h at g m a i l dot c o m' →
             'devansh@gmail.com'
    """
    tokens = text.lower().split()
    email = ""
    for token in tokens:
        if token == "at":
            email += "@"
        elif token == "dot":
            email += "."
        elif len(token) == 1 and token.isalnum():
            # Single letter or digit
            email += token
        # else ignore filler words like "underscore", etc.
    return email

# ─── MAIN AUDIO LOOP ─────────────────────────────────────────────────────────────
print("🎙️ AI Caller Agent: speak now (Ctrl+C to exit).")
# Initialize chat history for Groq:
chat_history = [{"role": "system", "content": SYSTEM_PROMPT}]

with sd.RawInputStream(
    samplerate=samplerate,
    blocksize=8000,
    dtype="int16",
    channels=1,
    callback=audio_callback
):
    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            user_text = result.get("text", "")
            if not user_text:
                continue

            print(f"📝 You said: {user_text}")

            ### Booking Flow ###
            if booking_state is None and is_booking_request(user_text):
                # Start booking: let Groq ask for date/time
                chat_history.append({"role": "user", "content": user_text})
                assistant_text = request_via_groq(chat_history)
                chat_history.append({"role": "assistant", "content": assistant_text})
                booking_state = "date_time"
                speak(assistant_text)

            elif booking_state == "date_time":
                dt = parse_date_time(user_text)
                if not dt:
                    # Let Groq re-ask for date/time
                    chat_history.append({"role": "user", "content": user_text})
                    followup = request_via_groq(chat_history + [{
                        "role": "assistant",
                        "content": "I didn't catch the date/time. Please provide the date and start time in the format YYYY-MM-DD HH:MM."
                    }])
                    chat_history.append({"role": "assistant", "content": followup})
                    speak(followup)
                    continue

                booking_details["date"] = dt["date"]
                booking_details["start_time"] = dt["start_time"]
                booking_details["duration_minutes"] = 30

                # Ask for email via Groq with instruction to spell out
                chat_history.append({"role": "user", "content": user_text})
                assistant_text = (
                    "Got date " + dt["date"] + " at " + dt["start_time"] + 
                    ". Please spell your email address one letter at a time, saying 'at' for @ and 'dot' for ., for example: d e v a n s h at g m a i l dot c o m."
                )
                chat_history.append({"role": "assistant", "content": assistant_text})
                booking_state = "email"
                speak(assistant_text)

            elif booking_state == "email":
                # Parse spelled‐out email
                spelled = user_text.strip()
                parsed_email = parse_spelled_email(spelled)

                if not EMAIL_REGEX.match(parsed_email):
                    followup = (
                        "I didn’t get a valid email. Please spell it out again, using single letters, 'at' for @, and 'dot' for ."
                    )
                    chat_history.append({"role": "user", "content": user_text})
                    chat_history.append({"role": "assistant", "content": followup})
                    speak(followup)
                    continue

                booking_details["attendee_email"] = parsed_email

                # Create event
                date = booking_details["date"]
                start_time = booking_details["start_time"]
                duration = booking_details["duration_minutes"]
                hh, mm = map(int, start_time.split(":"))
                start_dt = f"{date}T{start_time}:00"
                total_mins = hh * 60 + mm + duration
                end_hh = total_mins // 60
                end_mm = total_mins % 60
                if end_hh >= 24:
                    end_hh -= 24
                end_time_str = f"{end_hh:02d}:{end_mm:02d}:00"
                end_dt = f"{date}T{end_time_str}"

                try:
                    link = create_calendar_event(
                        summary="Meeting with BuildABrand",
                        start_datetime=start_dt,
                        end_datetime=end_dt,
                        attendee_email=parsed_email
                    )
                except Exception as e:
                    print("🛑 Calendar API error:", repr(e))
                    speak("Sorry, I encountered an error creating the event.")
                    booking_state = None
                    booking_details.clear()
                    continue

                # Let Groq generate confirmation
                chat_history.append({
                    "role": "user",
                    "content": f"Booking details: date {date}, time {start_time}, email {parsed_email}. Event link: {link}"
                })
                assistant_text = request_via_groq(chat_history + [{
                    "role": "assistant",
                    "content": "Confirm the booking to the user briefly."
                }])
                chat_history.append({"role": "assistant", "content": assistant_text})
                speak(assistant_text)

                booking_state = None
                booking_details.clear()

            else:
                # ─── Normal Conversation via Groq ────────────────────────────
                chat_history.append({"role": "user", "content": user_text})
                assistant_text = request_via_groq(chat_history)
                chat_history.append({"role": "assistant", "content": assistant_text})
                speak(assistant_text)