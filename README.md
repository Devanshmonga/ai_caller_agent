AI Caller Agent

A Python-based AI receptionist that handles phone calls, answers questions about the “BuildABrand” company, and schedules meetings on Google Calendar. Uses:
	•	Vosk for offline speech-to-text
	•	Groq LLM for conversational responses and booking prompts
	•	Mimic3 (Mycroft) for text-to-speech
	•	Google Calendar API to create events
	•	SoundDevice to capture microphone input and play back audio

⸻

Features
	•	Live conversation: Listen on your Mac’s mic, transcribe speech, generate replies via Groq, and speak replies aloud.
	•	Google Calendar booking: When the caller requests a meeting, the agent asks for date/time (via Groq), then asks the caller to spell their email, and finally creates a 30-minute event in your primary calendar.
	•	Company context: All general queries about BuildABrand’s services receive concise (1–2 sentence) answers.
	•	Spelled-out email: During booking, callers spell their email (“letter by letter, saying ‘at’ for @ and ‘dot’ for .”) so transcription is reliable.

⸻

Prerequisites
	1.	macOS (or Linux) with Python 3.11+
	2.	Docker (for running Mimic3 TTS locally)
	3.	Groq API key (from Groq Cloud)
	4.	Google Cloud project with Calendar API enabled, and a Desktop OAuth client (credentials.json)
	5.	Vosk model: vosk-model-small-en-us-0.15 downloaded and extracted
	6.	An Airtel (or any) SIM/Dongle setup, if you plan to deploy on Asterisk (optional; README focuses on local “mic → speaker” mode)

⸻

Installation
	1.	Clone this repository

git clone https://github.com/your-username/ai-caller-agent.git
cd ai-caller-agent


	2.	Create a Python 3.11+ virtual environment

python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip


	3.	Install Python dependencies

pip install vosk groq google-api-python-client google-auth-httplib2 google-auth-oauthlib requests sounddevice


	4.	Download and place the Vosk model
	•	Download the small English model from:
https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
	•	Extract so you have a folder named vosk-model-small-en-us-0.15 alongside app.py.
	•	Example structure:

ai-caller-agent/
  ├── app.py
  ├── vosk-model-small-en-us-0.15/
  │    ├── conf/
  │    ├── am/
  │    └── ...
  └── README.md


	5.	Obtain your Groq API key
	•	Sign up at Groq Cloud and create an API key.
	•	Export it in your shell (or add to ~/.zshrc / ~/.bashrc):

export GROQ_API_KEY="your_actual_groq_api_key"


	6.	Enable Google Calendar API & place credentials.json
	•	In Google Cloud Console, enable the Google Calendar API for your project.
	•	Create an OAuth 2.0 Client → Desktop type → Download the JSON.
	•	Rename it to credentials.json and place it next to app.py.

⸻

Configuration
	1.	Verify folder structure
	•	app.py
	•	credentials.json (Google OAuth)
	•	vosk-model-small-en-us-0.15/ (Vosk model folder)
	2.	Mimic3 TTS via Docker

docker pull mycroftai/mimic3
docker run -it -p 59125:59125 mycroftai/mimic3

	•	The agent will call http://localhost:59125/api/tts?text=... to get WAV audio.

	3.	Environment variables
	•	GROQ_API_KEY must be exported before running:

export GROQ_API_KEY="your_actual_groq_api_key"


	•	(Optional) If you need a different Google credential filename or path, update get_calendar_service() accordingly.

⸻

Usage
	1.	Start Mimic3 TTS server
In one terminal:

docker run -it -p 59125:59125 mycroftai/mimic3


	2.	Activate your virtual environment & run the app

source venv/bin/activate
python app.py


	3.	Speak through your Mac’s microphone
	•	For general questions about BuildABrand, ask normally (e.g. “What web development services do you offer?”).
	•	To book a meeting, say “Book a meeting.” The agent will:
	1.	Ask “When would you like the meeting? Please say the date and time.”
	2.	You respond (e.g. “2025-06-15 at 14:00”).
	3.	Agent asks “Please spell your email address one letter at a time, saying ‘at’ for @ and ‘dot’ for .”
	4.	You spell (e.g. “d e v a n s h at g m a i l dot c o m”).
	5.	Agent creates a 30-minute event in your Google Calendar and reads back a confirmation with the event link.
	4.	Google OAuth flow
	•	The first time the agent tries to create a calendar event, a browser window will prompt you to authorize.
	•	Sign in with the same Google account you used to create credentials.json.
	•	A token.json file will be created automatically, so you won’t be asked again.
	5.	Stop the agent
	•	Press Ctrl+C to exit.

⸻

Folder Structure

ai-caller-agent/
├── app.py
├── credentials.json        # Google OAuth client (Desktop)
├── token.json              # Created automatically after first authorization
├── vosk-model-small-en-us-0.15/
│    ├── conf/
│    ├── am/
│    └── ...
├── venv/                   # Python virtual environment
└── README.md


⸻

Troubleshooting
	•	“Failed to create model” / Vosk error
	•	Ensure the vosk-model-small-en-us-0.15 folder is in the same directory as app.py.
	•	Use an absolute path in VOSK_MODEL_PATH if needed.
	•	“TTS Error” / Mimic3 not responding
	•	Verify Docker is running Mimic3:

docker ps | grep mimic3


	•	You should see a container listening on port 59125. If not, re-run the Docker command.

	•	Groq errors
	•	Check that GROQ_API_KEY is correctly exported.
	•	Look at the console logs for any stack trace or rate-limit issues.
	•	Google Calendar errors
	•	Delete token.json and re-run if you see “invalid_grant” or “insufficient permissions.”
	•	Ensure credentials.json is the correct OAuth client for “Desktop” type with Calendar scopes enabled.
	•	Confirm your system clock is correct—OAuth fails if your clock is out of sync.
	•	Email parsing issues
	•	The agent expects you to spell out your email one character at a time, using “at” for @ and “dot” for “.”.
	•	Example:

d e v a n s h at g m a i l dot c o m


	•	Audio dropouts or misrecognitions
	•	Ensure your mic input is clear and not too quiet. Vosk may mis-transcribe if there’s background noise.
	•	Try increasing the system volume or using a USB headset.

⸻

Customization
	•	Change default meeting duration
	•	In app.py, modify booking_details["duration_minutes"] from 30 to any other integer.
	•	Adjust LLM parameters
	•	In request_via_groq(), change model, temperature, or max_tokens as desired to tune response length or creativity.
	•	Add more company details
	•	Edit the SYSTEM_PROMPT string to include additional services, company policies, or FAQs you want the agent to know.

⸻

License

This project is released under the MIT License. See LICENSE for details.
