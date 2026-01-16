#!/bin/bash
# Start all services for the Personal Assistant

cd /root/personal-assistant

# Start API server in background
echo "🚀 Starting API server..."
python3 api_server.py &
API_PID=$!

# Wait for API to be ready
sleep 3

# Start Discord bot in background  
echo "🤖 Starting Discord bot..."
python3 -m src.main &
BOT_PID=$!

echo "✅ All services started"
echo "   API Server PID: $API_PID"
echo "   Discord Bot PID: $BOT_PID"

# Keep script running
wait

