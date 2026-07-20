"""
Office Notify - Server v3.0 (Final)
- Login authentication (superadmin + managers)
- Employee count live tracking
- Manager add / disable / delete
- Broadcast with full formatting
"""

import asyncio, json, websockets, hashlib, os

HOST       = "0.0.0.0"
PORT       = 8765
USERS_FILE = "users.json"

# ==================== USERS ====================
def hp(p): return hashlib.sha256(p.encode()).hexdigest()

def load_users():
    if not os.path.exists(USERS_FILE):
        save_users({"admin": {"password": hp("admin123"), "role": "superadmin", "enabled": True}})
        print("[!] Default: admin / admin123")
    with open(USERS_FILE) as f: return json.load(f)

def save_users(u):
    with open(USERS_FILE, "w") as f: json.dump(u, f, indent=2)

# ==================== STATE ====================
employees      = set()
admin_sessions = {}   # ws -> {username, role}

async def notify_admins_count():
    msg = json.dumps({"type": "employee_count", "count": len(employees)})
    dead = set()
    for ws in list(admin_sessions):
        try: await ws.send(msg)
        except: dead.add(ws)
    for ws in dead:
        admin_sessions.pop(ws, None)

# ==================== HANDLER ====================
async def handler(ws):
    try:
        async for raw in ws:
            d    = json.loads(raw)
            kind = d.get("type")

            # Employee connect
            if kind == "employee_connect":
                employees.add(ws)
                print(f"[+] Employee: {d.get('name','?')} | Total: {len(employees)}")
                await notify_admins_count()

            # Login
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

            # Broadcast
            elif kind == "broadcast" and ws in admin_sessions:
                payload = {
                    "type":        "broadcast",
                    "text":        d.get("text",""),
                    "color":       d.get("color","yellow"),
                    "size":        d.get("size", 22),
                    "opacity":     d.get("opacity", 1.0),
                    "font_family": d.get("font_family","Segoe UI"),
                    "bold":        d.get("bold", False),
                    "italic":      d.get("italic", False),
                    "effect":      d.get("effect","none"),
                    "pos":         d.get("pos","current"),
                }
                dead = set()
                for emp in employees:
                    try: await emp.send(json.dumps(payload))
                    except: dead.add(emp)
                employees.difference_update(dead)
                sender = admin_sessions[ws]["username"]
                await ws.send(json.dumps({
                    "type": "broadcast_sent",
                    "text": d.get("text",""),
                    "username": sender
                }))
                if dead: await notify_admins_count()
                print(f"[Broadcast] '{d.get('text','')}' -> {len(employees)} employees")

            # Get managers
            elif kind == "get_managers" and ws in admin_sessions:
                if admin_sessions[ws]["role"] == "superadmin":
                    users = load_users()
                    mgrs  = {k: {"enabled": v["enabled"]} for k,v in users.items() if v["role"]=="manager"}
                    await ws.send(json.dumps({"type":"managers_list","managers":mgrs}))

            # Add manager
            elif kind == "add_manager" and ws in admin_sessions:
                if admin_sessions[ws]["role"] == "superadmin":
                    users = load_users()
                    u2, p2 = d.get("username","").strip(), d.get("password","")
                    if u2 and p2 and u2 not in users:
                        users[u2] = {"password": hp(p2), "role":"manager","enabled":True}
                        save_users(users)
                        await ws.send(json.dumps({"type":"manager_added","username":u2}))
                        print(f"[+] Manager added: {u2}")
                    else:
                        await ws.send(json.dumps({"type":"error","message":"Username already exists!"}))

            # Toggle manager
            elif kind == "toggle_manager" and ws in admin_sessions:
                if admin_sessions[ws]["role"] == "superadmin":
                    users = load_users()
                    u2    = d.get("username","")
                    if u2 in users and users[u2]["role"] == "manager":
                        users[u2]["enabled"] = not users[u2]["enabled"]
                        save_users(users)
                        await ws.send(json.dumps({"type":"manager_updated","username":u2,"enabled":users[u2]["enabled"]}))

            # Delete manager
            elif kind == "delete_manager" and ws in admin_sessions:
                if admin_sessions[ws]["role"] == "superadmin":
                    users = load_users()
                    u2    = d.get("username","")
                    if u2 in users and users[u2]["role"] == "manager":
                        del users[u2]
                        save_users(users)
                        await ws.send(json.dumps({"type":"manager_deleted","username":u2}))

            # Logout
            elif kind == "logout":
                admin_sessions.pop(ws, None)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        was_employee = ws in employees
        employees.discard(ws)
        admin_sessions.pop(ws, None)
        if was_employee:
            print(f"[-] Employee disconnected | Total: {len(employees)}")
            await notify_admins_count()

# ==================== MAIN ====================
async def main():
    print("="*50)
    print("  Office Notify Server v3.0")
    print(f"  ws://{HOST}:{PORT}")
    print("  Default: admin / admin123")
    print("="*50)
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
