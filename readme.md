[Patient UI] ---> [FastAPI API Layer] ---> [Redis Queue]
                                   ↘︎
                                [PostgreSQL - Logging]
                                   ↘︎
                                [Monitoring & Alerts]
# QTrack - Real-Time Queue Management System

A scalable real-time queue management application that handles patient queuing with live updates and monitoring.

## Architecture

```
[Patient UI] ---> [FastAPI API Layer] ---> [Redis Queue]
                                   ↘︎
                                [PostgreSQL - Logging]
                                   ↘︎
                                [Monitoring & Alerts]
```

## Tech Stack

- **Backend**: FastAPI, Python 3.13
- **Frontend**: React, TypeScript, Vite
- **Database**: PostgreSQL (logging), Redis (real-time queue)
- **Real-time**: Server-Sent Events (SSE), Redis Streams
- **Containerization**: Docker Compose

## Prerequisites

- Python 3.13+
- Node.js 18+
- Docker & Docker Compose
- Git

## Setup Instructions

### 1. Clone and Navigate
```bash
git clone <repository-url>
cd Qtrack-app
```

### 2. Backend Setup

#### Environment Configuration
Create `.env` file in `backend/` directory:
```env
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=qtrack_db
```

#### Virtual Environment (Recommended)
```bash
# Activate existing virtual environment
# On Windows:
Scripts\activate
# On macOS/Linux:
venv\Scripts\Activate.ps1

# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
```

#### Install Dependencies
```bash
cd backend/app
pip install -r requirements.txt
```

### 3. Database & Redis Setup

#### Using Docker Compose (Recommended)
```bash
cd backend
docker-compose up -d
```

This will start:
- PostgreSQL database on port 5432
- Redis server on port 6379

#### Manual Setup
If not using Docker, ensure PostgreSQL and Redis are running locally on default ports.

### 4. Frontend Setup
```bash
cd frontend/qtrack-frontend
npm install
```

## Running the Application

### Start Backend Server
```bash
cd backend/app
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Start Frontend Development Server
```bash
cd frontend/qtrack-frontend
npm run dev
```

### Access the Application
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## API Endpoints

### Core Functionality
- `GET /health-check` - Health check endpoint
- `POST /join-queue` - Add patient to queue
- `GET /live-queue/{branch_id}` - Get current queue status
- `GET /live-queue-stream/{branch_id}` - Real-time queue updates (SSE)
- `PUT /update-status` - Update patient status
- `DELETE /remove-from-queue` - Remove patient from queue
- `DELETE /remove-log` - Remove queue log entry

### Example Usage

#### Join Queue
```bash
curl -X POST "http://localhost:8000/join-queue" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "phone": "1234567890",
    "branch_id": "ENT"
  }'
```

#### Get Live Queue
```bash
curl "http://localhost:8000/live-queue/ENT"
```

## Key Features

- **Real-time Updates**: Uses Redis Streams and Server-Sent Events for live queue monitoring
- **Scalable Architecture**: FastAPI async support handles 1000+ concurrent users
- **Dual Storage**: Redis for real-time data, PostgreSQL for persistent logging
- **Status Management**: Track patient status (waiting, called, completed, etc.)
- **Branch Support**: Multi-branch queue management

## Development Scripts

### Reset Queue Data
```bash
cd backend/app
python -m scripts.redis_generate_data
```

## Project Structure

```
Qtrack-app/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── requirements.txt      # Python dependencies
│   │   ├── models/
│   │   │   ├── schemas.py       # Pydantic models
│   │   │   └── db_models.py     # SQLAlchemy models
│   │   ├── services/
│   │   │   ├── redis_client.py  # Redis connection
│   │   │   └── db.py           # PostgreSQL connection
│   │   └── scripts/
│   │       └── redis_generate_data.py
│   └── docker-compose.yaml     # Database services
├── frontend/
│   └── qtrack-frontend/        # React TypeScript app
└── readme.md
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_USER` | PostgreSQL username | - |
| `DB_PASSWORD` | PostgreSQL password | - |
| `DB_HOST` | Database host | localhost |
| `DB_PORT` | Database port | 5432 |
| `DB_NAME` | Database name | qtrack_db |

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Ensure PostgreSQL is running
   - Check `.env` file configuration
   - Verify database exists

2. **Redis Connection Error**
   - Ensure Redis server is running on port 6379
   - Check Docker Compose services

3. **Frontend Build Issues**
   - Clear node_modules: `rm -rf node_modules && npm install`
   - Check Node.js version compatibility

### Logs
- Backend logs: Check uvicorn console output
- Database logs: `docker-compose logs postgres`
- Redis logs: `docker-compose logs redis`

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit Pull Request

## License

[Add your license information here]
```

✅ Real-time updates - SSE streams immediately push queue changes
✅ Clean heartbeats - Only every 30 seconds instead of constant pings
✅ Proper Redis Streams - Consistent event publishing across all endpoints
✅ Immediate responsiveness - Changes appear instantly when APIs return 200