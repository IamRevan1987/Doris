#!/bin/bash
cd ~/docker/APIinterface/Ancient_Holocron
echo "Starting Ancient_Holocron API on port 8000..."
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
