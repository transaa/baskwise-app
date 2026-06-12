"""PriceWise — receipt-powered price tracker dashboard.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pricewise import db
from pricewise.location import (
    AREA, CITY, REGION, TIER_ORDER, is_nearby, location_label, place_str,
)
from pricewise.ocr import image_to_text_with_confidence, ocr_available
from pricewise.quality import assess as assess_quality
from pricewise.parser import parse_receipt
from pricewise.freshness import is_stale, label as freshness_label
from pricewise.insights import staple_inflation
from pricewise.savings import analyze_receipt, top_opportunities
from pricewise.seed import ensure_seeded
from pricewise.upc import resolve_upc
from pricewise.watches import evaluate_watches

st.set_page_config(page_title="baskwise", page_icon="🧺", layout="wide")


# --- data access -----------------------------------------------------------

@st.cache_data(ttl=5)
def load_items() -> pd.DataFrame:
    with db.get_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT i.id, i.name, i.norm_key, i.category, i.qty,
                   i.unit_price, i.line_total, i.upc,
                   r.store, r.city, r.state, r.zip,
                   r.purchased_on, r.id AS receipt_id
            FROM items i
            JOIN receipts r ON r.id = i.receipt_id
            """,
            conn,
        )
    if not df.empty:
        df["purchased_on"] = pd.to_datetime(df["purchased_on"], errors="coerce")
        df["month"] = df["purchased_on"].dt.to_period("M").astype(str)
    return df


@st.cache_data(ttl=3600)
def resolve_upc_cached(upc: str):
    return resolve_upc(upc)


def refresh() -> None:
    load_items.clear()


# --- bootstrap -------------------------------------------------------------

added = ensure_seeded()

st.title("🧺 baskwise")
st.caption(
    "Snap your receipts. We turn them into a price database and show you which "
    "store is cheaper — so you save money on your next trip."
)
if added:
    st.success(f"Loaded {added} sample receipts to get you started.")

df = load_items()

# --- home location (powers all "near you" comparisons) ---------------------
home_zip, home_state, home_city = "", "", ""
if not df.empty:
    # Order locations by how much data each has, so the default home is the
    # user's main shopping area (the most-seen ZIP), not an arbitrary one.
    by_zip = df.dropna(subset=["zip"]).copy()
    counts = by_zip.groupby("zip")["receipt_id"].nunique()
    locs = (
        by_zip[["zip", "state", "city"]].drop_duplicates().assign(
            n=lambda d: d["zip"].map(counts)
        ).sort_values("n", ascending=False)
    )
    loc_labels = {
        f"{r.city}, {r.state} {r.zip}": (str(r.zip), str(r.state), str(r.city))
        for r in locs.itertuples()
    }
    if loc_labels:
        st.sidebar.header("📍 Your location")
        st.sidebar.caption("Sets what counts as 'near you' for price comparisons.")
        pick = st.sidebar.selectbox("Home ZIP", list(loc_labels.keys()))
        home_zip, home_state, home_city = loc_labels[pick]
        st.sidebar.caption(
            f"Showing deals near **{pick}**.\n\n"
            "📍 same ZIP = your area · 🚗 same city = your city · "
            "🗺️ same state = your region"
        )

with st.sidebar:
    st.divider()
    if db.is_postgres():
        st.caption("🐘 Storage: **Postgres** — persistent, shared community database ✅")
    else:
        st.caption("💾 Storage: SQLite (local / resets on restart)")
    with st.expander("ℹ️ About baskwise"):
        st.caption(
            "baskwise turns your receipts into a real, local price database and "
            "shows you where to shop to save — built around real shoppers, not "
            "retailer ads.\n\n"
            "🌐 [baskwise.com](https://baskwise.com) · 📱 [baskwise.app](https://baskwise.app)"
        )

if df.empty:
    st.warning("No data yet. Add a receipt in the **Add Receipt** tab.")

(tab_savings, tab_alerts, tab_upc, tab_overview, tab_prices,
 tab_basket, tab_add) = st.tabs(
    ["💰 Savings Finder", "🔔 Alerts", "🔍 UPC Lookup", "📊 Overview",
     "📈 Price History", "🛒 Basket Comparison", "➕ Add Receipt"]
)


# --- Savings Finder --------------------------------------------------------

with tab_savings:
    if df.empty:
        st.info("Add a receipt to find savings.")
    else:
        # --- proactive: biggest savings opportunities near you ---
        opps = top_opportunities(df, home_zip, home_state, home_city, limit=5)
        if opps:
            st.subheader("🔥 Top savings opportunities near you")
            st.caption(
                "Switch stores on these and pocket the difference every time. "
                "Tap **🔔 Watch** to get alerted if the price climbs."
            )
            for o in opps:
                txt_col, btn_col = st.columns([6, 1])
                txt_col.markdown(
                    f"**{o['item']}** — you pay \\${o['your_unit']:.2f} at "
                    f"{o['your_store']}, but it's **\\${o['best_unit']:.2f} at "
                    f"{o['best_store']}** ({o['best_place']}) → "
                    f"**save \\${o['savings']:.2f}/unit**"
                )
                if btn_col.button("🔔 Watch", key=f"watchopp_{o['norm_key']}"):
                    with db.session() as conn:
                        db.add_watch(
                            conn, norm_key=o["norm_key"], label=o["item"],
                            threshold=float(o["best_unit"]),
                        )
                    st.toast(
                        f"Watching {o['item']} — alerting at ${o['best_unit']:.2f} or below."
                    )
                    st.rerun()
            st.divider()

        st.subheader("How much could you have saved?")
        st.caption(
            "Pick a receipt. We check each item against the cheapest price at stores "
            "**near you**, and show where to buy next time."
        )

        receipts = (
            df[["receipt_id", "store", "purchased_on"]]
            .drop_duplicates()
            .sort_values("purchased_on", ascending=False)
        )
        label_to_id = {
            f"{r.store} — {r.purchased_on.date()}": int(r.receipt_id)
            for r in receipts.itertuples()
        }
        choice = st.selectbox("Receipt to analyze", list(label_to_id.keys()))
        result = analyze_receipt(df, label_to_id[choice], home_zip, home_state, home_city)

        c1, c2, c3 = st.columns(3)
        c1.metric("You paid", f"${result['paid_total']:.2f}")
        c2.metric("Cheapest possible", f"${result['optimized_total']:.2f}")
        c3.metric(
            "Potential savings",
            f"${result['savings']:.2f}",
            delta=f"-{result['savings']:.2f}" if result["savings"] > 0 else "0.00",
            delta_color="inverse",
        )

        if result["savings"] > 0.001:
            st.success(
                f"💡 You could have saved **${result['savings']:.2f}** on this trip "
                f"by buying each item at its cheapest store near you."
            )
        else:
            st.info(
                f"Nice — **{result['receipt_store']}** was already the cheapest option "
                "near you for everything on this receipt (based on current data)."
            )

        rows = pd.DataFrame(result["rows"])
        if not rows.empty:
            view = rows.copy()
            view["paid"] = view.apply(
                lambda r: f"${r['paid_unit']:.2f} @ {r['paid_store']}", axis=1
            )
            view["cheapest"] = view.apply(
                lambda r: (
                    f"${r['best_unit']:.2f} @ {r['best_store']}"
                    + ("  ✅ switch" if r["cheaper_elsewhere"] else "  (same)")
                ),
                axis=1,
            )
            view["save/unit"] = view["savings"].apply(
                lambda s: f"${s:.2f}" if s > 0.001 else "—"
            )
            st.dataframe(
                view[["item", "category", "qty", "paid", "cheapest", "save/unit"]],
                use_container_width=True,
                hide_index=True,
            )

            switches = rows[rows["cheaper_elsewhere"]]
            if not switches.empty:
                st.subheader("🛒 Your money-saving shopping plan")
                st.caption("Where to buy each item next time for the lowest total — all near you.")
                plan = {}
                for _, r in rows.iterrows():
                    plan.setdefault(r["best_store"], {"place": r["best_place"], "items": []})
                    plan[r["best_store"]]["items"].append(
                        f"{r['item']} (${r['best_unit']:.2f})"
                    )
                cols = st.columns(len(plan))
                for col, (store, info) in zip(cols, plan.items()):
                    with col:
                        header = f"**{store}**"
                        if info["place"]:
                            header += f"  \n_{info['place']}_"
                        st.markdown(header)
                        for line in info["items"]:
                            st.markdown(f"- {line}")


# --- Alerts ----------------------------------------------------------------

with tab_alerts:
    st.subheader("🔔 Price-drop alerts")
    st.caption(
        "Set a target price for the things you buy. baskwise flags them the "
        "moment they drop to your price at a store near you."
    )
    if df.empty:
        st.info("Add a receipt first so there are products to watch.")
    else:
        with db.session() as conn:
            watches = db.list_watches(conn)
        evals = evaluate_watches(df, watches, home_zip, home_state, home_city)

        triggered = [e for e in evals if e["triggered"]]
        if triggered:
            for e in triggered:
                st.success(
                    f"🔔 **{e['label']}** hit your target — now "
                    f"**\\${e['best_unit']:.2f}** at {e['best_store']} "
                    f"({e['best_place']}), at or below your \\${e['threshold']:.2f} target."
                )

        if evals:
            st.markdown("**Your watches**")
            for e in evals:
                c1, c2, c3, c4 = st.columns([3, 2, 4, 1])
                c1.markdown(f"**{e['label']}**")
                c2.markdown(f"target \\${e['threshold']:.2f}")
                if e["has_data"]:
                    tag = (
                        "🟢 at/below target" if e["triggered"]
                        else f"🔴 \\${e['gap']:.2f} above"
                    )
                    c3.markdown(
                        f"cheapest \\${e['best_unit']:.2f} @ {e['best_store']} — {tag}"
                    )
                else:
                    c3.markdown("_no price data near you yet_")
                if c4.button("🗑", key=f"del_{e['id']}", help="Remove this watch"):
                    with db.session() as conn:
                        db.delete_watch(conn, e["id"])
                    st.rerun()
        else:
            st.caption("No watches yet — add one below.")

        st.divider()
        st.markdown("**Add a watch**")
        prods = (
            df.groupby(["norm_key", "name"]).size().reset_index(name="n")
            .sort_values("n", ascending=False)
        )
        name_to_key = {r["name"]: r["norm_key"] for _, r in prods.iterrows()}
        a1, a2, a3 = st.columns([3, 2, 1])
        psel = a1.selectbox("Product", list(name_to_key.keys()), key="watch_prod")
        thr = a2.number_input(
            "Alert me at/below ($)", min_value=0.0, value=3.00, step=0.10, key="watch_thr"
        )
        a3.markdown("<br>", unsafe_allow_html=True)
        if a3.button("➕ Add", type="primary", key="watch_add"):
            with db.session() as conn:
                db.add_watch(
                    conn, norm_key=name_to_key[psel], label=psel, threshold=float(thr)
                )
            st.rerun()


# --- UPC Lookup ------------------------------------------------------------

with tab_upc:
    st.subheader("Look up any item by its barcode (UPC)")
    st.caption(
        "A UPC is a global standard — the same code is the same product at every "
        "store. Enter one to identify the product and see every price the "
        "community has logged for it, cheapest first."
    )

    # UPCs already present in the receipt data, as one-tap quick-pick buttons.
    known = (
        df[df["upc"].notna()][["upc", "name"]].drop_duplicates()
        if not df.empty else pd.DataFrame(columns=["upc", "name"])
    )
    examples: dict[str, str] = {}
    for r in known.itertuples():
        examples.setdefault(r.upc, r.name)

    if examples:
        st.caption("Quick pick a product from your receipts:")
        cols = st.columns(len(examples))
        for col, (code, name) in zip(cols, examples.items()):
            if col.button(name, key=f"upcpick_{code}", use_container_width=True):
                st.session_state["upc_choice"] = code

    typed = st.text_input("…or type/scan any UPC", placeholder="e.g. 3017620422003")
    upc = typed.strip() if typed.strip() else st.session_state.get("upc_choice", "")

    if upc:
        product = resolve_upc_cached(upc)

        badge = {
            "openfoodfacts": "🟢 Open Food Facts (live)",
            "offline-cache": "🟡 offline cache",
            "unknown": "⚪ not in product database",
        }.get(product.source, product.source)

        if product.found:
            st.markdown(f"### {product.name}")
            meta = " · ".join(x for x in [product.brand, product.category] if x)
            st.markdown(f"**UPC {product.upc}** — {meta or 'no extra detail'}  \n_{badge}_")
        else:
            st.markdown(f"### UPC {product.upc}")
            st.caption(f"{badge} — we couldn't identify this product, but price data still works.")

        prices = df[df["upc"] == upc] if not df.empty else pd.DataFrame()

        if not prices.empty:
            # Latest price per physical store location (store + ZIP).
            latest = (
                prices.sort_values("purchased_on")
                .groupby(["store", "city", "state", "zip"], as_index=False, dropna=False)
                .tail(1)
                .copy()
            )
            latest["proximity"] = latest.apply(
                lambda r: location_label(
                    r["zip"], r["state"], home_zip, home_state,
                    r["city"], home_city,
                ),
                axis=1,
            )
            latest["place"] = latest.apply(
                lambda r: place_str(r["city"], r["state"], r["zip"]), axis=1
            )
            latest["tier"] = latest["proximity"].map(TIER_ORDER).fillna(9)
            latest = latest.sort_values(["tier", "unit_price"])

            near = latest[latest["proximity"].apply(is_nearby)]
            cheapest_anywhere = latest.loc[latest["unit_price"].idxmin()]

            if not near.empty:
                best_near = near.loc[near["unit_price"].idxmin()]
                st.success(
                    f"💲 Cheapest **near you**: **{best_near['store']}** at "
                    f"**${best_near['unit_price']:.2f}** — {best_near['place']} "
                    f"({freshness_label(best_near['purchased_on'])})"
                )
                if is_stale(best_near["purchased_on"]):
                    st.caption(
                        "⚠️ This price is getting old — it may have changed in store. "
                        "Snap a fresh receipt to update it for everyone."
                    )
                # Is somewhere else (out of town) cheaper, and how much?
                if cheapest_anywhere["unit_price"] < best_near["unit_price"] - 0.001:
                    diff = best_near["unit_price"] - cheapest_anywhere["unit_price"]
                    st.caption(
                        f"ℹ️ It's \\${cheapest_anywhere['unit_price']:.2f} at "
                        f"{cheapest_anywhere['store']} in {cheapest_anywhere['place']} "
                        f"(\\${diff:.2f} less), but that's outside your area."
                    )
            else:
                st.warning(
                    f"No prices logged near you yet. Cheapest anywhere: "
                    f"**{cheapest_anywhere['store']}** at "
                    f"**${cheapest_anywhere['unit_price']:.2f}** "
                    f"({cheapest_anywhere['place']})."
                )

            badge_map = {
                AREA: "📍 your area", CITY: "🚗 your city", REGION: "🗺️ your region",
            }
            show = latest[["store", "place", "proximity", "unit_price", "purchased_on"]].copy()
            show["proximity"] = show["proximity"].map(
                lambda p: badge_map.get(p, "🌎 other regions")
            )
            show["unit_price"] = show["unit_price"].map("${:.2f}".format)
            show["purchased_on"] = show["purchased_on"].map(freshness_label)
            show.columns = ["Store", "Location", "Distance", "Latest price", "Freshness"]
            st.dataframe(show, use_container_width=True, hide_index=True)
            st.caption(
                "Prices are the **freshest the community has reported**, with their age. "
                "🟢 fresh (≤2 wks) · 🟡 aging · 🔴 stale (>6 wks). They get more "
                "real-time as more shoppers snap receipts near you."
            )

            near_spread = (
                near["unit_price"].max() - near["unit_price"].min()
                if len(near) >= 2 else 0
            )
            if near_spread > 0.001:
                st.caption(
                    f"Price spread in your area: **${near_spread:.2f}** — that's the "
                    "money on the table for this one item, just by picking the right store."
                )

            st.markdown("**Price history (all locations)**")
            hist = prices.copy()
            hist["where"] = hist.apply(
                lambda r: f"{r['store']} ({r['city']})", axis=1
            )
            chart = hist.pivot_table(
                index="purchased_on", columns="where", values="unit_price"
            )
            st.line_chart(chart)
        else:
            st.info(
                "No community prices logged for this UPC yet. "
                "Scan it on your next shopping trip to be the first!"
            )


# --- Overview --------------------------------------------------------------

with tab_overview:
    if df.empty:
        st.info("Add a receipt to see your spending overview.")
    else:
        total_spend = df["line_total"].sum()
        n_receipts = df["receipt_id"].nunique()
        n_items = len(df)
        n_stores = df["store"].nunique()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total tracked", f"${total_spend:,.2f}")
        c2.metric("Receipts", n_receipts)
        c3.metric("Line items", n_items)
        c4.metric("Stores", n_stores)

        # --- personal grocery inflation ---
        ins = staple_inflation(df)
        if ins["rows"]:
            st.subheader("📉 Your grocery inflation")
            arrow = "▲" if ins["basket_pct"] > 0 else ("▼" if ins["basket_pct"] < 0 else "■")
            st.markdown(
                f"Across the staples you buy repeatedly, your basket went from "
                f"**\\${ins['first_total']:.2f}** to **\\${ins['last_total']:.2f}** "
                f"({ins['from_date']} → {ins['to_date']}) — "
                f"**{arrow} {ins['basket_pct']:+.1f}%**."
            )
            risers = [r for r in ins["rows"] if r["pct"] > 0][:5]
            if risers:
                st.caption("Biggest price increases on your staples:")
                rdf = pd.DataFrame(risers)
                rdf["was → now"] = rdf.apply(
                    lambda r: f"${r['first_unit']:.2f} → ${r['last_unit']:.2f}", axis=1
                )
                rdf["change"] = rdf["pct"].map(lambda p: f"+{p:.1f}%")
                st.dataframe(
                    rdf[["item", "category", "was → now", "change"]],
                    use_container_width=True, hide_index=True,
                )

        st.subheader("Spending by month")
        by_month = df.groupby("month")["line_total"].sum().sort_index()
        st.bar_chart(by_month)

        left, right = st.columns(2)
        with left:
            st.subheader("By store")
            by_store = df.groupby("store")["line_total"].sum().sort_values(ascending=False)
            st.bar_chart(by_store)
        with right:
            st.subheader("By category")
            by_cat = df.groupby("category")["line_total"].sum().sort_values(ascending=False)
            st.bar_chart(by_cat)


# --- Price History ---------------------------------------------------------

with tab_prices:
    if df.empty:
        st.info("Add a receipt to track price history.")
    else:
        st.subheader("How has the price of an item changed?")
        # Offer items that appear more than once so the chart is meaningful.
        counts = df.groupby(["norm_key", "name"]).size().reset_index(name="n")
        counts = counts.sort_values("n", ascending=False)
        label_to_key = {
            f"{row['name']}  ({row['n']} purchases)": row["norm_key"]
            for _, row in counts.iterrows()
        }
        choice = st.selectbox("Pick an item", list(label_to_key.keys()))
        key = label_to_key[choice]

        item_df = df[df["norm_key"] == key].sort_values("purchased_on")
        pivot = item_df.pivot_table(
            index="purchased_on", columns="store", values="unit_price", aggfunc="mean"
        )
        st.line_chart(pivot)

        latest = item_df.sort_values("purchased_on").groupby("store").tail(1)
        cheapest = latest.loc[latest["unit_price"].idxmin()]
        st.markdown(
            f"**Cheapest right now:** {cheapest['store']} at "
            f"**${cheapest['unit_price']:.2f}**"
        )

        first = item_df.iloc[0]
        last = item_df.iloc[-1]
        if first["unit_price"] and first["unit_price"] != last["unit_price"]:
            pct = (last["unit_price"] - first["unit_price"]) / first["unit_price"] * 100
            arrow = "🔺" if pct > 0 else "🔻"
            st.caption(
                f"{arrow} {pct:+.1f}% since {first['purchased_on'].date()} "
                f"(\\${first['unit_price']:.2f} → \\${last['unit_price']:.2f})"
            )

        st.dataframe(
            item_df[["purchased_on", "store", "unit_price", "qty", "line_total"]]
            .rename(columns={"purchased_on": "date"})
            .reset_index(drop=True),
            use_container_width=True,
        )


# --- Basket Comparison -----------------------------------------------------

with tab_basket:
    if df.empty:
        st.info("Add a receipt to compare baskets across stores.")
    else:
        st.subheader("Which store is cheaper for your basket?")
        st.caption("Uses the most recent known price for each item at each store.")

        names = (
            df.groupby(["norm_key", "name"]).size().reset_index(name="n")
            .sort_values("n", ascending=False)
        )
        name_to_key = {row["name"]: row["norm_key"] for _, row in names.iterrows()}
        picked = st.multiselect(
            "Build a basket",
            list(name_to_key.keys()),
            default=list(name_to_key.keys())[:5],
        )

        if picked:
            keys = [name_to_key[p] for p in picked]
            basket = df[df["norm_key"].isin(keys)].copy()
            # Latest unit price per (item, store).
            latest = (
                basket.sort_values("purchased_on")
                .groupby(["norm_key", "name", "store"])
                .tail(1)
            )
            table = latest.pivot_table(
                index="name", columns="store", values="unit_price", aggfunc="mean"
            )
            st.dataframe(table.style.format("${:.2f}"), use_container_width=True)

            totals = table.sum(min_count=1)
            coverage = table.notna().sum()
            summary = pd.DataFrame(
                {
                    "Basket total": totals,
                    "Items priced": coverage,
                    "of": len(picked),
                }
            ).sort_values("Basket total")
            st.subheader("Basket totals by store")
            st.dataframe(
                summary.style.format({"Basket total": "${:.2f}"}),
                use_container_width=True,
            )

            full = totals.dropna()
            if len(full) >= 2:
                best, worst = full.idxmin(), full.idxmax()
                saving = full[worst] - full[best]
                st.success(
                    f"🏆 **{best}** is cheapest for this basket — "
                    f"about **${saving:.2f}** less than {worst}."
                )
            elif len(full) == 1:
                st.info(f"Only **{full.index[0]}** has every item priced so far.")
            else:
                st.info("No single store has all items priced yet — add more receipts.")


# --- Add Receipt -----------------------------------------------------------

with tab_add:
    st.subheader("📸 Add a receipt to your journal")
    st.caption(
        "Snap it — baskwise reads every item, price, store, and date. It's saved "
        "to **your grocery journal**, and the facts (item · price · store · date) "
        "join the **community price database** that powers savings for everyone. "
        "Every receipt makes it smarter — for you and for all shoppers."
    )

    ok, reason = ocr_available()
    mode = st.radio(
        "How do you want to add it?",
        ["📷 Take a photo", "📁 Upload a photo", "📝 Paste text"],
        horizontal=True,
    )

    text = ""
    img_bytes = None
    ocr_conf = None

    if mode == "📷 Take a photo":
        st.info(
            "📋 **For a clean read:** lay the receipt flat, good lighting, and fit "
            "the **whole** receipt in frame — top to bottom, nothing cut off."
        )
        if not ok:
            st.warning(f"Photo reading isn't available here: {reason}")
        shot = st.camera_input("Point at your receipt and snap", disabled=not ok)
        if shot is not None and ok:
            img_bytes = shot.getvalue()

    elif mode == "📁 Upload a photo":
        st.caption("Already have a photo? Upload it here.")
        if not ok:
            st.warning(f"Photo reading isn't available here: {reason}")
        up = st.file_uploader("Receipt photo", type=["png", "jpg", "jpeg"], disabled=not ok)
        if up is not None and ok:
            img_bytes = up.getvalue()

    else:
        text = st.text_area(
            "Paste the receipt text",
            height=220,
            placeholder="Walmart Supercenter\nDallas, TX 75201\n06/01/2026\nMILK 1GAL  3.46\nEGGS 12CT  3.28\n...",
        )

    if img_bytes is not None:
        with st.spinner("📖 Reading your receipt…"):
            ocr_text, ocr_conf = image_to_text_with_confidence(img_bytes)
        if ocr_conf is not None:
            tone = "🟢" if ocr_conf >= 80 else ("🟡" if ocr_conf >= 60 else "🔴")
            st.caption(f"{tone} OCR read confidence: **{ocr_conf:.0f}%**")
            if ocr_conf < 60:
                st.warning(
                    "Low read confidence — the photo may be blurry, dim, or cut off. "
                    "A clearer picture gives more accurate prices. Check the text below carefully."
                )
        st.text_area(
            "Here's what we read — fix any typos before saving:",
            value=ocr_text, height=200, key="ocr_text",
        )
        text = st.session_state.get("ocr_text", ocr_text)

    if text.strip():
        parsed = parse_receipt(text)
        place = ", ".join(x for x in [parsed.city, parsed.state] if x)
        when = parsed.purchased_on + (f" {parsed.time}" if parsed.time else "")
        st.markdown(
            f"**Store:** {parsed.store}  |  "
            f"**Where:** {place or 'unknown'} {parsed.zip}  |  "
            f"**When:** {when or 'unknown'}  |  "
            f"**Items:** {len(parsed.items)}  |  "
            f"**Total:** ${parsed.computed_total:.2f}"
        )

        # --- quality check: accuracy gate before data enters the database ---
        report = assess_quality(parsed, ocr_conf)
        grade_badge = {
            "high": "🟢 High confidence — looks accurate",
            "medium": "🟡 Review recommended",
            "low": "🔴 Needs attention before saving",
        }[report["grade"]]
        st.markdown(f"**🔎 Quality check — {grade_badge}**")
        for c in report["checks"]:
            icon = {True: "✅", False: "❌", None: "➖"}[c.ok]
            detail = c.detail.replace("$", "\\$")  # avoid markdown treating $..$ as LaTeX
            st.markdown(f"{icon} **{c.label}:** {detail}")
        if report["reconciled"] is False:
            st.warning(
                "The item prices don't add up to the receipt's total — likely an "
                "OCR misread. Please fix the numbers above so the data stays accurate "
                "for everyone."
            )

        # Date is MANDATORY — without it we can't tell if prices are current, and
        # we won't feed others a false "fresh" price.
        save_date = parsed.purchased_on
        if not parsed.has_date:
            st.error(
                "📅 **No date found on this receipt — and the date is required.** "
                "Without it we can't tell whether these prices are current, and we "
                "won't show other shoppers a false 'fresh' price. Please enter the "
                "**exact date printed on the receipt** (not today, unless that's when "
                "you bought it)."
            )
            picked_date = st.date_input("Purchase date (from the receipt)", value=None)
            save_date = picked_date.isoformat() if picked_date else ""
            st.caption(
                "💡 Tip: receipts with the date cut off can carry very old prices — "
                "best to re-photograph with the date visible."
            )

        if parsed.items:
            preview = pd.DataFrame([vars(i) for i in parsed.items])[
                ["name", "category", "qty", "unit_price", "line_total", "upc"]
            ]
            st.dataframe(preview, use_container_width=True, hide_index=True)

            can_save = bool(save_date)
            if not can_save:
                st.button("💾 Save to my journal", type="primary", disabled=True,
                          help="Enter the receipt's date first — it's required.")
                st.caption("⛔ Add the purchase date above to enable saving.")
            elif st.button("💾 Save to my journal", type="primary"):
                with db.session() as conn:
                    db.insert_receipt(
                        conn,
                        store=parsed.store,
                        purchased_on=save_date,
                        total=parsed.total
                        if parsed.total is not None
                        else parsed.computed_total,
                        source_file=None,
                        items=[vars(i) for i in parsed.items],
                        city=parsed.city,
                        state=parsed.state,
                        zip=parsed.zip,
                        purchased_time=parsed.time,
                    )
                refresh()
                st.session_state.pop("ocr_text", None)
                st.success(
                    "✅ Saved to your journal — and added to the community price "
                    "database. Thanks for making baskwise smarter for everyone! "
                    "Check the **Savings Finder** and **Overview** tabs."
                )
                st.balloons()
                st.rerun()
        else:
            st.warning(
                "No line items detected. If this was a photo, edit the text above "
                "to fix any misreads, or try a clearer picture."
            )

    with st.expander("⚙️ Admin"):
        st.caption("Reset wipes all data and reloads the bundled samples.")
        if st.button("Reset to sample data"):
            db.reset_db()
            ensure_seeded()
            refresh()
            st.success("Database reset to sample data.")
            st.rerun()


# --- Footer (renders once, below the tabs) ---------------------------------
st.divider()
fcol1, fcol2 = st.columns([3, 1])
fcol1.caption("🧺 **baskwise** — save smarter, every trip.")
fcol2.caption("[baskwise.app](https://baskwise.app)")
