# -*- coding: utf-8 -*-
"""
羁绊 AI · 后端启动入口
命令：cd backend && python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""
from kizuna.app import create_app

app = create_app()
