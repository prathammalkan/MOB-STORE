# MobStore

Premium mobile storefront built with Flask, PostgreSQL, and optional Cloudinary image hosting.

## Features

- Responsive storefront with product search, filtering, and sorting
- Customer registration, login, cart, checkout, and order history
- IMEI-based warranty & service request flow
- Admin dashboard: product management, order tracking, revenue stats, and service queue
- PostgreSQL-backed schema with automatic table migration on startup
- Optional Cloudinary integration for product image uploads

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/prathammalkan/MOB-STORE.git
cd MOB-STORE
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

**Required variables:**

| Variable         | Description                              |
|------------------|------------------------------------------|
| `SECRET_KEY`     | Long random string for session signing   |
| `DATABASE_URL`   | PostgreSQL connection string             |
| `ADMIN_USERNAME` | Admin login username (default: `admin`)  |
| `ADMIN_PASSWORD` | Admin login password (**required**)      |

**Optional – Cloudinary image uploads:**

| Variable                | Description              |
|-------------------------|--------------------------|
| `CLOUDINARY_URL`        | Full Cloudinary URL      |
| `CLOUDINARY_CLOUD_NAME` | Cloud name               |
| `CLOUDINARY_API_KEY`    | API key                  |
| `CLOUDINARY_API_SECRET` | API secret               |

**Other:**

| Variable    | Description                             |
|-------------|-----------------------------------------|
| `FLASK_ENV` | Set to `production` for secure cookies  |

### 5. Run locally

```bash
flask run
```

Or with gunicorn:

```bash
gunicorn app:app
```

## Deployment

The app is ready for any platform that supports Python and PostgreSQL (Railway, Render, Fly.io, Heroku, etc.).

Start command:

```
web: gunicorn app:app
```

The app automatically creates all required database tables on first startup.

## Production checklist

1. Set all required environment variables before starting.
2. Create a user account and test the cart → checkout → invoice flow.
3. Access the admin panel at `/admin` with your configured credentials.
4. Add, edit, and delete a product from the admin dashboard.
5. Submit a service request and update its status from admin.

## Notes

- If Cloudinary is not configured, product images fall back to direct URLs.
- `ADMIN_PASSWORD` **must** be set — the app will refuse to start without it.
- `SECRET_KEY` should be a long random string; a random one is generated at startup if absent, but sessions will reset on every restart.
