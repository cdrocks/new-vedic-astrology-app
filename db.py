import os
import re
from datetime import datetime
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor


DB_URL = os.getenv("SUPABASE_DB_URL")


def get_connection():
    if not DB_URL:
        raise ValueError("SUPABASE_DB_URL environment variable not set")
    return psycopg2.connect(DB_URL)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_valid_email(email: str) -> bool:
    return bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', email))


# --- USERS ---
def add_user(email: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, total_purchased, total_used)
                VALUES (%s, 0, 0)
                ON CONFLICT (email) DO NOTHING
                """,
                (normalize_email(email),)
            )
            conn.commit()
    finally:
        conn.close()


def get_user(email: str):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (normalize_email(email),))
            return cur.fetchone()
    finally:
        conn.close()


def update_user_credits(email: str, purchased: int = 0, used: int = 0):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET total_purchased = total_purchased + %s,
                    total_used = total_used + %s,
                    last_active = NOW()
                WHERE email = %s
                """,
                (purchased, used, normalize_email(email))
            )
            conn.commit()
    finally:
        conn.close()


# --- CHARTS ---
def add_chart(email: str, chart_id: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO charts (email, chart_id, free_used, paid_used)
                VALUES (%s, %s, 0, 0)
                ON CONFLICT (email, chart_id) DO NOTHING
                """,
                (normalize_email(email), chart_id)
            )
            conn.commit()
    finally:
        conn.close()


def get_chart(email: str, chart_id: str):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM charts WHERE email = %s AND chart_id = %s",
                (normalize_email(email), chart_id)
            )
            return cur.fetchone()
    finally:
        conn.close()


def use_free_question(email: str, chart_id: str) -> bool:
    chart = get_chart(email, chart_id)
    if not chart:
        add_chart(email, chart_id)
        chart = get_chart(email, chart_id)
    if chart["free_used"] >= 3:
        return False
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE charts
                SET free_used = free_used + 1, last_active = NOW()
                WHERE email = %s AND chart_id = %s
                """,
                (normalize_email(email), chart_id)
            )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def get_free_remaining(email: str, chart_id: str) -> int:
    chart = get_chart(email, chart_id)
    if not chart:
        return 3
    return max(0, 3 - chart["free_used"])


def use_paid_question(email: str, chart_id: str) -> bool:
    chart = get_chart(email, chart_id)
    if not chart:
        add_chart(email, chart_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE charts
                SET paid_used = paid_used + 1, last_active = NOW()
                WHERE email = %s AND chart_id = %s
                """,
                (normalize_email(email), chart_id)
            )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


# --- ORDERS ---
def add_order(order_id: str, email: str, plan: str, credits: int, amount: str, status: str = "pending"):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (order_id, email, plan, credits, amount, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (order_id) DO NOTHING
                """,
                (order_id, normalize_email(email), plan, credits, amount, status)
            )
            conn.commit()
    finally:
        conn.close()


def get_order(order_id: str):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
            return cur.fetchone()
    finally:
        conn.close()


def mark_order_paid(order_id: str) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE orders SET status = 'paid' WHERE order_id = %s",
                (order_id,)
            )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


# --- PAID CREDITS ---
def get_paid_remaining(email: str) -> int:
    user = get_user(email)
    if not user:
        return 0
    return max(0, user["total_purchased"] - user["total_used"])


def deduct_paid_credit(email: str) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET total_used = total_used + 1, last_active = NOW()
                WHERE email = %s AND total_used < total_purchased
                """,
                (normalize_email(email),)
            )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


# --- LOGS ---
def log_interaction(
    email: str,
    chart_id: str,
    question_number: int,
    question_type: str,
    safety_status: str,
    safety_flag: str,
    question: str,
    answer: str,
    order_id: str = "",
    ip_address: str = "",
    workflow: str = "",
    error: str = "",
):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO logs
                (email, chart_id, question_number, question_type, safety_status,
                 safety_flag, question, answer, order_id, ip_address, workflow, error)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    normalize_email(email),
                    chart_id,
                    question_number,
                    question_type,
                    safety_status,
                    safety_flag,
                    question,
                    answer,
                    order_id,
                    ip_address,
                    workflow,
                    error,
                )
            )
            conn.commit()
    finally:
        conn.close()
