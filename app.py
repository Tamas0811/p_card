import os
from dotenv import load_dotenv
from google import genai
import streamlit as st

load_dotenv()

# Load API Key from .env or sidebar
api_key = os.getenv("GEMINI_API_KEY") or st.sidebar.text_input(
    "Enter Google Gemini API Key:", type="password"
)

client = genai.Client(api_key=api_key) if api_key else None


def generate_sql(user_query, schema_info):
    prompt = f"""
    You are a SQLite expert. Given the database schema below, write a single raw SQLite query to answer the user's request.
    Return ONLY the raw SQL query. Do not wrap it in markdown block quotes (e.g. no ```sql), no explanation.

    Schema:
    {schema_info}

    User Question: {user_query}
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    # Clean up any residual markdown formatting
    sql_query = response.text.strip().replace("```sql", "").replace("```", "")
    return sql_query