import html
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from supabase import create_client, Client


# ============================================================
# 基本设置
# ============================================================

ROOT = Path(__file__).resolve().parent

SUPABASE_URL = "https://iapdvuzqtfizmsuixkct.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY is missing.")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ============================================================
# 管理员账号
# ============================================================

ADMIN_USERNAME = "admin"

# 建议之后改成你自己的密码
ADMIN_PASSWORD = "12345678"


# ============================================================
# 登录 Session
# ============================================================

SESSIONS = set()


# ============================================================
# 数据库
# ============================================================

def add_email(email):

    # 先检查这个 Gmail 是否存在
    result = (
        supabase
        .table("subscribers")
        .select("id, starred")
        .eq("email", email)
        .execute()
    )

    if result.data:

        existing = result.data[0]

        # ⭐ 已经星标
        if existing.get("starred") is True:

            return "starred"

        # 普通重复
        return "exists"


    # 新增
    supabase.table("subscribers").insert({
        "email": email,
        "starred": False
    }).execute()

    return "added"


def get_emails():

    result = (
        supabase
        .table("subscribers")
        .select("id, email, created_at, starred")
        .order("id", desc=True)
        .execute()
    )

    return result.data or []


def delete_email(email_id):

    (
        supabase
        .table("subscribers")
        .delete()
        .eq("id", email_id)
        .execute()
    )


def star_email(email_id):

    (
        supabase
        .table("subscribers")
        .update({
            "starred": True
        })
        .eq("id", email_id)
        .execute()
    )


def unstar_email(email_id):

    (
        supabase
        .table("subscribers")
        .update({
            "starred": False
        })
        .eq("id", email_id)
        .execute()
    )


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

        return (
            session is not None
            and session in SESSIONS
        )


    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    def do_GET(self):

        path = urlparse(self.path).path


        # ====================================================
        # 首页
        # ====================================================

        if path == "/" or path == "/ggsjxh.html":

            self.serve_file(
                ROOT / "ggsjxh.html",
                "text/html; charset=utf-8"
            )

            return


        # ====================================================
        # CSS
        # ====================================================

        if path.startswith("/css/"):

            file_path = ROOT / path.lstrip("/")

            if file_path.is_file():

                self.serve_file(
                    file_path,
                    "text/css; charset=utf-8"
                )

                return


        # ====================================================
        # JavaScript
        # ====================================================

        if path.startswith("/js/"):

            file_path = ROOT / path.lstrip("/")

            if file_path.is_file():

                self.serve_file(
                    file_path,
                    "application/javascript; charset=utf-8"
                )

                return


        # ====================================================
        # 登录页面
        # ====================================================

        if path == "/admin/login":

            self.login_page()

            return


        # ====================================================
        # Admin
        # ====================================================

        if path == "/admin":

            if not self.is_logged_in():

                self.redirect("/admin/login")

                return

            self.admin_page()

            return


        # ====================================================
        # 登出
        # ====================================================

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


            # =================================================
            # Gmail 检查
            # =================================================

            if not email.endswith("@gmail.com"):

                self.send_json(
                    400,
                    {
                        "error":
                        "Please enter a valid Gmail address."
                    }
                )

                return


            # =================================================
            # 保存
            # =================================================

            try:

                result = add_email(email)


                # 新增成功
                if result == "added":

                    self.send_json(
                        201,
                        {
                            "message":
                            "Registration successful!"
                        }
                    )

                    return


                # ⭐ 已锁定
                if result == "starred":

                    self.send_json(
                        403,
                        {
                            "error":
                            "This email has been locked and cannot be registered again."
                        }
                    )

                    return


                # 普通重复
                self.send_json(
                    200,
                    {
                        "message":
                        "This email is already registered."
                    }
                )

            except Exception as e:

                print("Supabase error:", e)

                self.send_json(
                    500,
                    {
                        "error":
                        "Database error."
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


            if email_id.isdigit():

                try:

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

                except Exception as e:

                    print("Delete error:", e)

                    self.send_json(
                        500,
                        {
                            "error":
                            "Delete failed."
                        }
                    )

                return


        # ====================================================
        # ⭐ 星标
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


            if email_id.isdigit():

                try:

                    star_email(
                        int(email_id)
                    )

                    self.send_json(
                        200,
                        {
                            "message":
                            "Email locked."
                        }
                    )

                except Exception as e:

                    print("Star error:", e)

                    self.send_json(
                        500,
                        {
                            "error":
                            "Star failed."
                        }
                    )

                return


        # ====================================================
        # 取消 ⭐
        # ====================================================

        if path.startswith("/admin/unstar/"):

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

                try:

                    unstar_email(
                        int(email_id)
                    )

                    self.send_json(
                        200,
                        {
                            "message":
                            "Unlocked."
                        }
                    )

                except Exception as e:

                    print("Unstar error:", e)

                    self.send_json(
                        500,
                        {
                            "error":
                            "Unstar failed."
                        }
                    )

                return


        # ====================================================
        # 后台数据 API
        # ====================================================

        if path == "/admin/refresh":

            if not self.is_logged_in():

                self.send_json(
                    401,
                    {
                        "error":
                        "Unauthorized."
                    }
                )

                return


            try:

                subscribers = get_emails()

                self.send_json(
                    200,
                    {
                        "data":
                        subscribers
                    }
                )

            except Exception as e:

                print("Refresh error:", e)

                self.send_json(
                    500,
                    {
                        "error":
                        "Database error."
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
    # Login
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
    # Admin Dashboard
    # --------------------------------------------------------

    def admin_page(self):

        subscribers = get_emails()

        rows = ""


        for item in subscribers:

            email_id = item["id"]
            email = item["email"]
            created_at = item["created_at"]
            starred = item.get("starred", False)


            if starred:

                star_button = f"""
                <button
                    onclick="unstarEmail({email_id})">
                    ⭐
                </button>
                """

                status = "⭐ Locked"

            else:

                star_button = f"""
                <button
                    onclick="starEmail({email_id})">
                    ☆
                </button>
                """

                status = "Active"


            rows += f"""
            <tr>

                <td>
                    {email_id}
                </td>

                <td>
                    {html.escape(str(email))}
                </td>

                <td>
                    {html.escape(str(created_at))}
                </td>

                <td>
                    {status}
                </td>

                <td>

                    {star_button}

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

    margin-right: 5px;
}}

.locked {{
    font-weight: bold;
}}

</style>

</head>

<body>

<div class="header">

<h1>Registration Dashboard</h1>

<div class="actions">

<button
    class="refresh"
    onclick="refreshPage()">
    🔄 Refresh
</button>

<a
    class="logout"
    href="/admin/logout">
    Logout
</a>

</div>

</div>


<p>
Total registrations:
<strong id="total">
{len(subscribers)}
</strong>
</p>


<table>

<thead>

<tr>

<th>ID</th>

<th>Email</th>

<th>Time</th>

<th>Status</th>

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

        location.href =
            "/admin/login";
    }}

}}


async function starEmail(id) {{

    const response = await fetch(
        "/admin/star/" + id,
        {{
            method: "POST"
        }}
    );


    if (response.ok) {{

        location.reload();

    }} else {{

        alert("Operation failed.");
    }}

}}


async function unstarEmail(id) {{

    if (!confirm(
        "Unlock this email so it can be registered again?"
    )) {{
        return;
    }}


    const response = await fetch(
        "/admin/unstar/" + id,
        {{
            method: "POST"
        }}
    );


    if (response.ok) {{

        location.reload();

    }} else {{

        alert("Operation failed.");
    }}

}}


async function refreshPage() {{

    const button =
        document.querySelector(".refresh");

    button.disabled = true;

    button.textContent =
        "⏳ Refreshing...";


    try {{

        const response =
            await fetch(
                "/admin/refresh",
                {{
                    method: "POST"
                }}
            );


        if (response.ok) {{

            location.reload();

        }} else {{

            alert(
                "Session expired. Please login again."
            );

            location.href =
                "/admin/login";
        }}

    }} catch (error) {{

        alert(
            "Unable to refresh."
        );

        button.disabled = false;

        button.textContent =
            "🔄 Refresh";
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
