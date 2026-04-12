import datetime
import sqlite3
import time
from functools import wraps

from flask import abort, flash, redirect, render_template, request, session, url_for
from zenora import APIClient

from app import app
from config import Config
import sqlite_helper
import user

ADMIN_CHECK_TTL = 300  # re-verify admin status every 5 minutes


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "token" not in session:
            return redirect(Config.OAUTH_URL)
        allow = Config.admin_discord_ids()
        if not allow:
            abort(404)

        cached_at = session.get("_admin_verified_at", 0)
        if session.get("_is_admin") and (time.time() - cached_at) < ADMIN_CHECK_TTL:
            return view(*args, **kwargs)

        client = APIClient(session["token"], bearer=True)
        cu = client.users.get_current_user()
        if cu.id not in allow:
            session.pop("_is_admin", None)
            abort(404)

        session["_is_admin"] = True
        session["_admin_verified_at"] = time.time()
        return view(*args, **kwargs)

    return wrapped


def _parse_schedule_dt(value):
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    if len(s) == 16 and "T" in s:
        s = s + ":00"
    dt = datetime.datetime.fromisoformat(s)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _banner_status(row, db_now):
    if not row["active"]:
        return "Inactive"
    if row["starts_at"] and row["starts_at"] > db_now:
        return "Scheduled"
    if row["ends_at"] and row["ends_at"] <= db_now:
        return "Ended"
    return "Live"


def _name_taken(cur, name, exclude_banner_id=None):
    if exclude_banner_id is None:
        return cur.execute(
            "SELECT 1 FROM banners WHERE name = ?", (name,)
        ).fetchone()
    return cur.execute(
        "SELECT 1 FROM banners WHERE name = ? AND id != ?",
        (name, exclude_banner_id),
    ).fetchone()


def _validate_banner_form(cur, name, unit_ids, pity_ids, starts_at, ends_at):
    if not name or not name.strip():
        return "Name is required."
    if starts_at and ends_at and ends_at <= starts_at:
        return "End time must be after start time."
    if len(unit_ids) < 1:
        return "Select at least one unit."
    if len(pity_ids) < 2:
        return "Link exactly two pity rules (SR + SSR), matching the live shrine layout."
    pities = cur.execute(
        f"SELECT id, rarity, rateup_exists FROM pity WHERE id IN ({','.join('?' * len(pity_ids))})",
        tuple(pity_ids),
    ).fetchall()
    if len(pities) != len(set(pity_ids)):
        return "Invalid pity selection."
    pool = cur.execute(
        f"""SELECT id, rarity FROM units WHERE id IN ({','.join('?' * len(unit_ids))})""",
        tuple(unit_ids),
    ).fetchall()
    if len(pool) != len(set(unit_ids)):
        return "Invalid unit selection."
    rarity_set = {u["rarity"] for u in pool}
    for p in pities:
        if p["rarity"] not in rarity_set:
            return f"Pity {p['id']} ({p['rarity']}) requires at least one unit of that rarity in the pool."
    return None


def _validate_rateup_pool(cur, unit_rateup_pairs, pity_ids):
    pities = cur.execute(
        f"SELECT id, rarity, rateup_exists FROM pity WHERE id IN ({','.join('?' * len(pity_ids))})",
        tuple(pity_ids),
    ).fetchall()
    id_to_rarity = {
        r["id"]: r["rarity"]
        for r in cur.execute(
            f"SELECT id, rarity FROM units WHERE id IN ({','.join('?' * len(unit_rateup_pairs))})",
            tuple(uid for uid, _ in unit_rateup_pairs),
        ).fetchall()
    }
    for p in pities:
        if p["rateup_exists"] is None:
            continue
        rar = p["rarity"]
        if not any(
            id_to_rarity.get(uid) == rar and ru for uid, ru in unit_rateup_pairs
        ):
            return (
                f"Pity id {p['id']} ({rar}) expects at least one rate-up unit "
                f"of that rarity in the pool."
            )
    return None


def _parse_banner_form():
    name = (request.form.get("name") or "").strip()
    active = request.form.get("active") == "on"
    permanent = request.form.get("permanent") == "on"
    sort_order = int(request.form.get("sort_order") or 0)
    currency_id = int(request.form.get("currency_id") or 1)
    if permanent:
        starts_at = None
        ends_at = None
    else:
        starts_at = _parse_schedule_dt(request.form.get("starts_at"))
        ends_at = _parse_schedule_dt(request.form.get("ends_at"))
    unit_ids = list(
        dict.fromkeys(int(x) for x in request.form.getlist("unit_id") if x.isdigit())
    )
    rateup_unit_ids = {int(x) for x in request.form.getlist("rateup_unit_id") if x.isdigit()}
    copy_from = request.form.get("copy_pity_from")
    pity_ids = list(
        dict.fromkeys(int(x) for x in request.form.getlist("pity_id") if x.isdigit())
    )
    return {
        "name": name,
        "active": active,
        "sort_order": sort_order,
        "currency_id": currency_id,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "unit_ids": unit_ids,
        "rateup_unit_ids": rateup_unit_ids,
        "copy_pity_from": int(copy_from) if copy_from and copy_from.isdigit() else None,
        "pity_ids": pity_ids,
    }


@app.route("/admin")
@admin_required
def admin_dashboard():
    current_user, currencies = user.load_user()
    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        counts = sqlite_helper.get_admin_counts(cur)
    return render_template(
        "admin/dashboard.html",
        current_user=current_user,
        currencies=currencies,
        counts=counts,
    )


@app.route("/admin/banners", methods=["GET"])
@admin_required
def admin_banners_list():
    current_user, currencies = user.load_user()
    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        db_now = cur.execute("SELECT datetime('now') AS now").fetchone()["now"]
        rows = sqlite_helper.get_all_banners_admin(cur)
    for r in rows:
        r["status"] = _banner_status(r, db_now)
    return render_template(
        "admin/banners.html",
        current_user=current_user,
        currencies=currencies,
        banners=rows,
        db_now=db_now,
    )


@app.route("/admin/banners/new", methods=["GET", "POST"])
@admin_required
def admin_banner_new():
    current_user, currencies = user.load_user()
    if request.method == "GET":
        with sqlite3.connect(Config.DATABASE_URI) as con:
            con.row_factory = sqlite_helper.dict_factory
            cur = con.cursor()
            units = sqlite_helper.get_units_for_admin(cur)
            pities = sqlite_helper.get_pity_rows(cur)
            currencies_rows = sqlite_helper.get_currency_rows(cur)
            existing = sqlite_helper.get_all_banners_admin(cur)
        return render_template(
            "admin/banner_form.html",
            current_user=current_user,
            currencies=currencies,
            units=units,
            pities=pities,
            currencies_rows=currencies_rows,
            existing_banners=existing,
            banner=None,
            selected_units={},
            selected_pity=set(),
        )

    data = _parse_banner_form()
    unit_rateup = [(uid, uid in data["rateup_unit_ids"]) for uid in data["unit_ids"]]

    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        pity_ids = list(data["pity_ids"])
        if data["copy_pity_from"]:
            src = cur.execute(
                "SELECT pity_id FROM banner_pity WHERE banner_id = ? ORDER BY pity_id",
                (data["copy_pity_from"],),
            ).fetchall()
            if src:
                pity_ids = [r["pity_id"] for r in src]
        err = _validate_banner_form(
            cur,
            data["name"],
            data["unit_ids"],
            pity_ids,
            data["starts_at"],
            data["ends_at"],
        )
        if not err and _name_taken(cur, data["name"]):
            err = "A banner with that name already exists."
        if not err:
            err = _validate_rateup_pool(cur, unit_rateup, pity_ids)
        if err:
            flash(err, "error")
            units = sqlite_helper.get_units_for_admin(cur)
            pities = sqlite_helper.get_pity_rows(cur)
            currencies_rows = sqlite_helper.get_currency_rows(cur)
            existing = sqlite_helper.get_all_banners_admin(cur)
            selected_units = {uid: (uid in data["rateup_unit_ids"]) for uid in data["unit_ids"]}
            return render_template(
                "admin/banner_form.html",
                current_user=current_user,
                currencies=currencies,
                units=units,
                pities=pities,
                currencies_rows=currencies_rows,
                existing_banners=existing,
                banner={
                    "name": data["name"],
                    "active": data["active"],
                    "sort_order": data["sort_order"],
                    "currency_id": data["currency_id"],
                    "starts_at": request.form.get("starts_at"),
                    "ends_at": request.form.get("ends_at"),
                },
                selected_units=selected_units,
                selected_pity=set(pity_ids),
            )

        bid = sqlite_helper.insert_banner(
            cur,
            data["name"],
            data["active"],
            data["starts_at"],
            data["ends_at"],
            data["sort_order"],
            data["currency_id"],
        )
        sqlite_helper.replace_banner_units(cur, bid, unit_rateup)
        sqlite_helper.replace_banner_pity(cur, bid, pity_ids)
        con.commit()
    flash("Banner created.", "success")
    return redirect(url_for("admin_banners_list"))


@app.route("/admin/banners/<int:banner_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_banner_edit(banner_id):
    current_user, currencies = user.load_user()
    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        detail = sqlite_helper.get_banner_admin_detail(cur, banner_id)
        if not detail:
            abort(404)

        if request.method == "GET":
            units = sqlite_helper.get_units_for_admin(cur)
            pities = sqlite_helper.get_pity_rows(cur)
            currencies_rows = sqlite_helper.get_currency_rows(cur)
            existing = sqlite_helper.get_all_banners_admin(cur)
            selected_units = {
                u["unit_id"]: bool(u["rateup"]) for u in detail["units"]
            }
            return render_template(
                "admin/banner_form.html",
                current_user=current_user,
                currencies=currencies,
                units=units,
                pities=pities,
                currencies_rows=currencies_rows,
                existing_banners=existing,
                banner=detail["banner"],
                selected_units=selected_units,
                selected_pity=set(detail["pity_ids"]),
            )

        data = _parse_banner_form()
        unit_rateup = [(uid, uid in data["rateup_unit_ids"]) for uid in data["unit_ids"]]
        pity_ids = list(data["pity_ids"])
        if data["copy_pity_from"] and data["copy_pity_from"] != banner_id:
            src = cur.execute(
                "SELECT pity_id FROM banner_pity WHERE banner_id = ? ORDER BY pity_id",
                (data["copy_pity_from"],),
            ).fetchall()
            if src:
                pity_ids = [r["pity_id"] for r in src]

        err = _validate_banner_form(
            cur,
            data["name"],
            data["unit_ids"],
            pity_ids,
            data["starts_at"],
            data["ends_at"],
        )
        if not err and _name_taken(cur, data["name"], banner_id):
            err = "A banner with that name already exists."
        if not err:
            err = _validate_rateup_pool(cur, unit_rateup, pity_ids)
        if err:
            flash(err, "error")
            units = sqlite_helper.get_units_for_admin(cur)
            pities = sqlite_helper.get_pity_rows(cur)
            currencies_rows = sqlite_helper.get_currency_rows(cur)
            existing = sqlite_helper.get_all_banners_admin(cur)
            selected_units = {uid: (uid in data["rateup_unit_ids"]) for uid in data["unit_ids"]}
            return render_template(
                "admin/banner_form.html",
                current_user=current_user,
                currencies=currencies,
                units=units,
                pities=pities,
                currencies_rows=currencies_rows,
                existing_banners=existing,
                banner={
                    "id": banner_id,
                    "name": data["name"],
                    "active": data["active"],
                    "sort_order": data["sort_order"],
                    "currency_id": data["currency_id"],
                    "starts_at": request.form.get("starts_at"),
                    "ends_at": request.form.get("ends_at"),
                },
                selected_units=selected_units,
                selected_pity=set(pity_ids),
            )

        sqlite_helper.update_banner(
            cur,
            banner_id,
            data["name"],
            data["active"],
            data["starts_at"],
            data["ends_at"],
            data["sort_order"],
            data["currency_id"],
        )
        sqlite_helper.replace_banner_units(cur, banner_id, unit_rateup)
        sqlite_helper.replace_banner_pity(cur, banner_id, pity_ids)
        con.commit()
    flash("Banner updated.", "success")
    return redirect(url_for("admin_banners_list"))


@app.route("/admin/banners/<int:banner_id>/duplicate", methods=["POST"])
@admin_required
def admin_banner_duplicate(banner_id):
    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        detail = sqlite_helper.get_banner_admin_detail(cur, banner_id)
        if not detail:
            abort(404)
        src = detail["banner"]
        new_name = src["name"] + " (copy)"
        suffix = 2
        while cur.execute("SELECT 1 FROM banners WHERE name = ?", (new_name,)).fetchone():
            new_name = f"{src['name']} (copy {suffix})"
            suffix += 1
        new_id = sqlite_helper.insert_banner(
            cur,
            new_name,
            False,
            src["starts_at"],
            src["ends_at"],
            src["sort_order"],
            src["currency_id"],
        )
        unit_rateup = [(u["unit_id"], bool(u["rateup"])) for u in detail["units"]]
        sqlite_helper.replace_banner_units(cur, new_id, unit_rateup)
        sqlite_helper.replace_banner_pity(cur, new_id, detail["pity_ids"])
        con.commit()
    flash(f"Banner duplicated as #{new_id} \"{new_name}\" (inactive).", "success")
    return redirect(url_for("admin_banner_edit", banner_id=new_id))


@app.route("/admin/banners/<int:banner_id>/delete", methods=["POST"])
@admin_required
def admin_banner_delete(banner_id):
    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        detail = sqlite_helper.get_banner_admin_detail(cur, banner_id)
        if not detail:
            abort(404)
        name = detail["banner"]["name"]
        sqlite_helper.delete_banner(cur, banner_id)
        con.commit()
    flash(f"Banner #{banner_id} \"{name}\" deleted.", "success")
    return redirect(url_for("admin_banners_list"))


# ---------------------------------------------------------------------------
# Missions admin
# ---------------------------------------------------------------------------

def _mission_status(row, db_now):
    if not row["starts_at"] and not row["ends_at"]:
        return "Permanent"
    if row["starts_at"] and row["starts_at"] > db_now:
        return "Scheduled"
    if row["ends_at"] and row["ends_at"] <= db_now:
        return "Ended"
    return "Active"


def _parse_mission_form():
    description = (request.form.get("description") or "").strip()
    reward = int(request.form.get("reward") or 0)
    reset = request.form.get("reset") or "None"
    requirement = int(request.form.get("requirement") or 1)
    currency_id = int(request.form.get("currency_id") or 1)
    permanent = request.form.get("permanent") == "on"
    if permanent:
        starts_at = None
        ends_at = None
    else:
        starts_at = _parse_schedule_dt(request.form.get("starts_at"))
        ends_at = _parse_schedule_dt(request.form.get("ends_at"))
    return {
        "description": description,
        "reward": reward,
        "reset": reset,
        "requirement": requirement,
        "currency_id": currency_id,
        "starts_at": starts_at,
        "ends_at": ends_at,
    }


def _validate_mission_form(data):
    if not data["description"]:
        return "Description is required."
    if data["reward"] < 0:
        return "Reward must be non-negative."
    if data["requirement"] < 1:
        return "Requirement must be at least 1."
    if data["starts_at"] and data["ends_at"] and data["ends_at"] <= data["starts_at"]:
        return "End time must be after start time."
    return None


@app.route("/admin/missions", methods=["GET"])
@admin_required
def admin_missions_list():
    current_user, currencies = user.load_user()
    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        db_now = cur.execute("SELECT datetime('now') AS now").fetchone()["now"]
        rows = sqlite_helper.get_all_missions_admin(cur)
        currency_rows = sqlite_helper.get_currency_rows(cur)
    currency_map = {c["id"]: c["name"] for c in currency_rows}
    for r in rows:
        r["status"] = _mission_status(r, db_now)
        r["currency_name"] = currency_map.get(r["currency_id"], str(r["currency_id"]))
    return render_template(
        "admin/missions.html",
        current_user=current_user,
        currencies=currencies,
        missions=rows,
        db_now=db_now,
    )


@app.route("/admin/missions/new", methods=["GET", "POST"])
@admin_required
def admin_mission_new():
    current_user, currencies = user.load_user()
    if request.method == "GET":
        with sqlite3.connect(Config.DATABASE_URI) as con:
            con.row_factory = sqlite_helper.dict_factory
            cur = con.cursor()
            currencies_rows = sqlite_helper.get_currency_rows(cur)
        return render_template(
            "admin/mission_form.html",
            current_user=current_user,
            currencies=currencies,
            currencies_rows=currencies_rows,
            mission=None,
        )

    data = _parse_mission_form()
    err = _validate_mission_form(data)
    if err:
        flash(err, "error")
        with sqlite3.connect(Config.DATABASE_URI) as con:
            con.row_factory = sqlite_helper.dict_factory
            cur = con.cursor()
            currencies_rows = sqlite_helper.get_currency_rows(cur)
        return render_template(
            "admin/mission_form.html",
            current_user=current_user,
            currencies=currencies,
            currencies_rows=currencies_rows,
            mission=data,
        )

    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        sqlite_helper.insert_mission(
            cur,
            data["description"],
            data["reward"],
            data["reset"],
            data["requirement"],
            data["currency_id"],
            data["starts_at"],
            data["ends_at"],
        )
        con.commit()
    flash("Mission created.", "success")
    return redirect(url_for("admin_missions_list"))


@app.route("/admin/missions/<int:mission_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_mission_edit(mission_id):
    current_user, currencies = user.load_user()
    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        mission = sqlite_helper.get_mission_by_id(cur, mission_id)
        if not mission:
            abort(404)

        if request.method == "GET":
            currencies_rows = sqlite_helper.get_currency_rows(cur)
            return render_template(
                "admin/mission_form.html",
                current_user=current_user,
                currencies=currencies,
                currencies_rows=currencies_rows,
                mission=mission,
            )

        data = _parse_mission_form()
        err = _validate_mission_form(data)
        if err:
            flash(err, "error")
            currencies_rows = sqlite_helper.get_currency_rows(cur)
            return render_template(
                "admin/mission_form.html",
                current_user=current_user,
                currencies=currencies,
                currencies_rows=currencies_rows,
                mission={**data, "id": mission_id},
            )

        sqlite_helper.update_mission(
            cur,
            mission_id,
            data["description"],
            data["reward"],
            data["reset"],
            data["requirement"],
            data["currency_id"],
            data["starts_at"],
            data["ends_at"],
        )
        con.commit()
    flash("Mission updated.", "success")
    return redirect(url_for("admin_missions_list"))


@app.route("/admin/missions/<int:mission_id>/delete", methods=["POST"])
@admin_required
def admin_mission_delete(mission_id):
    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        mission = sqlite_helper.get_mission_by_id(cur, mission_id)
        if not mission:
            abort(404)
        sqlite_helper.delete_mission(cur, mission_id)
        con.commit()
    flash(f"Mission #{mission_id} deleted.", "success")
    return redirect(url_for("admin_missions_list"))


# ---------------------------------------------------------------------------
# Characters (units) admin
# ---------------------------------------------------------------------------

@app.route("/admin/characters", methods=["GET"])
@admin_required
def admin_characters_list():
    current_user, currencies = user.load_user()
    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        units = sqlite_helper.get_all_units_admin(cur)
    return render_template(
        "admin/characters.html",
        current_user=current_user,
        currencies=currencies,
        units=units,
    )


@app.route("/admin/characters/new", methods=["GET", "POST"])
@admin_required
def admin_character_new():
    current_user, currencies = user.load_user()

    def _existing_ids():
        with sqlite3.connect(Config.DATABASE_URI) as con:
            con.row_factory = sqlite_helper.dict_factory
            cur = con.cursor()
            return [r["id"] for r in cur.execute("SELECT id FROM units").fetchall()]

    if request.method == "GET":
        return render_template(
            "admin/character_form.html",
            current_user=current_user,
            currencies=currencies,
            unit=None,
            existing_ids=_existing_ids(),
        )

    unit_id = request.form.get("unit_id", "").strip()
    rarity = request.form.get("rarity", "").strip()

    if not unit_id or not unit_id.isdigit():
        flash("A valid numeric ID is required.", "error")
        return render_template(
            "admin/character_form.html",
            current_user=current_user,
            currencies=currencies,
            unit={"id": unit_id, "rarity": rarity},
            existing_ids=_existing_ids(),
        )

    unit_id = int(unit_id)
    if rarity not in ("R", "SR", "SSR"):
        flash("Rarity must be R, SR, or SSR.", "error")
        return render_template(
            "admin/character_form.html",
            current_user=current_user,
            currencies=currencies,
            unit={"id": unit_id, "rarity": rarity},
            existing_ids=_existing_ids(),
        )

    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        existing = cur.execute("SELECT 1 FROM units WHERE id = ?", (unit_id,)).fetchone()
        if existing:
            flash(f"Unit #{unit_id} already exists.", "error")
            return render_template(
                "admin/character_form.html",
                current_user=current_user,
                currencies=currencies,
                unit={"id": unit_id, "rarity": rarity},
                existing_ids=_existing_ids(),
            )
        sqlite_helper.insert_unit(cur, unit_id, rarity)
        con.commit()
    flash(f"Character #{unit_id} ({rarity}) added.", "success")
    return redirect(url_for("admin_characters_list"))


@app.route("/admin/characters/<int:unit_id>/delete", methods=["POST"])
@admin_required
def admin_character_delete(unit_id):
    with sqlite3.connect(Config.DATABASE_URI) as con:
        con.row_factory = sqlite_helper.dict_factory
        cur = con.cursor()
        existing = cur.execute("SELECT 1 FROM units WHERE id = ?", (unit_id,)).fetchone()
        if not existing:
            abort(404)
        in_banner = cur.execute(
            "SELECT banner_id FROM banner_units WHERE unit_id = ? LIMIT 1", (unit_id,)
        ).fetchone()
        if in_banner:
            flash(f"Cannot delete unit #{unit_id} — it is used in banner #{in_banner['banner_id']}. Remove it from all banners first.", "error")
            return redirect(url_for("admin_characters_list"))
        sqlite_helper.delete_unit(cur, unit_id)
        con.commit()
    flash(f"Character #{unit_id} deleted.", "success")
    return redirect(url_for("admin_characters_list"))
