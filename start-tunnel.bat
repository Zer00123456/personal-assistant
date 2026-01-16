@echo off
echo Starting SSH tunnel to VPS...
echo Keep this window open while using the MCP connection.
echo.
echo Press Ctrl+C to stop the tunnel.
echo.
ssh -L 8000:localhost:8000 -N root@72.61.147.47


