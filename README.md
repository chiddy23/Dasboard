# JustInsurance Student Progress Dashboard

A **production-ready, multi-tenant SaaS dashboard** for tracking student progress through pre-licensing insurance courses hosted on Absorb LMS.

![JustInsurance Logo](https://justinsuranceco.com/wp-content/uploads/2025/12/Untitled-design-50.png)

## Features

- **Multi-Tenant Authentication**: Agencies log in with their Absorb LMS credentials and Department ID
- **Real-Time Progress Tracking**: View student progress, time spent, and course completion
- **Smart Status Indicators**:
  - 🟢 **Active** - Logged in within 24 hours
  - 🟡 **Warning** - 24-72 hours since last login
  - 🔴 **Re-engage** - 72+ hours since last login
- **Interactive Dashboard**: KPI cards, searchable student table, filtering
- **Visual Analytics**: Doughnut and bar charts for progress distribution
- **CSV Export**: Export student data for reporting
- **Responsive Design**: Works on desktop and mobile devices
- **Secure**: Rate limiting, session management, input validation

## Tech Stack

- **Backend**: Python Flask
- **Frontend**: React 18 with Vite
- **Styling**: Tailwind CSS
- **Charts**: Chart.js with react-chartjs-2
- **API**: Absorb LMS REST API v2

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Absorb LMS API credentials

### 1. Clone and Setup

```bash
cd justinsurance-student-dashboard

# Copy environment file
cp .env.example .env

# Edit .env with your Absorb API credentials
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run backend server
python app.py
```

Backend will run on http://localhost:5000

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Frontend will run on http://localhost:3000

### 4. Access the Dashboard

1. Open http://localhost:3000
2. Enter your Absorb LMS username
3. Enter your Absorb LMS password
4. Enter your Agency Department ID (GUID format)
5. Click "Access Dashboard"

## Environment Variables

Create a `.env` file in the root directory:

```env
# Absorb LMS API Credentials (MASTER - for backend only)
ABSORB_BASE_URL=https://rest.myabsorb.com
ABSORB_TENANT_URL=https://yourinsurancelicense.myabsorb.com
ABSORB_API_KEY=your_api_key_here
ABSORB_PRIVATE_KEY=your_private_key_here

# Flask Configuration
FLASK_SECRET_KEY=your_secure_random_key_here
FLASK_ENV=development
FLASK_DEBUG=True

# Rate Limiting
RATE_LIMIT_PER_MINUTE=10

# Frontend URL (for CORS)
FRONTEND_URL=http://localhost:3000
```

## Docker Deployment

### Production Build

```bash
# Build and run production container
docker-compose up --build

# Access at http://localhost:8080
```

### Development Mode

```bash
# Run with hot reload for development
docker-compose --profile dev up
```

## API Endpoints

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Authenticate with Absorb credentials |
| `/api/auth/logout` | POST | End current session |
| `/api/auth/session` | GET | Get current session info |

### Dashboard

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard/summary` | GET | Get KPI summary data |
| `/api/dashboard/students` | GET | Get all students with progress |
| `/api/dashboard/sync` | POST | Force refresh data from Absorb |
| `/api/dashboard/export` | GET | Export students as CSV |

### Students

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/students/{id}` | GET | Get detailed student info |
| `/api/students/{id}/enrollments` | GET | Get student's enrollments |

## Project Structure

```
justinsurance-student-dashboard/
├── backend/
│   ├── app.py                 # Flask application
│   ├── absorb_api.py          # Absorb LMS API client
│   ├── config.py              # Configuration management
│   ├── routes/
│   │   ├── auth.py            # Authentication routes
│   │   ├── dashboard.py       # Dashboard data routes
│   │   └── students.py        # Student detail routes
│   ├── middleware/
│   │   ├── auth_middleware.py # Authentication checks
│   │   └── rate_limiter.py    # Rate limiting
│   └── utils/
│       ├── validators.py      # Input validation
│       └── formatters.py      # Data formatting
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Main application
│   │   ├── components/
│   │   │   ├── Login.jsx      # Login page
│   │   │   ├── Dashboard.jsx  # Main dashboard
│   │   │   ├── KPICards.jsx   # KPI summary cards
│   │   │   ├── StudentTable.jsx
│   │   │   ├── StudentModal.jsx
│   │   │   ├── Charts.jsx     # Analytics charts
│   │   │   ├── StatusBadge.jsx
│   │   │   └── ProgressBar.jsx
│   │   └── styles/
│   │       └── main.css       # Tailwind + custom styles
│   └── package.json
├── .env                       # Environment variables
├── docker-compose.yml         # Docker configuration
├── Dockerfile                 # Production Dockerfile
└── README.md
```

## Deployment Options

### Render.com

1. Connect your GitHub repository
2. Create a new Web Service
3. Set build command: `pip install -r backend/requirements.txt && cd frontend && npm install && npm run build`
4. Set start command: `cd backend && gunicorn app:app`
5. Add environment variables from `.env`

### Railway.app

1. Connect your GitHub repository
2. Railway will auto-detect the Dockerfile
3. Add environment variables in the dashboard

### Cloudflare Workers

For a serverless approach, the backend can be adapted to run on Cloudflare Workers using the Workers API.

## Security Features

- **Rate Limiting**: Login attempts limited to 10/minute per IP
- **Session Security**: HttpOnly, Secure, SameSite cookies
- **Input Validation**: All inputs sanitized and validated
- **Token Expiry**: Sessions expire after 4 hours (matching Absorb tokens)
- **Department Isolation**: Users can only see students in their department

## Troubleshooting

### 403 Forbidden from Absorb API

Ensure both headers are included in API requests:
- `x-api-key`: Your API key
- `Authorization`: Bearer token

### Token Expiration

Absorb tokens expire after 4 hours. Users will be redirected to login when their session expires.

### CORS Issues

Make sure `FRONTEND_URL` in `.env` matches your frontend's URL.

## Support

For support or questions:
- Email: support@justinsuranceco.com
- GitHub Issues: [Create an issue](https://github.com/justinsurance/student-dashboard/issues)

## License

Copyright 2026 JustInsurance. All rights reserved.
