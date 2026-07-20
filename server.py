"""
Office Notify - Server v4.0 FINAL
- Login (superadmin + managers)
- Employee count tracking
- Manager add/disable/delete
- Broadcast with pos field
- Real-time collaboration (all admins see each others messages)
"""
import asyncio, json, websockets, hashlib, os

HOST       = "0.0.0.0"
PORT       = 8765
USERS_FILE = "users.json"

def hp(p): return hashlib.sha256(p.encode()).hexdigest()

def load_users():
    if not os.path.exists(USERS_FILE):
        save_users({"admin": {"password": hp("admin123"), "role": "superadmin", "enabled": True}})
        print("[!] Default: admin / admin123")
    with open(USERS_FILE) as f: return json.load(f)

def save_users(u):
    with open(USERS_FILE, "w") as f: json.dump(u, f, indent=2)

employees      = set()
admin_sessions = {}

async def notify_count():
    msg = json.dumps({"type": "employee_count", "count": len(employees)})
    dead = set()
    for ws in list(admin_sessions):
        try: await ws.send(msg)
        except: dead.add(ws)
    for ws in dead: admin_sessions.pop(ws, None)

async def handler(ws):
    try:
        async for raw in ws:
            d    = json.loads(raw)
            kind = d.get("type")

            if kind == "employee_connect":
                employees.add(ws)
                print(f"[+] Employee: {d.get('name','?')} | Total: {len(employees)}")
                await notify_count()

            elif kind == "login":
                users = load_users()
                u, p  = d.get("username",""), hp(d.get("password",""))
                if u in users and users[u]["password"]==p and users[u]["enabled"]:
                    admin_sessions[ws] = {"username": u, "role": users[u]["role"]}
                    await ws.send(json.dumps({
                        "type": "login_success",
                        "role": users[u]["role"],
                        "username": u,
                        "employee_count": len(employees)
                    }))
                    print(f"[+] Login: {u} ({users[u]['role']})")
                else:
                    await ws.send(json.dumps({"type": "login_failed"}))

            elif kind == "broadcast" and ws in admin_sessions:
                payload = {
                    "type":        "broadcast",
                    "text":        d.get("text", ""),
                    "color":       d.get("color", "#ffffff"),
                    "size":        d.get("size", 22),
                    "opacity":     d.get("opacity", 1.0),
                    "font_family": d.get("font_family", "Segoe UI"),
                    "bold":        d.get("bold", False),
                    "italic":      d.get("italic", False),
                    "effect":      d.get("effect", "none"),
                    "pos":         d.get("pos", "current"),
                }
                # Send to all employees
                dead = set()
                for emp in employees:
                    try: await emp.send(json.dumps(payload))
                    except: dead.add(emp)
                employees.difference_update(dead)
                if dead: await notify_count()

                sender = admin_sessions[ws]["username"]
                text   = d.get("text", "")

                # Notify ALL admins (collaboration feature)
                for adm_ws in list(admin_sessions.keys()):
                    try:
                        await adm_ws.send(json.dumps({
                            "type":    "broadcast_sent",
                            "text":    text,
                            "username": sender,
                            "is_mine": adm_ws == ws
                        }))
                    except: pass

                print(f"[Broadcast] '{text}' by {sender} -> {len(employees)} employees")

            elif kind == "get_managers" and ws in admin_sessions:
                if admin_sessions[ws]["role"] == "superadmin":
                    users = load_users()
                    mgrs  = {k: {"enabled": v["enabled"]} for k,v in users.items() if v["role"]=="manager"}
                    await ws.send(json.dumps({"type": "managers_list", "managers": mgrs}))

            elif kind == "add_manager" and ws in admin_sessions:
                if admin_sessions[ws]["role"] == "superadmin":
                    users  = load_users()
                    u2, p2 = d.get("username","").strip(), d.get("password","")
                    if u2 and p2 and u2 not in users:
                        users[u2] = {"password": hp(p2), "role": "manager", "enabled": True}
                        save_users(users)
                        await ws.send(json.dumps({"type": "manager_added", "username": u2}))
                        print(f"[+] Manager added: {u2}")
                    else:
                        await ws.send(json.dumps({"type": "error", "message": "Username already exists!"}))

            elif kind == "toggle_manager" and ws in admin_sessions:
                if admin_sessions[ws]["role"] == "superadmin":
                    users = load_users()
                    u2    = d.get("username","")
                    if u2 in users and users[u2]["role"] == "manager":
                        users[u2]["enabled"] = not users[u2]["enabled"]
                        save_users(users)
                        await ws.send(json.dumps({
                            "type": "manager_updated",
                            "username": u2,
                            "enabled": users[u2]["enabled"]
                        }))

            elif kind == "delete_manager" and ws in admin_sessions:
                if admin_sessions[ws]["role"] == "superadmin":
                    users = load_users()
                    u2    = d.get("username","")
                    if u2 in users and users[u2]["role"] == "manager":
                        del users[u2]
                        save_users(users)
                        await ws.send(json.dumps({"type": "manager_deleted", "username": u2}))

            elif kind == "logout":
                admin_sessions.pop(ws, None)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        was_emp = ws in employees
        employees.discard(ws)
        admin_sessions.pop(ws, None)
        if was_emp:
            print(f"[-] Employee disconnected | Total: {len(employees)}")
            await notify_count()

async def main():
    print("="*50)
    print("  Office Notify Server v4.0 FINAL")
    print(f"  ws://{HOST}:{PORT}")
    print("  Default: admin / admin123")
    print("="*50)
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
