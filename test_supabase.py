import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

print("URL:", url)
print("KEY:", "OK" if key else "MISSING")

supabase = create_client(url, key)

result = supabase.table("subscribers").select("*").limit(10).execute()

print("DATABASE:")
print(result.data)