# Pulse Chat — Real-Time Chat Application

A production-grade real-time chat application built with:
- **Backend**: Python + Django 4.2
- **Real-time**: Django Channels (WebSockets)
- **Frontend**: Vanilla HTML, CSS, JavaScript
- **Database**: SQLite (dev) → PostgreSQL (production)

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run migrations
```bash
python manage.py makemigrations accounts
python manage.py makemigrations chat
python manage.py migrate
```

### 3. Create a superuser (optional)
```bash
python manage.py createsuperuser
```

### 4. Run the development server
```bash
python manage.py runserver
```

Then open http://127.0.0.1:8000 in your browser.

> **Note**: For WebSocket support in development, Daphne is used automatically via ASGI.
> The `runserver` command works because `daphne` is listed first in `INSTALLED_APPS`.

---

## Features

- ✅ **User Authentication** — Register/login with profile picture upload
- ✅ **Real-Time Messaging** — WebSockets via Django Channels
- ✅ **Typing Indicators** — Live "is typing..." notifications
- ✅ **Read Receipts** — ✓ sent, ✓✓ delivered, ✓✓ blue (read)
- ✅ **Online/Offline Presence** — Live status indicators
- ✅ **Emoji Picker** — Built-in emoji selector
- ✅ **File & Image Sharing** — Upload images, PDFs, zip files (10MB max)
- ✅ **Image Lightbox** — Click images to view fullscreen
- ✅ **User Search** — Find users by username
- ✅ **Unread Message Counts** — Badge on conversation list
- ✅ **Message Pagination** — Load older messages on demand
- ✅ **Dark/Light Mode** — Toggle with persistent preference
- ✅ **Responsive Design** — Works on mobile and desktop
- ✅ **Browser Notifications** — Push alerts when tab is unfocused

---

## Production Deployment

### Environment Variables
```bash
SECRET_KEY=your-long-random-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com www.yourdomain.com
```

### PostgreSQL
Uncomment the PostgreSQL DATABASES block in `settings.py` and set:
```bash
DB_NAME=chatapp
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=5432
```

### Redis (for production WebSockets)
Install `channels-redis` and uncomment the Redis channel layer in `settings.py`:
```bash
REDIS_URL=redis://127.0.0.1:6379
```

### Run with Daphne (production)
```bash
daphne -b 0.0.0.0 -p 8000 chatapp.asgi:application
```

### Collect Static Files
```bash
python manage.py collectstatic --no-input
```

---

## Project Structure

```
chatapp/
├── chatapp/          # Django project config
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py       # ASGI + WebSocket routing
├── accounts/         # Auth, user model, profiles
│   ├── models.py     # Custom User model
│   ├── views.py
│   ├── forms.py
│   └── templates/
├── chat/             # Messaging app
│   ├── models.py     # Conversation, Message, FileAttachment
│   ├── consumers.py  # WebSocket consumers
│   ├── routing.py    # WebSocket URL routing
│   ├── views.py
│   └── templates/
├── static/
│   ├── css/main.css  # Full design system
│   └── js/
│       ├── app.js    # Global utils, theme
│       └── chat.js   # WebSocket chat logic
├── templates/
│   └── base.html
├── media/            # User uploads (gitignored)
├── manage.py
└── requirements.txt
```
