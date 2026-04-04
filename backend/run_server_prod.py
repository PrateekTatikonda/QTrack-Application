#!/usr/bin/env python3
"""
QTrack Backend Server Runner - Production Mode
Run the FastAPI application with uvicorn (no reload)
"""

import uvicorn
import os
import sys
from pathlib import Path

# Add the app directory to Python path
current_dir = Path(__file__).parent
app_dir = current_dir / "app"
sys.path.insert(0, str(app_dir))

def main():
    """Run the FastAPI server in production mode"""
    try:
        print("🚀 Starting QTrack Backend Server (Production Mode)...")
        print("📍 Server will be available at: http://localhost:8000")
        print("📖 API Documentation: http://localhost:8000/docs")
        print("⚡ Production mode: No auto-reload")
        print("❌ Press Ctrl+C to stop the server")
        print("-" * 50)
        
        # Change to app directory to ensure proper imports
        os.chdir(app_dir)
        
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            log_level="info",
            access_log=True,
            workers=1,
        )
        
    except KeyboardInterrupt:
        print("\n\n⭐ QTrack Backend Server stopped successfully!")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()