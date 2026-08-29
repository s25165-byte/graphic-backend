import html
import json
import secrets
import sqlite3
import time
import os

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


# ============================================================
# 基本设置
# ============================================================

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "subscribers.db"

ADMIN_USERNAME = "admin"

# !!! 建议你修改成自己的强密码 !!!
ADMIN_PASSWORD = "12345678"

# Session 有效时间：30天
SESSION_DURATION = 30 * 24 * 60 * 60


# ============================================================
# 数据库
# ============================================================

def init_database():

    with sqlite3.connect(DATABASE) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                starred INTEGER NOT NULL DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                created_at INTEGER NOT NULL
            )
        """)

        conn.commit()


# ============================================================
# Gmail
# ============================================================

def normalize_email(email):

    return email.strip().lower()


def email_exists(email):

    with sqlite3.connect(DATABASE) as conn:

        result = conn.execute(
            """
            SELECT id, starred
            FROM subscribers
            WHERE email = ?
            COLLATE NOCASE
            """,
            (email,)
        ).fetchone()

        return result


def add_email(email):

    email = normalize_email(email)

    with sqlite3.connect(DATABASE) as conn:

        try:

            conn.execute(
                """
                INSERT INTO subscribers
                (email)
                VALUES (?)
                """,
                (email,)
            )

            conn.commit()

            return True

        except sqlite3.IntegrityError:

            return False


def get_emails():

    with sqlite3.connect(DATABASE) as conn:

        return conn.execute(
            """
            SELECT
                id,
                email,
                created_at,
                starred
            FROM subscribers
            ORDER BY
                starred DESC,
                id DESC
            """
        ).fetchall()


def delete_email(email_id):

    with sqlite3.connect(DATABASE) as conn:

        conn.execute(
            """
            DELETE FROM subscribers
            WHERE id = ?
            """,
            (email_id,)
        )

        conn.commit()


def toggle_star(email_id):

    with sqlite3.connect(DATABASE) as conn:

        row = conn.execute(
            """
            SELECT starred
            FROM subscribers
            WHERE id = ?
            """,
            (email_id,)
        ).fetchone()

        if row is None:
            return False

        new_value = 0 if row[0] else 1

        conn.execute(
            """
            UPDATE subscribers
            SET starred = ?
            WHERE id = ?
            """,
            (new_value, email_id)
        )

        conn.commit()

        return True


# ============================================================
# Session
# ============================================================

def create_session():

    token = secrets.token_urlsafe(32)

    now = int(time.time())

    with sqlite3.connect(DATABASE) as conn:

        conn.execute(
            """
            INSERT INTO sessions
            (token, created_at)
            VALUES (?, ?)
            """,
            (token, now)
        )

        conn.commit()

    return token


def delete_session(token):

    if not token:
        return

    with sqlite3.connect(DATABASE) as conn:

        conn.execute(
            """
            DELETE FROM sessions
            WHERE token = ?
            """,
            (token,)
        )

        conn.commit()


def session_valid(token):

    if not token:
        return False

    now = int(time.time())

    with sqlite3.connect(DATABASE) as conn:

        row = conn.execute(
            """
            SELECT created_at
            FROM sessions
            WHERE token = ?
            """,
            (token,)
        ).fetchone()

        if row is None:
            return False

        created_at = row[0]

        if now - created_at > SESSION_DURATION:

            conn.execute(
                """
                DELETE FROM sessions
                WHERE token = ?
                """,
                (token,)
            )

            conn.commit()

            return False

        return True


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

        self.send_header(
            "Cache-Control",
            "no-store"
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

        return session_valid(
            self.get_session()
        )


    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    def do_GET(self):

        path = urlparse(
            self.path
        ).path


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

        if path == "/style.css":

            self.serve_file(
                ROOT / "style.css",
                "text/css; charset=utf-8"
            )

            return


        # ====================================================
        # JavaScript
        # ====================================================

        if path == "/main.js":

            self.serve_file(
                ROOT / "main.js",
                "application/javascript; charset=utf-8"
            )

            return


        # ====================================================
        # CSS 文件夹
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
        # JS 文件夹
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

            if self.is_logged_in():

                self.redirect("/admin")

                return

            self.login_page()

            return


        # ====================================================
        # 管理后台
        # ====================================================

        if path == "/admin":

            if not self.is_logged_in():

                self.redirect("/admin/login")

                return

            self.admin_page()

            return


        # ====================================================
        # 后台数据
        # ====================================================

        if path == "/admin/data":

            if not self.is_logged_in():

                self.send_json(
                    401,
                    {
                        "error": "Unauthorized."
                    }
                )

                return

            self.send_admin_data()

            return


        # ====================================================
        # 登出
        # ====================================================

        if path == "/admin/logout":

            session = self.get_session()

            delete_session(session)

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

                session = create_session()

                self.send_response(302)

                self.send_header(
                    "Location",
                    "/admin"
                )

                self.send_header(
                    "Set-Cookie",
                    (
                        f"session={session}; "
                        f"Max-Age={SESSION_DURATION}; "
                        f"Path=/; "
                        f"HttpOnly; "
                        f"SameSite=Strict"
                    )
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

                    email = normalize_email(
                        str(
                            data.get(
                                "email",
                                ""
                            )
                        )
                    )

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

                email = normalize_email(
                    data.get(
                        "email",
                        [""]
                    )[0]
                )


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
            # 检查是否已经存在
            # =================================================

            existing = email_exists(email)

            if existing:

                email_id = existing[0]
                starred = existing[1]

                if starred:

                    self.send_json(
                        409,
                        {
                            "error":
                            "This Gmail address has already been marked and cannot be registered again."
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


            # =================================================
            # 保存
            # =================================================

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


        # ====================================================
        # 星号
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


            success = toggle_star(
                int(email_id)
            )

            if success:

                self.send_json(
                    200,
                    {
                        "message":
                        "Star updated."
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
    # 后台数据 API
    # --------------------------------------------------------

    def send_admin_data(self):

        subscribers = get_emails()

        data = []

        for email_id, email, created_at, starred in subscribers:

            data.append(
                {
                    "id": email_id,
                    "email": email,
                    "created_at": str(created_at),
                    "starred": bool(starred)
                }
            )


        starred_count = sum(
            1
            for item in data
            if item["starred"]
        )


        self.send_json(
            200,
            {
                "total": len(data),
                "starred": starred_count,
                "subscribers": data
            }
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

        self.send_header(
            "Cache-Control",
            "no-cache"
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

    def login_page(
        self,
        error=""
    ):

        error_html = ""

        if error:

            error_html = f"""
            <p style="
                color:#b3261e;
                margin-bottom:15px;
            ">
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

* {{
    box-sizing: border-box;
}}

body {{

    margin: 0;

    font-family: Arial, sans-serif;

    background: #f5f5f5;

    min-height: 100vh;

    display: flex;

    justify-content: center;

    align-items: center;

    padding: 20px;
}}

.login-box {{

    background: white;

    width: 100%;

    max-width: 360px;

    padding: 30px;

    border-radius: 16px;

    box-shadow:
        0 5px 30px rgba(0,0,0,0.10);
}}

h1 {{

    margin-top: 0;

    margin-bottom: 25px;
}}

label {{

    display: block;

    margin-bottom: 5px;

    font-weight: 500;
}}

input {{

    width: 100%;

    padding: 12px;

    margin-bottom: 18px;

    border: 1px solid #ccc;

    border-radius: 8px;

    font-size: 16px;
}}

button {{

    width: 100%;

    padding: 12px;

    border: none;

    border-radius: 8px;

    background: #171716;

    color: white;

    cursor: pointer;

    font-size: 16px;
}}

button:hover {{

    opacity: .9;
}}

</style>

</head>

<body>

<div class="login-box">

<h1>Admin Login</h1>

{error_html}

<form method="POST"
      action="/admin/login">

<label>
    Username
</label>

<input
    type="text"
    name="username"
    autocomplete="username"
    required
>

<label>
    Password
</label>

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


        body = page.encode(
            "utf-8"
        )

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

        page = """
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Registration Dashboard</title>

<style>

* {
    box-sizing: border-box;
}

body {

    font-family: Arial, sans-serif;

    margin: 0;

    background: #f5f5f5;

    padding: 20px;
}

.container {

    max-width: 1100px;

    margin: auto;
}

.header {

    display: flex;

    justify-content: space-between;

    align-items: center;

    gap: 15px;

    margin-bottom: 20px;
}

.header h1 {

    margin: 0;
}

.header-actions {

    display: flex;

    gap: 8px;

    flex-wrap: wrap;
}

.header-actions button,
.logout {

    padding: 9px 14px;

    border: 1px solid #ccc;

    border-radius: 8px;

    background: white;

    cursor: pointer;

    text-decoration: none;

    color: black;
}

.stats {

    display: flex;

    gap: 12px;

    margin-bottom: 20px;

    flex-wrap: wrap;
}

.stat {

    background: white;

    border-radius: 12px;

    padding: 16px 20px;

    min-width: 150px;

    box-shadow:
        0 2px 10px rgba(0,0,0,0.05);
}

.stat-number {

    font-size: 28px;

    font-weight: bold;
}

.stat-label {

    color: #777;

    margin-top: 4px;
}

.table-box {

    background: white;

    border-radius: 12px;

    overflow: hidden;

    box-shadow:
        0 2px 10px rgba(0,0,0,0.05);
}

table {

    width: 100%;

    border-collapse: collapse;
}

th,
td {

    padding: 13px;

    border-bottom: 1px solid #eee;

    text-align: left;
}

th {

    background: #fafafa;
}

.star {

    border: none;

    background: none;

    font-size: 24px;

    cursor: pointer;

    padding: 0;

    line-height: 1;
}

.star.active {

    filter: none;
}

.actions {

    display: flex;

    gap: 8px;

    flex-wrap: wrap;
}

.delete {

    border: none;

    background: #eee;

    padding: 7px 12px;

    border-radius: 7px;

    cursor: pointer;
}

.loading {

    text-align: center;

    padding: 30px;

    color: #777;
}

.empty {

    text-align: center;

    padding: 40px;

    color: #777;
}

.refreshing {

    opacity: .6;

    pointer-events: none;
}


/* ==========================================
   手机
   ========================================== */

@media (max-width: 700px) {

    body {
        padding: 12px;
    }

    .header {

        align-items: flex-start;

        flex-direction: column;
    }

    .header-actions {

        width: 100%;
    }

    .header-actions button,
    .logout {

        flex: 1;

        text-align: center;
    }

    .table-box {

        overflow-x: auto;
    }

    table {

        min-width: 650px;
    }

}

</style>

</head>

<body>

<div class="container">

<div class="header">

<h1>
    Registration Dashboard
</h1>

<div class="header-actions">

<button
    id="refreshButton"
    onclick="refreshData()">
    🔄 Refresh
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

<div
    class="stat-number"
    id="totalCount">
    0
</div>

<div class="stat-label">
    Total registrations
</div>

</div>


<div class="stat">

<div
    class="stat-number"
    id="starredCount">
    0
</div>

<div class="stat-label">
    ⭐ Starred
</div>

</div>

</div>


<div class="table-box">

<table>

<thead>

<tr>

<th>
    ⭐
</th>

<th>
    ID
</th>

<th>
    Email
</th>

<th>
    Time
</th>

<th>
    Action
</th>

</tr>

</thead>

<tbody
    id="subscriberTable">

<tr>

<td
    colspan="5"
    class="loading">

Loading...

</td>

</tr>

</tbody>

</table>

</div>

</div>


<script>


// ==========================================================
// 加载数据
// ==========================================================

async function refreshData() {

    const button =
        document.getElementById(
            "refreshButton"
        );

    button.classList.add(
        "refreshing"
    );

    button.textContent =
        "⏳ Refreshing...";


    try {

        const response =
            await fetch(
                "/admin/data",
                {
                    cache: "no-store"
                }
            );


        if (response.status === 401) {

            location.href =
                "/admin/login";

            return;
        }


        if (!response.ok) {

            throw new Error(
                "Failed to load data."
            );
        }


        const data =
            await response.json();


        renderSubscribers(
            data
        );


    } catch (error) {

        alert(
            "Unable to refresh data."
        );

    } finally {

        button.classList.remove(
            "refreshing"
        );

        button.textContent =
            "🔄 Refresh";
    }
}


// ==========================================================
// 显示数据
// ==========================================================

function renderSubscribers(data) {

    document.getElementById(
        "totalCount"
    ).textContent =
        data.total;


    document.getElementById(
        "starredCount"
    ).textContent =
        data.starred;


    const table =
        document.getElementById(
            "subscriberTable"
        );


    if (
        !data.subscribers ||
        data.subscribers.length === 0
    ) {

        table.innerHTML = `

        <tr>

            <td
                colspan="5"
                class="empty">

                No registrations yet.

            </td>

        </tr>

        `;

        return;
    }


    table.innerHTML =
        data.subscribers.map(
            item => `

            <tr>

                <td>

                    <button
                        class="star ${
                            item.starred
                            ? "active"
                            : ""
                        }"
                        onclick="toggleStar(${item.id})"
                        title="${
                            item.starred
                            ? "Unstar"
                            : "Star"
                        }">

                        ${
                            item.starred
                            ? "★"
                            : "☆"
                        }

                    </button>

                </td>


                <td>
                    ${item.id}
                </td>


                <td>
                    ${escapeHtml(item.email)}
                </td>


                <td>
                    ${escapeHtml(item.created_at)}
                </td>


                <td>

                    <div class="actions">

                        <button
                            class="delete"
                            onclick="deleteEmail(${item.id})">

                            🗑️ Delete

                        </button>

                    </div>

                </td>

            </tr>

            `
        ).join("");
}


// ==========================================================
// 星号
// ==========================================================

async function toggleStar(id) {

    try {

        const response =
            await fetch(
                "/admin/star/" + id,
                {
                    method: "POST"
                }
            );


        if (response.status === 401) {

            location.href =
                "/admin/login";

            return;
        }


        if (!response.ok) {

            alert(
                "Unable to update star."
            );

            return;
        }


        await refreshData();

    } catch (error) {

        alert(
            "Network error."
        );
    }
}


// ==========================================================
// 删除
// ==========================================================

async function deleteEmail(id) {

    if (
        !confirm(
            "Delete this email?"
        )
    ) {

        return;
    }


    try {

        const response =
            await fetch(
                "/admin/delete/" + id,
                {
                    method: "POST"
                }
            );


        if (response.status === 401) {

            location.href =
                "/admin/login";

            return;
        }


        if (!response.ok) {

            alert(
                "Unable to delete."
            );

            return;
        }


        await refreshData();

    } catch (error) {

        alert(
            "Network error."
        );
    }
}


// ==========================================================
// 防止 HTML 注入
// ==========================================================

function escapeHtml(value) {

    return String(value)

        .replaceAll("&", "&amp;")

        .replaceAll("<", "&lt;")

        .replaceAll(">", "&gt;")

        .replaceAll('"', "&quot;")

        .replaceAll("'", "&#039;");
}


// ==========================================================
// 第一次进入后台自动加载
// ==========================================================

refreshData();

</script>

</body>

</html>
"""


        body = page.encode(
            "utf-8"
        )

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.send_header(
            "Cache-Control",
            "no-store"
        )

        self.end_headers()

        self.wfile.write(body)


# ============================================================
# 启动服务器
# ============================================================

if __name__ == "__main__":

    init_database()

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


    print(
        "================================"
    )

    print(
        "Website:"
    )

    print(
        "http://localhost:8000"
    )

    print()

    print(
        "Admin:"
    )

    print(
        "http://localhost:8000/admin"
    )

    print()

    print(
        "Username:"
    )

    print(
        ADMIN_USERNAME
    )

    print(
        "================================"
    )


    server.serve_forever()
