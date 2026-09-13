import discord
from discord.ext import commands
from discord import app_commands
import json
import os

def load_credit_config():
    if not os.path.exists("credit_config.json"):
        with open("credit_config.json", "w") as f:
            json.dump({
                "add_credit_msg": "{who_gave} successfully added {credits_added} credits to {who_given}.",
                "check_credit_msg": "{user} has a total of {credits} credits.",
                "pay_msg": "{user} paid {price} credits for {item_name}. New balance: {new_adjusted_credit}."
            }, f, indent=4)
    with open("credit_config.json", "r") as f:
        return json.load(f)

def save_credit_config(data):
    with open("credit_config.json", "w") as f:
        json.dump(data, f, indent=4)

def get_balance(user_id: int) -> int:
    if not os.path.exists("credits.json"):
        with open("credits.json", "w") as f:
            json.dump({}, f)
    with open("credits.json", "r") as f:
        data = json.load(f)
    return data.get(str(user_id), 0)

def add_balance(user_id: int, amount: int) -> int:
    if not os.path.exists("credits.json"):
        with open("credits.json", "w") as f:
            json.dump({}, f)
    with open("credits.json", "r") as f:
        data = json.load(f)
    uid = str(user_id)
    data[uid] = data.get(uid, 0) + amount
    with open("credits.json", "w") as f:
        json.dump(data, f, indent=4)
    return data[uid]

class CreditTextConfigModal(discord.ui.Modal, title="Edit Credit Texts"):
    add_input = discord.ui.TextInput(
        label="Add Credit Message", 
        style=discord.TextStyle.long,
        placeholder="Vars: {who_gave} {credits_added} {who_given}"
    )
    check_input = discord.ui.TextInput(
        label="Check Credit Message", 
        style=discord.TextStyle.long,
        placeholder="Vars: {user} {credits}"
    )
    pay_input = discord.ui.TextInput(
        label="Pay Message", 
        style=discord.TextStyle.long,
        placeholder="Vars: {user} {price} {item_name} {new_adjusted_credit}"
    )

    def __init__(self, config):
        super().__init__()
        self.add_input.default = config.get("add_credit_msg", "")
        self.check_input.default = config.get("check_credit_msg", "")
        self.pay_input.default = config.get("pay_msg", "")

    async def on_submit(self, interaction: discord.Interaction):
        config = load_credit_config()
        config["add_credit_msg"] = self.add_input.value
        config["check_credit_msg"] = self.check_input.value
        config["pay_msg"] = self.pay_input.value
        save_credit_config(config)
        await interaction.response.send_message("Credit messages updated successfully.", ephemeral=True)

class CreditDashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Edit Messages", style=discord.ButtonStyle.primary)
    async def edit_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_credit_config()
        await interaction.response.send_modal(CreditTextConfigModal(config))

class CreditsSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_credit_config()

    async def has_perms(self, interaction: discord.Interaction) -> bool:
        if await self.bot.is_owner(interaction.user):
            return True
        if not isinstance(interaction.user, discord.Member):
            return False
        if interaction.user.id == interaction.guild.owner_id:
            return True
        perms = interaction.user.guild_permissions
        return perms.administrator or perms.manage_guild

    @app_commands.command(name="creditsetup", description="Open the interactive credit setup dashboard.")
    async def creditsetup(self, interaction: discord.Interaction):
        if not await self.has_perms(interaction):
            return await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        
        status_msg = (
            "**Credit Setup Dashboard**\n\n"
            "Click the button below to edit the response messages for the economy commands.\n\n"
            "**Available Variables:**\n"
            "`Add Credit`: {who_gave}, {credits_added}, {who_given}\n"
            "`Check Credit`: {user}, {credits}\n"
            "`Pay`: {user}, {price}, {item_name}, {new_adjusted_credit}"
        )
        
        await interaction.response.send_message(status_msg, view=CreditDashboardView(), ephemeral=True)

    @app_commands.command(name="add_credit", description="Adds credits to a user (Staff Only).")
    async def add_credit(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if not await self.has_perms(interaction):
            return await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            
        add_balance(user.id, amount)
        config = load_credit_config()
        
        try:
            formatted_message = config["add_credit_msg"].format(
                who_gave=interaction.user.mention,
                credits_added=amount,
                who_given=user.mention
            )
        except KeyError as e:
            return await interaction.response.send_message(f"Configuration error: missing placeholder {e}")
            
        await interaction.response.send_message(formatted_message)

    @app_commands.command(name="credit", description="Check your or someone else's credit balance.")
    async def credit(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        current_balance = get_balance(target.id)
        config = load_credit_config()
        
        try:
            formatted_message = config["check_credit_msg"].format(
                user=target.mention,
                credits=current_balance
            )
        except KeyError as e:
            return await interaction.response.send_message(f"Configuration error: missing placeholder {e}")
            
        await interaction.response.send_message(formatted_message)

    @app_commands.command(name="pay", description="Pay another user for an item.")
    async def pay(self, interaction: discord.Interaction, user: discord.Member, item_name: str, price: int):
        if price <= 0:
            return await interaction.response.send_message("The price must be greater than zero.", ephemeral=True)
            
        sender_balance = get_balance(interaction.user.id)
        
        if sender_balance < price:
            return await interaction.response.send_message("You do not have enough credits.", ephemeral=True)
            
        new_adjusted_credit = add_balance(interaction.user.id, -price)
        add_balance(user.id, price)
        config = load_credit_config()
        
        try:
            formatted_message = config["pay_msg"].format(
                user=interaction.user.mention,
                item_name=item_name,
                price=price,
                new_adjusted_credit=new_adjusted_credit
            )
        except KeyError as e:
            return await interaction.response.send_message(f"Configuration error: missing placeholder {e}")
            
        await interaction.response.send_message(formatted_message)

async def setup(bot):
    await bot.add_cog(CreditsSystem(bot))