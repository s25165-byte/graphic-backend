
import html
import json
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ============================================================
# 基本设置
# ============================================================

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "subscribers.db"

# 管理员账号
ADMIN_USERNAME = "admin"

# !!! 把这里改成你自己的密码 !!!
ADMIN_PASSWORD = "12345678"

# 登录 Session
SESSIONS = set()


# ============================================================
# 数据库
# ============================================================

def init_database():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def add_email(email):
    with sqlite3.connect(DATABASE) as conn:
        try:
            conn.execute(
                "INSERT INTO subscribers (email) VALUES (?)",
                (email,)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def get_emails():
    with sqlite3.connect(DATABASE) as conn:
        return conn.execute("""
            SELECT id, email, created_at
            FROM subscribers
            ORDER BY id DESC
        """).fetchall()


def delete_email(email_id):
    with sqlite3.connect(DATABASE) as conn:
        conn.execute(
            "DELETE FROM subscribers WHERE id = ?",
            (email_id,)
        )
        conn.commit()


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

        cookie = self.headers.get("Cookie", "")

        for item in cookie.split(";"):

            item = item.strip()

            if item.startswith("session="):

                return item.split("=", 1)[1]

        return None


    def is_logged_in(self):

        session = self.get_session()

        return session is not None and session in SESSIONS


    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    def do_GET(self):

        path = urlparse(self.path).path


        # 首页
        if path == "/" or path == "/ggsjxh.html":

            self.serve_file(
                ROOT / "ggsjxh.html",
                "text/html; charset=utf-8"
            )

            return


        # CSS
        if path.startswith("/css/"):

            file_path = ROOT / path.lstrip("/")

            if file_path.is_file():

                self.serve_file(
                    file_path,
                    "text/css; charset=utf-8"
                )

                return


        # JavaScript
        if path.startswith("/js/"):

            file_path = ROOT / path.lstrip("/")

            if file_path.is_file():

                self.serve_file(
                    file_path,
                    "application/javascript; charset=utf-8"
                )

                return


        # 登录页面
        if path == "/admin/login":

            self.login_page()

            return


        # 管理后台
        if path == "/admin":

            if not self.is_logged_in():

                self.redirect("/admin/login")

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


        self.send_error(404, "Not Found")


    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    def do_POST(self):

        path = urlparse(self.path).path


        # ====================================================
        # 登录
        # ====================================================

        if path == "/admin/login":

            length = int(
                self.headers.get(
                    "Content-Length",
                    "0"
                )
            )

            raw_data = self.rfile.read(length)

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


            # 检查账号密码
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


            # 登录失败
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

            raw_data = self.rfile.read(length)

            content_type = self.headers.get(
                "Content-Type",
                ""
            )


            # JSON
            if "application/json" in content_type:

                try:

                    data = json.loads(
                        raw_data.decode("utf-8")
                    )

                    email = str(
                        data.get("email", "")
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


            # Form
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


            # 保存
            if add_email(email):

                self.send_json(
                    201,
                    {
                        "message":
                        "Registration successful!"
                    }
                )

            else:

                self.send_json(
                    200,
                    {
                        "message":
                        "This email is already registered."
                    }
                )

            return


        # ====================================================
        # 删除
        # ====================================================

        if path.startswith("/admin/delete/"):

            # 必须登录
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

            if email_id.isdigit():

                delete_email(
                    int(email_id)
                )

                self.send_json(
                    200,
                    {
                        "message":
                        "Deleted successfully."
                    }
                )

                return


        self.send_error(404, "Not Found")


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

    def redirect(self, location):

        self.send_response(302)

        self.send_header(
            "Location",
            location
        )

        self.end_headers()


    # --------------------------------------------------------
    # 登录页面
    # --------------------------------------------------------

    def login_page(self, error=""):

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
    # Admin
    # --------------------------------------------------------

    def admin_page(self):

        subscribers = get_emails()

        rows = ""


        for email_id, email, created_at in subscribers:

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

                    <button
                        onclick="deleteEmail({email_id})">
                        Delete
                    </button>

                </td>

            </tr>
            """


        if not rows:

            rows = """
            <tr>

                <td colspan="4">
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

    max-width: 1000px;

    margin: 40px auto;

    padding: 20px;
}}

.header {{
    display: flex;

    justify-content: space-between;

    align-items: center;

    margin-bottom: 25px;
}}

.logout {{
    text-decoration: none;

    padding: 8px 14px;

    border: 1px solid #ccc;

    border-radius: 6px;
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

</style>

</head>

<body>

<div class="header">

<h1>Registration Dashboard</h1>

<a
    class="logout"
    href="/admin/logout">
    Logout
</a>

</div>


<p>
Total registrations:
<strong>{len(subscribers)}</strong>
</p>


<table>

<thead>

<tr>

<th>ID</th>

<th>Email</th>

<th>Time</th>

<th>Action</th>

</tr>

</thead>


<tbody>

{rows}

</tbody>

</table>


<script>

async function deleteEmail(id) {{

    if (!confirm("Delete this email?")) {{
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
        alert("You are not logged in.");
        location.href = "/admin/login";
    }}

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
# 启动服务器
# ============================================================

if __name__ == "__main__":

    import os

    init_database()

    PORT = int(os.environ.get("PORT", 8000))

    server = ThreadingHTTPServer(
        ("0.0.0.0", PORT),
        WebsiteServer
    )

    print("================================")
    print("Website:")
    print("http://localhost:8000")
    print()
    print("Admin:")
    print("http://localhost:8000/admin")
    print()
    print("Username:")
    print(ADMIN_USERNAME)
    print("================================")

    server.serve_forever()
