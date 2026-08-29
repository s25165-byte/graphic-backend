import html
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from supabase import create_client


# ============================================================
# 基本设置
# ============================================================

ROOT = Path(__file__).resolve().parent

ADMIN_USERNAME = "admin"

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "12345678"
)


# ============================================================
# Supabase
# ============================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# 如果使用一个环境变量：
#
# SUPABASE_CONFIG=
# https://xxxxx.supabase.co|sb_xxxxx

if not SUPABASE_URL or not SUPABASE_KEY:
    config = os.environ.get("SUPABASE_CONFIG", "")

    if "|" in config:
        SUPABASE_URL, SUPABASE_KEY = config.split("|", 1)

SUPABASE_URL = SUPABASE_URL.strip()
SUPABASE_KEY = SUPABASE_KEY.strip()

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Missing SUPABASE_URL / SUPABASE_KEY"
    )

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ============================================================
# Session
# ============================================================

SESSIONS = set()


# ============================================================
# Supabase 数据库
# ============================================================

def add_email(email):

    try:
        result = (
            supabase
            .table("subscribers")
            .select("id, email, starred")
            .eq("email", email)
            .limit(1)
            .execute()
        )

        if result.data:
            existing = result.data[0]

            if existing.get("starred"):
                return "blocked"

            return "exists"

        supabase.table("subscribers").insert({
            "email": email,
            "starred": False
        }).execute()

        return "success"

    except Exception as e:
        print("ADD EMAIL ERROR:", e)
        return "error"


def get_emails():

    try:
        result = (
            supabase
            .table("subscribers")
            .select(
                "id, email, created_at, starred"
            )
            .order(
                "id",
                desc=True
            )
            .execute()
        )

        return result.data or []

    except Exception as e:
        print("GET EMAILS ERROR:", e)
        return []


def delete_email(email_id):

    try:
        result = (
            supabase
            .table("subscribers")
            .select("id, starred")
            .eq("id", email_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            return "not_found"

        record = result.data[0]

        # ⭐保护的邮箱不能删除
        if record.get("starred"):
            return "starred"

        supabase.table("subscribers").delete().eq(
            "id",
            email_id
        ).execute()

        return "deleted"

    except Exception as e:
        print("DELETE EMAIL ERROR:", e)
        return "error"


def star_email(email_id):

    try:
        result = (
            supabase
            .table("subscribers")
            .update({
                "starred": True
            })
            .eq("id", email_id)
            .execute()
        )

        if result.data:
            return True

        return False

    except Exception as e:
        print("STAR EMAIL ERROR:", e)
        return False


# ============================================================
# HTTP Server
# ============================================================

class WebsiteServer(BaseHTTPRequestHandler):

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    def send_json(self, status, data):

        body = json.dumps(
            data,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.end_headers()

        self.wfile.write(body)

    # --------------------------------------------------------
    # Cookie
    # --------------------------------------------------------

    def get_session(self):

        cookie = self.headers.get(
            "Cookie",
            ""
        )

        for item in cookie.split(";"):

            item = item.strip()

            if item.startswith("session="):

                return item.split(
                    "=",
                    1
                )[1]

        return None

    def is_logged_in(self):

        session = self.get_session()

        return (
            session is not None
            and session in SESSIONS
        )

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    def do_GET(self):

        path = urlparse(
            self.path
        ).path

        # 首页
        if (
            path == "/"
            or path == "/ggsjxh.html"
        ):

            self.serve_file(
                ROOT / "ggsjxh.html",
                "text/html; charset=utf-8"
            )

            return

        # CSS
        if path.startswith("/css/"):

            file_path = (
                ROOT /
                path.lstrip("/")
            )

            if file_path.is_file():

                self.serve_file(
                    file_path,
                    "text/css; charset=utf-8"
                )

                return

        # JavaScript
        if path.startswith("/js/"):

            file_path = (
                ROOT /
                path.lstrip("/")
            )

            if file_path.is_file():

                self.serve_file(
                    file_path,
                    "application/javascript; charset=utf-8"
                )

                return

        # 管理员登录
        if path == "/admin/login":

            self.login_page()

            return

        # 管理后台
        if path == "/admin":

            if not self.is_logged_in():

                self.redirect(
                    "/admin/login"
                )

                return

            self.admin_page()

            return

        # 登出
        if path == "/admin/logout":

            session = self.get_session()

            if session in SESSIONS:

                SESSIONS.remove(session)

            self.send_response(302)

            self.send_header(
                "Location",
                "/admin/login"
            )

            self.send_header(
                "Set-Cookie",
                "session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict"
            )

            self.end_headers()

            return

        self.send_error(
            404,
            "Not Found"
        )

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    def do_POST(self):

        path = urlparse(
            self.path
        ).path

        # ====================================================
        # 管理员登录
        # ====================================================

        if path == "/admin/login":

            length = int(
                self.headers.get(
                    "Content-Length",
                    "0"
                )
            )

            raw_data = self.rfile.read(
                length
            )

            data = parse_qs(
                raw_data.decode("utf-8")
            )

            username = data.get(
                "username",
                [""]
            )[0]

            password = data.get(
                "password",
                [""]
            )[0]

            if (
                secrets.compare_digest(
                    username,
                    ADMIN_USERNAME
                )
                and
                secrets.compare_digest(
                    password,
                    ADMIN_PASSWORD
                )
            ):

                session = secrets.token_urlsafe(32)

                SESSIONS.add(session)

                self.send_response(302)

                self.send_header(
                    "Location",
                    "/admin"
                )

                self.send_header(
                    "Set-Cookie",
                    f"session={session}; Path=/; HttpOnly; SameSite=Strict"
                )

                self.end_headers()

                return

            self.login_page(
                "Incorrect username or password."
            )

            return

        # ====================================================
        # 报名
        # ====================================================

        if path == "/subscribe":

            length = int(
                self.headers.get(
                    "Content-Length",
                    "0"
                )
            )

            raw_data = self.rfile.read(
                length
            )

            content_type = self.headers.get(
                "Content-Type",
                ""
            )

            if "application/json" in content_type:

                try:

                    data = json.loads(
                        raw_data.decode("utf-8")
                    )

                    email = str(
                        data.get(
                            "email",
                            ""
                        )
                    ).strip().lower()

                except Exception:

                    self.send_json(
                        400,
                        {
                            "error":
                            "Invalid data."
                        }
                    )

                    return

            else:

                data = parse_qs(
                    raw_data.decode("utf-8")
                )

                email = data.get(
                    "email",
                    [""]
                )[0].strip().lower()

            # Gmail 检查
            if not email.endswith("@gmail.com"):

                self.send_json(
                    400,
                    {
                        "error":
                        "Please enter a valid Gmail address."
                    }
                )

                return

            result = add_email(email)

            if result == "success":

                self.send_json(
                    201,
                    {
                        "message":
                        "Registration successful!"
                    }
                )

            elif result == "blocked":

                self.send_json(
                    403,
                    {
                        "error":
                        "This email has been blocked."
                    }
                )

            elif result == "exists":

                self.send_json(
                    200,
                    {
                        "message":
                        "This email is already registered."
                    }
                )

            else:

                self.send_json(
                    500,
                    {
                        "error":
                        "Database error."
                    }
                )

            return

        # ====================================================
        # ⭐ 标记
        # ====================================================

        if path.startswith("/admin/star/"):

            if not self.is_logged_in():

                self.send_json(
                    401,
                    {
                        "error":
                        "Unauthorized."
                    }
                )

                return

            email_id = path.split("/")[-1]

            if not email_id.isdigit():

                self.send_json(
                    400,
                    {
                        "error":
                        "Invalid ID."
                    }
                )

                return

            if star_email(int(email_id)):

                self.send_json(
                    200,
                    {
                        "message":
                        "Starred successfully."
                    }
                )

            else:

                self.send_json(
                    404,
                    {
                        "error":
                        "Email not found."
                    }
                )

            return

        # ====================================================
        # 删除
        # ====================================================

        if path.startswith("/admin/delete/"):

            if not self.is_logged_in():

                self.send_json(
                    401,
                    {
                        "error":
                        "Unauthorized."
                    }
                )

                return

            email_id = path.split("/")[-1]

            if not email_id.isdigit():

                self.send_json(
                    400,
                    {
                        "error":
                        "Invalid ID."
                    }
                )

                return

            result = delete_email(
                int(email_id)
            )

            if result == "deleted":

                self.send_json(
                    200,
                    {
                        "message":
                        "Deleted successfully."
                    }
                )

            elif result == "starred":

                self.send_json(
                    403,
                    {
                        "error":
                        "Starred emails cannot be deleted."
                    }
                )

            else:

                self.send_json(
                    404,
                    {
                        "error":
                        "Email not found."
                    }
                )

            return

        self.send_error(
            404,
            "Not Found"
        )

    # --------------------------------------------------------
    # 文件
    # --------------------------------------------------------

    def serve_file(
        self,
        file_path,
        content_type
    ):

        if not file_path.is_file():

            self.send_error(
                404,
                "File not found"
            )

            return

        body = file_path.read_bytes()

        self.send_response(200)

        self.send_header(
            "Content-Type",
            content_type
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.end_headers()

        self.wfile.write(body)

    # --------------------------------------------------------
    # Redirect
    # --------------------------------------------------------

    def redirect(
        self,
        location
    ):

        self.send_response(302)

        self.send_header(
            "Location",
            location
        )

        self.end_headers()

    # --------------------------------------------------------
    # Login
    # --------------------------------------------------------

    def login_page(
        self,
        error=""
    ):

        error_html = ""

        if error:

            error_html = f"""
            <p style="color:red;">
                {html.escape(error)}
            </p>
            """

        page = f"""
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Admin Login</title>

<style>

body {{
    font-family: Arial, sans-serif;
    background: #f5f5f5;

    display: flex;
    justify-content: center;
    align-items: center;

    min-height: 100vh;
}}

.login-box {{
    background: white;

    width: 320px;

    padding: 30px;

    border-radius: 12px;

    box-shadow:
        0 5px 25px rgba(0,0,0,0.1);
}}

h1 {{
    margin-top: 0;
}}

input {{
    width: 100%;
    box-sizing: border-box;

    padding: 12px;

    margin: 8px 0 15px;

    border: 1px solid #ccc;

    border-radius: 6px;
}}

button {{
    width: 100%;

    padding: 12px;

    border: none;

    border-radius: 6px;

    cursor: pointer;
}}

</style>

</head>

<body>

<div class="login-box">

<h1>Admin Login</h1>

{error_html}

<form method="POST"
      action="/admin/login">

<label>Username</label>

<input
    type="text"
    name="username"
    autocomplete="username"
    required
>

<label>Password</label>

<input
    type="password"
    name="password"
    autocomplete="current-password"
    required
>

<button type="submit">
    Login
</button>

</form>

</div>

</body>

</html>
"""

        body = page.encode("utf-8")

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.end_headers()

        self.wfile.write(body)

    # --------------------------------------------------------
    # Admin Dashboard
    # --------------------------------------------------------

    def admin_page(self):

        subscribers = get_emails()

        rows = ""

        active_count = 0
        starred_count = 0

        for item in subscribers:

            email_id = item["id"]
            email = item["email"]
            created_at = item["created_at"]
            starred = item.get(
                "starred",
                False
            )

            if starred:
                starred_count += 1
            else:
                active_count += 1

            if starred:

                star_button = """
                <span
                    style="
                    font-size:24px;
                    color:gold;
                    "
                    title="Blocked email"
                >
                    ★
                </span>
                """

            else:

                star_button = f"""
                <button
                    onclick="starEmail({email_id})"
                    title="Block this email"
                >
                    ☆
                </button>
                """

            if starred:

                delete_button = """
                <span
                    style="color:#999;"
                    title="Starred emails cannot be deleted"
                >
                    Protected
                </span>
                """

            else:

                delete_button = f"""
                <button
                    onclick="deleteEmail({email_id})"
                >
                    Delete
                </button>
                """

            rows += f"""
            <tr>

                <td>
                    {email_id}
                </td>

                <td>
                    {html.escape(email)}
                </td>

                <td>
                    {html.escape(str(created_at))}
                </td>

                <td>
                    {star_button}
                </td>

                <td>
                    {delete_button}
                </td>

            </tr>
            """

        if not rows:

            rows = """
            <tr>

                <td colspan="5">
                    No registrations yet.
                </td>

            </tr>
            """

        page = f"""
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Admin Dashboard</title>

<style>

body {{
    font-family: Arial, sans-serif;

    max-width: 1100px;

    margin: 40px auto;

    padding: 20px;
}}

.header {{
    display: flex;

    justify-content: space-between;

    align-items: center;

    margin-bottom: 25px;
}}

.actions {{
    display: flex;

    gap: 10px;
}}

.logout,
.refresh {{
    text-decoration: none;

    padding: 8px 14px;

    border: 1px solid #ccc;

    border-radius: 6px;

    background: white;

    cursor: pointer;
}}

table {{
    width: 100%;

    border-collapse: collapse;
}}

th,
td {{
    padding: 12px;

    border-bottom: 1px solid #ddd;

    text-align: left;
}}

button {{
    padding: 7px 12px;

    cursor: pointer;
}}

.stats {{
    display: flex;

    gap: 30px;

    margin-bottom: 20px;
}}

.stat {{
    padding: 12px 18px;

    border: 1px solid #ddd;

    border-radius: 8px;
}}

</style>

</head>

<body>

<div class="header">

<h1>Registration Dashboard</h1>

<div class="actions">

<button
    class="refresh"
    onclick="refreshData()">
    ↻ Refresh
</button>

<a
    class="logout"
    href="/admin/logout">
    Logout
</a>

</div>

</div>

<div class="stats">

<div class="stat">
Active:
<strong>{active_count}</strong>
</div>

<div class="stat">
⭐ Protected:
<strong>{starred_count}</strong>
</div>

<div class="stat">
Total:
<strong>{len(subscribers)}</strong>
</div>

</div>

<table>

<thead>

<tr>

<th>ID</th>

<th>Email</th>

<th>Time</th>

<th>Star</th>

<th>Action</th>

</tr>

</thead>

<tbody>

{rows}

</tbody>

</table>

<script>

async function starEmail(id) {{

    if (!confirm(
        "Star this email?\\n\\n" +
        "Once starred, this Gmail cannot be registered again."
    )) {{
        return;
    }}

    const response = await fetch(
        "/admin/star/" + id,
        {{
            method: "POST"
        }}
    );

    if (response.ok) {{
        location.reload();
    }} else {{
        alert("Failed to star this email.");
    }}
}}


async function deleteEmail(id) {{

    if (!confirm(
        "Delete this email?"
    )) {{
        return;
    }}

    const response = await fetch(
        "/admin/delete/" + id,
        {{
            method: "POST"
        }}
    );

    if (response.ok) {{
        location.reload();
    }} else {{

        const data = await response.json()
            .catch(() => ({{}}));

        alert(
            data.error ||
            "Failed to delete."
        );
    }}
}}


function refreshData() {{

    location.reload();

}}

</script>

</body>

</html>
"""

        body = page.encode("utf-8")

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.end_headers()

        self.wfile.write(body)


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":

    PORT = int(
        os.environ.get(
            "PORT",
            8000
        )
    )

    server = ThreadingHTTPServer(
        ("0.0.0.0", PORT),
        WebsiteServer
    )

    print("================================")
    print("Graphic Backend")
    print()
    print("Port:", PORT)
    print("Supabase:", SUPABASE_URL)
    print()
    print("Admin:")
    print("/admin")
    print()
    print("Username:")
    print(ADMIN_USERNAME)
    print("================================")

    server.serve_forever()
