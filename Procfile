web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true
payment: uvicorn payment_service:app --host=0.0.0.0 --port=${PAYMENT_PORT:-8000}
