from telegram import Update
from telegram.ext import ContextTypes

from bot.utils import db
from bot.utils.formatters import format_budget_summary


async def show_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user = db.get_user(user.id)
    if not db_user:
        await update.message.reply_text("No budget found. Send /start to set one up!")
        return

    budgets = db.get_budgets(db_user["id"])
    if not budgets:
        await update.message.reply_text("No budget found. Send /start to set one up!")
        return

    spent = db.get_spent_by_category(db_user["id"])

    lines = ["*Your budget overview:*"]
    total_budget = 0.0
    total_spent = 0.0
    for b in budgets:
        cat = b["category"]
        budget_amt = float(b["amount"])
        spent_amt = spent.get(cat, 0.0)
        remaining = budget_amt - spent_amt
        emoji = "✅" if remaining >= 0 else "⚠️"
        lines.append(
            f"{emoji} {cat.title()}: ${spent_amt:,.2f} spent / ${budget_amt:,.2f} budget (${remaining:,.2f} left)"
        )
        total_budget += budget_amt
        total_spent += spent_amt

    total_remaining = total_budget - total_spent
    lines.append(f"\n💰 Total: ${total_spent:,.2f} / ${total_budget:,.2f} (${total_remaining:,.2f} left)")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
